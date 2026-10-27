"""Production PipelineOps (Task 5B): adapts the real planner, Kokoro, timeline and exporter to the 5A orchestrator.

Each operation is a thin bridge: it builds the typed context the existing stage function expects
from the PipelineRun, calls it, and maps failures to PipelineError codes. Nothing here loads a
model at import time; Kokoro loads on the first uncached voice beat and is reused afterwards.
Production is English-only until translation and multilingual voices are integrated.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from pathlib import Path
from threading import Event, Lock, Thread

import httpx

from .config import Settings
from .contracts import LessonRequest
from .export.ffmpeg import validate_mp4
from .export.render import ExportContext, check_inputs, props_sha1, render_props, run_export
from .jobs import PipelineError
from .orchestrator import PipelineOps, PipelineRun, default_validate
from .planner.ollama_client import PlanRequest, plan_lesson
from .planner.schema import Lesson
from .speech.engines import NarrationContext, run_voice
from .speech.kokoro_engine import KokoroEngine
from .timeline.build import run_timeline

logger = logging.getLogger(__name__)
PROGRESS_INTERVAL = 0.5  # seconds between progress publishes while the exporter runs
PROBE_TTL = 5.0  # seconds a planner-availability answer is reused by GET /api/health
LANGUAGE_MESSAGE = ("Hindi/Kannada need translation and voice integration that is not connected yet; "
                    "only English ('en') lessons are available")


class ProductionKokoro(KokoroEngine):
    """The existing engine plus a one-shot hook that fires after a real, successful model load."""

    def __init__(self, settings: Settings, on_loaded: Callable[[], None] | None = None) -> None:
        super().__init__(settings)
        self._on_loaded = on_loaded

    def load(self) -> None:
        super().load()  # raises if the local model cannot be loaded; the hook never fires then
        if self._on_loaded is not None:
            self._on_loaded()


def ollama_has_model(settings: Settings, model: str, transport: httpx.BaseTransport | None = None) -> bool:
    """True only when the local Ollama service answers and lists `model` (Ollama /api/tags)."""
    try:
        with httpx.Client(base_url=settings.ollama_url, timeout=2.0, trust_env=False,
                          follow_redirects=False, transport=transport) as client:
            response = client.get("/api/tags")
            response.raise_for_status()
            return any(m.get("name") == model or m.get("model") == model for m in response.json().get("models", []))
    except (httpx.HTTPError, ValueError, AttributeError):
        return False


def planner_probe(settings: Settings, model: str) -> Callable[[], bool]:
    """A health probe that asks Ollama at most once per PROBE_TTL seconds."""
    state: dict[str, float | bool] = {"at": float("-inf"), "ready": False}
    lock = Lock()

    def probe() -> bool:
        with lock:
            if time.monotonic() - float(state["at"]) >= PROBE_TTL:
                state["ready"], state["at"] = ollama_has_model(settings, model), time.monotonic()
            return bool(state["ready"])

    return probe


def unload_planner(settings: Settings, model: str, transport: httpx.BaseTransport | None = None) -> None:
    """Ask Ollama to drop only the planner model from memory (LOW_RAM, once per job)."""
    with httpx.Client(base_url=settings.ollama_url, timeout=30.0, trust_env=False,
                      follow_redirects=False, transport=transport) as client:
        client.post("/api/chat", json={"model": model, "keep_alive": 0}).raise_for_status()


def export_complete(folder: Path, settings: Settings) -> bool:
    """A finished export has valid inputs, a props.sha1 matching the current props, and a probe-valid MP4."""
    try:
        lesson, timeline = check_inputs(folder)
        sha = folder / "props.sha1"
        if not sha.is_file() or sha.read_text(encoding="ascii", errors="replace").strip() != props_sha1(
                render_props(lesson, timeline, settings)):
            return False
        validate_mp4(folder / "lesson.mp4", timeline.duration_frames / timeline.fps, settings.ffprobe)
        return True
    except Exception:  # damaged or partial output is simply "not complete"
        return False


def precheck(request: LessonRequest) -> None:
    if request.language != "en":
        raise PipelineError("language_unavailable", LANGUAGE_MESSAGE)


def plan(run: PipelineRun) -> None:
    request = PlanRequest(topic=run.request.topic, level=run.request.level, language=run.request.language,
                          target_seconds=run.request.target_seconds, subject=run.request.subject)
    result = plan_lesson(request, run.settings)
    if result.error is not None or result.lesson is None:
        error = result.error
        raise PipelineError(error.code if error else "planner_error", error.message if error else "Planner returned no lesson")
    for note in result.notes:
        run.warn(note)
    run.lesson = result.lesson
    if result.cached:
        run.cached("Planner cache hit")
    else:
        run.note(f"{result.model}; {result.attempts} attempt(s); {result.generation_seconds:.1f}s generation")


def validate(run: PipelineRun) -> None:
    """The planner already validated the lesson; re-check contract and identity only (no Ollama call)."""
    lesson = run.lesson
    if lesson is None or lesson.lesson_id != run.lesson_id or lesson.language != "en":
        raise PipelineError("plan_invalid", "Validated lesson does not match the job's identity")
    try:
        Lesson.model_validate(lesson.model_dump(mode="json"))
    except ValueError as exc:
        raise PipelineError("validation_failed", str(exc)) from exc
    default_validate(run)


def localize(run: PipelineRun) -> None:
    raise PipelineError("localize_unavailable", LANGUAGE_MESSAGE)


def production_ops(on_tts_loaded: Callable[[], None] | None = None) -> PipelineOps:
    """Build the production operations. One Kokoro engine is created lazily and reused by every job."""
    engines: dict[Path, ProductionKokoro] = {}
    lock = Lock()

    def engine_for(settings: Settings) -> ProductionKokoro:
        with lock:
            if settings.kokoro_model not in engines:
                engines[settings.kokoro_model] = ProductionKokoro(settings, on_tts_loaded)
            return engines[settings.kokoro_model]

    def voice(run: PipelineRun) -> None:
        if run.settings.low_ram:  # free RAM for TTS: unload only the planner model, once per job
            model = run.settings.planner_model(run.ctx.job.device_profile)
            try:
                unload_planner(run.settings, model)
                run.note(f"LOW_RAM: unloaded {model}")
            except (httpx.HTTPError, OSError) as exc:
                run.warn(f"LOW_RAM: could not unload planner model {model}: {exc}")
        assert run.lesson is not None
        context = NarrationContext(job=run.ctx.job, language=run.language, request=run.request,
                                   lesson=run.lesson, settings=run.settings, cache=run.cache,
                                   engine=engine_for(run.settings), gender=run.request.voice, speed=run.request.speed)
        try:
            run_voice(context)
        except Exception as exc:
            raise PipelineError("tts_failed", str(exc)) from exc
        run.data["narration"] = context

    def timeline(run: PipelineRun) -> None:
        context: NarrationContext = run.data["narration"]
        try:
            run_timeline(context)
        except Exception as exc:
            run.ctx.job.playable = False
            raise PipelineError("timeline_failed", str(exc)) from exc
        # run_timeline marks the job playable itself; only the verified preview may do that.
        run.ctx.job.playable = False
        run.preview_ready()

    def export(run: PipelineRun) -> None:
        context = ExportContext(job=run.ctx.job, language=run.language, request=run.request,
                                settings=run.settings, cache=run.cache)
        stop = Event()

        def pump() -> None:  # run_export updates job.progress in place; publish it while it runs
            while not stop.wait(PROGRESS_INTERVAL):
                run.progress(run.ctx.job.progress)

        thread = Thread(target=pump, name="export-progress", daemon=True)
        thread.start()
        try:
            run_export(context)
        except Exception as exc:
            raise PipelineError("export_failed", str(exc)) from exc
        finally:
            stop.set()
            thread.join()

    return PipelineOps(plan=plan, localize=localize, voice=voice, timeline=timeline, export=export,
                       validate=validate, precheck=precheck, export_complete=export_complete, mock=False)
