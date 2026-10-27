"""MP4 export stage: render props -> render.mjs -> faststart -> ffprobe check (export.md §4)."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from threading import Thread
from time import monotonic, perf_counter

import psutil
from pydantic import ConfigDict, JsonValue

from ..cache import Cache
from ..config import Settings
from ..jobs import JobContext
from ..planner.schema import Lesson
from ..timeline.schema import RenderProps, Timeline
from .ffmpeg import ExportError, faststart, validate_mp4

DEFAULT_CONCURRENCY = 2
REQUIRED = ("lesson.json", "timeline.json", "narration.wav", "narration.m4a", "lesson.srt")


class ExportContext(JobContext):
    model_config = ConfigDict(arbitrary_types_allowed=True, validate_assignment=True)
    settings: Settings
    cache: Cache
    visual_spec: JsonValue | None = None  # explicit caller only; production jobs leave absent


def media_base(settings: Settings) -> str:
    return f"http://127.0.0.1:{settings.port}"


def media_url(lesson_id: str, variant: str, name: str) -> str:
    return f"/media/{lesson_id}/{variant}/{name}"


def check_inputs(folder: Path) -> tuple[Lesson, Timeline]:
    missing = [n for n in REQUIRED if not (folder / n).is_file() or (folder / n).stat().st_size == 0]
    if missing:
        raise ExportError(f"Missing export inputs in {folder.name}: {', '.join(missing)}. Run the voice and timeline stages first")
    lesson = Lesson.model_validate_json((folder / "lesson.json").read_text(encoding="utf-8"))
    timeline = Timeline.model_validate_json((folder / "timeline.json").read_text(encoding="utf-8"))
    RenderProps(lesson=lesson, timeline=timeline)  # lesson/timeline agreement
    if timeline.audio is None:
        raise ExportError("timeline.json has no audio URLs; the render needs the narration WAV")
    return lesson, timeline


def render_props(lesson: Lesson, timeline: Timeline, settings: Settings, *,
                 visual_spec: JsonValue | None = None) -> RenderProps:
    validated = None
    if visual_spec is not None:
        from ..visuals.validate import validate_visuals
        result = validate_visuals(visual_spec, lesson)
        if result.spec is not None:
            validated = result.spec.model_dump(mode="json")
    return RenderProps(lesson=lesson, timeline=timeline, mediaBase=media_base(settings),
                       audioVariant="wav", showCaptions=True, visualSpec=validated)


def props_sha1(props: RenderProps) -> str:
    return hashlib.sha1(json.dumps(props.model_dump(mode="json"), sort_keys=True,
                                   ensure_ascii=False).encode("utf-8")).hexdigest()


def check_media_reachable(settings: Settings, timeline: Timeline, folder: Path) -> None:
    """Remotion fetches the WAV over HTTP from this backend; fail early with a clear message."""
    assert timeline.audio is not None
    url = media_base(settings) + timeline.audio.wav
    expected = (folder / "narration.wav").stat().st_size
    try:
        with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=5) as response:
            length = int(response.headers.get("Content-Length", "-1"))
            status = response.status
    except urllib.error.HTTPError as exc:
        raise ExportError(f"Backend returned HTTP {exc.code} for {url}; the renderer cannot fetch the narration") from exc
    except (OSError, ValueError) as exc:
        raise ExportError(f"Cannot reach the backend at {media_base(settings)} to fetch {timeline.audio.wav}: {exc}. "
                          "Start it with uvicorn on 127.0.0.1 so the renderer can load audio") from exc
    if status != 200 or length != expected:
        raise ExportError(f"{url} returned status {status}, {length} bytes; expected 200 and {expected} bytes")


def kill_tree(process: subprocess.Popen) -> None:
    """Terminate the renderer and every descendant (Node workers, Chrome) on Windows and POSIX."""
    try:
        parent = psutil.Process(process.pid)
        family = parent.children(recursive=True) + [parent]
    except psutil.NoSuchProcess:
        return
    for p in family:
        try:
            p.kill()
        except psutil.NoSuchProcess:
            pass
    psutil.wait_procs(family, timeout=10)
    process.wait()


def command(settings: Settings, props: Path, raw: Path) -> list[str]:
    node = shutil.which(settings.node_binary)
    if node is None:
        raise ExportError(f"Node.js executable '{settings.node_binary}' was not found on PATH")
    if not settings.render_script.is_file():
        raise ExportError(f"Renderer not found: {settings.render_script} (Varun's web/render/render.mjs is not available yet)")
    concurrency = settings.render_concurrency or DEFAULT_CONCURRENCY
    return [node, str(settings.render_script), "--props", str(props), "--out", str(raw),
            "--concurrency", str(concurrency)]


def run_renderer(arguments: list[str], timeout: float, on_progress, log: Path, cwd: Path) -> dict:
    """Run render.mjs, parsing one JSON object per stdout line. Returns the `done` message."""
    result: dict = {}
    problems: list[str] = []
    with log.open("wb") as stderr:
        process = subprocess.Popen(arguments, stdout=subprocess.PIPE, stderr=stderr, stdin=subprocess.DEVNULL,
                                   cwd=cwd, shell=False)

        def read() -> None:
            for line in process.stdout:  # type: ignore[union-attr]
                text = line.decode("utf-8", errors="replace").strip()
                if not text:
                    continue
                try:
                    message = json.loads(text)
                except ValueError:
                    continue  # tolerate stray log lines
                if not isinstance(message, dict):
                    continue
                if "progress" in message:
                    try:
                        on_progress(min(1.0, max(0.0, float(message["progress"]))))
                    except (TypeError, ValueError):
                        pass
                elif message.get("done") is True:
                    result.update(message)
                elif "error" in message:
                    problems.append(str(message["error"]))

        reader = Thread(target=read, daemon=True)
        reader.start()
        deadline = monotonic() + timeout
        try:
            while process.poll() is None:
                if monotonic() > deadline:
                    kill_tree(process)
                    reader.join(5)
                    raise ExportError(f"Render timed out after {timeout:g}s; renderer process tree terminated")
                reader.join(0.1)
        except BaseException:
            if process.poll() is None:
                kill_tree(process)
            raise
        reader.join(10)
    if problems or process.returncode != 0:
        tail = log.read_text(encoding="utf-8", errors="replace").strip()[-400:]
        detail = "; ".join(problems) or tail or "no error message"
        raise ExportError(f"Renderer failed (exit {process.returncode}): {detail}")
    if not result:
        raise ExportError("Renderer exited 0 without reporting done")
    return result


def run_export(ctx: ExportContext) -> ExportContext:
    started = perf_counter()
    stage = next(s for s in ctx.job.stages if s.name == "export")
    folder = ctx.cache.lesson_dir(ctx.job.lesson_id, ctx.job.variant)
    lesson, timeline = check_inputs(folder)
    props = render_props(lesson, timeline, ctx.settings, visual_spec=ctx.visual_spec)
    if ctx.visual_spec is not None and props.visualSpec is None:
        warning = "VisualSpec rejected against canonical source; rendering legacy scenes"
        if warning not in ctx.job.warnings:
            ctx.job.warnings.append(warning)
    digest = props_sha1(props)
    mp4, raw, sha_file = folder / "lesson.mp4", folder / "raw.mp4", folder / "props.sha1"
    expected = timeline.duration_frames / timeline.fps

    if sha_file.is_file() and sha_file.read_text(encoding="ascii", errors="replace").strip() == digest and mp4.is_file():
        try:
            validate_mp4(mp4, expected, ctx.settings.ffprobe)
            stage.status, stage.note = "cached", "lesson.mp4 matches props.sha1 and passed ffprobe"
            ctx.job.progress = 1.0
            return ctx
        except ExportError:
            pass  # stale or damaged: re-render

    ctx.job.progress = 0.0
    check_media_reachable(ctx.settings, timeline, folder)
    props_path = folder / "render.props.json"  # props.json stays the browser-player configuration
    ctx.cache.write_json(props_path, props)
    sha_file.unlink(missing_ok=True)
    raw.unlink(missing_ok=True)
    arguments = command(ctx.settings, props_path, raw)

    def progress(value: float) -> None:
        ctx.job.progress = value * 0.95  # remux + probe take the last 5%

    run_renderer(arguments, ctx.settings.render_timeout_seconds, progress, folder / "render.stderr.log", ctx.settings.render_script.parent)
    if not raw.is_file():
        raise ExportError("Renderer reported done but raw.mp4 was not written")
    faststart(raw, mp4, ctx.settings.ffmpeg)
    try:
        duration = validate_mp4(mp4, expected, ctx.settings.ffprobe)
    except ExportError:
        mp4.unlink(missing_ok=True)
        raise
    raw.unlink(missing_ok=True)
    sha_file.write_text(digest, encoding="ascii")
    ctx.job.progress = 1.0
    stage.note = f"lesson.mp4 {duration:.2f}s in {perf_counter() - started:.1f}s"
    return ctx
