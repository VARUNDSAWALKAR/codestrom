"""Task 3 tests. The renderer here is backend/tests/fake_render.py (a test double): these tests prove the
backend orchestration only, NOT that Varun's Remotion renderer works."""
from __future__ import annotations

import http.server
import json
import shutil
import socketserver
import sys
import threading
from pathlib import Path

import psutil
import pytest
from fastapi.testclient import TestClient

from backend.app.cache import Cache, variant_key
from backend.app.config import get_settings
from backend.app.export import render as R
from backend.app.export.ffmpeg import ExportError, validate_mp4
from backend.app.export.render import ExportContext, run_export
from backend.app.jobs import JobRecord, run_measured_stage
from backend.app.main import create_app
from backend.app.planner.schema import Lesson
from backend.app.timeline.build import schedule
from backend.app.timeline.schema import Timeline
from backend.app.timeline.srt import render_srt
from backend.tests.test_task2 import FALLBACK, ctx_for, fake_clips

FAKE = Path(__file__).with_name("fake_render.py")
LESSON_ID, VARIANT = "fallback-python-loop", variant_key("en", "female", 1)
HAVE_TOOLS = bool(shutil.which(get_settings().ffmpeg) and shutil.which(get_settings().ffprobe))
needs_tools = pytest.mark.skipif(not HAVE_TOOLS, reason="ffmpeg/ffprobe missing")


class MediaHandler(http.server.SimpleHTTPRequestHandler):
    def translate_path(self, path):
        return super().translate_path(path.removeprefix("/media"))

    def log_message(self, *a):
        pass


@pytest.fixture()
def env(tmp_path):
    """Synthetic Task 2 artifacts + a localhost media server + settings pointing at the fake renderer."""
    lesson = Lesson.model_validate_json(FALLBACK.read_text(encoding="utf-8"))
    scenes, _, _ = schedule(ctx_for(lesson), fake_clips(lesson, tmp_path, 0.5))
    timeline = Timeline(lesson_id=LESSON_ID, language="en", variant=VARIANT, duration_frames=sum(s.duration_frames for s in scenes),
                        audio={"web": f"/media/{LESSON_ID}/{VARIANT}/narration.m4a", "wav": f"/media/{LESSON_ID}/{VARIANT}/narration.wav"},
                        voice={"engine": "kokoro", "voice_id": "hf_alpha", "speed": 1.0}, scenes=scenes)
    cache = Cache(tmp_path / "cache")
    cache.initialize()
    folder = cache.lesson_dir(LESSON_ID, VARIANT)
    folder.mkdir(parents=True)
    cache.write_json(folder / "lesson.json", lesson)
    cache.write_json(folder / "timeline.json", timeline)
    (folder / "narration.wav").write_bytes(b"RIFF" + b"0" * 1000)
    (folder / "narration.m4a").write_bytes(b"m4a" * 100)
    (folder / "lesson.srt").write_text(render_srt(timeline), encoding="utf-8")
    handler = lambda *a, **k: MediaHandler(*a, directory=str(cache.lessons), **k)
    server = socketserver.TCPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    settings = get_settings().model_copy(update={"cache_dir": cache.root, "port": server.server_address[1],
                                                 "render_script": FAKE, "node_binary": sys.executable,
                                                 "render_timeout_seconds": 60})
    ctx = ExportContext(job=JobRecord(lesson_id=LESSON_ID, variant=VARIANT, device_profile="cpu"),
                        language="en", settings=settings, cache=cache)
    yield ctx, folder, timeline, server
    server.shutdown()
    server.server_close()


def with_settings(ctx, **kw):
    return ctx.model_copy(update={"settings": ctx.settings.model_copy(update=kw)})


def stage_of(ctx):
    return next(s for s in ctx.job.stages if s.name == "export")


# ---- inputs ----
def test_missing_inputs_named(env):
    ctx, folder, *_ = env
    (folder / "narration.wav").unlink()
    (folder / "lesson.srt").unlink()
    with pytest.raises(ExportError, match=r"narration\.wav, lesson\.srt"):
        run_export(ctx)


def test_timeline_without_audio_rejected(env):
    ctx, folder, timeline, _ = env
    ctx.cache.write_json(folder / "timeline.json", timeline.model_copy(update={"audio": None}))
    with pytest.raises(ExportError, match="no audio"):
        run_export(ctx)


# ---- command construction ----
def test_command_arguments(env):
    ctx, folder, *_ = env
    cmd = R.command(with_settings(ctx, render_concurrency=0).settings, folder / "p.json", folder / "raw.mp4")
    assert cmd[1:] == [str(FAKE), "--props", str(folder / "p.json"), "--out", str(folder / "raw.mp4"), "--concurrency", "2"]
    cmd = R.command(ctx.settings.model_copy(update={"render_concurrency": 4}), folder / "p.json", folder / "raw.mp4")
    assert cmd[-2:] == ["--concurrency", "4"]


def test_command_rejects_missing_renderer_and_node(env):
    ctx, folder, *_ = env
    with pytest.raises(ExportError, match="Renderer not found"):
        R.command(ctx.settings.model_copy(update={"render_script": folder / "nope.mjs"}), folder / "p", folder / "r")
    with pytest.raises(ExportError, match="Node.js"):
        R.command(ctx.settings.model_copy(update={"node_binary": "definitely-not-node-xyz"}), folder / "p", folder / "r")


def test_real_render_script_absent_is_actionable():
    s = get_settings()
    if s.render_script.is_file():
        pytest.skip("web/render/render.mjs now exists")
    with pytest.raises(ExportError, match="not available yet|not found"):
        R.command(s.model_copy(update={"node_binary": sys.executable}), Path("p"), Path("r"))


# ---- render props ----
def test_render_props_use_http_media_and_wav_without_touching_player_props(env):
    ctx, folder, timeline, _ = env
    lesson = Lesson.model_validate_json((folder / "lesson.json").read_text(encoding="utf-8"))
    props = R.render_props(lesson, timeline, ctx.settings)
    assert props.mediaBase == f"http://127.0.0.1:{ctx.settings.port}" and props.audioVariant == "wav" and props.showCaptions
    assert not (folder / "props.json").exists()  # the browser-player props are left alone


# ---- media reachability ----
def test_unreachable_backend_actionable(env):
    ctx, folder, timeline, server = env
    server.shutdown()
    server.server_close()
    with pytest.raises(ExportError, match="Cannot reach the backend"):
        R.check_media_reachable(ctx.settings, timeline, folder)


def test_missing_media_404(env):
    ctx, folder, timeline, _ = env
    R.check_media_reachable(ctx.settings, timeline, folder)
    bad = timeline.model_copy(update={"audio": timeline.audio.model_copy(update={"wav": "/media/nothing/here.wav"})})
    with pytest.raises(ExportError, match="HTTP 404"):
        R.check_media_reachable(ctx.settings, bad, folder)


def test_export_fails_before_rendering_when_media_missing(env, monkeypatch):
    ctx, folder, _, server = env
    server.shutdown()
    server.server_close()
    monkeypatch.setattr(R, "run_renderer", lambda *a, **k: pytest.fail("renderer must not start"))
    with pytest.raises(ExportError, match="backend"):
        run_export(ctx)


# ---- renderer success / progress / caching ----
@needs_tools
def test_success_progress_faststart_and_media_url(env, monkeypatch):
    ctx, folder, timeline, _ = env
    seen = []
    real = R.run_renderer
    monkeypatch.setattr(R, "run_renderer", lambda a, t, cb, *r: real(a, t, lambda v: (seen.append(v), cb(v)), *r))
    run_measured_stage(ctx, "export", run_export, ctx.cache)
    assert stage_of(ctx).status == "done" and ctx.job.progress == 1.0
    assert seen == [0.25, 0.5, 1.0]
    assert (folder / "lesson.mp4").is_file() and not (folder / "raw.mp4").exists()
    assert validate_mp4(folder / "lesson.mp4", timeline.duration_frames / 30, ctx.settings.ffprobe) > 0
    sent = json.loads((folder / "fake.args.json").read_text())
    assert sent[sent.index("--concurrency") + 1] == "2" and sent[sent.index("--out") + 1].endswith("raw.mp4")
    rendered = json.loads((folder / "render.props.json").read_text(encoding="utf-8"))
    assert rendered["audioVariant"] == "wav" and rendered["mediaBase"].startswith("http://127.0.0.1:")
    # faststart: moov precedes mdat
    head = (folder / "lesson.mp4").read_bytes()[:4096]
    assert head.find(b"moov") != -1 and head.find(b"moov") < (head.find(b"mdat") if b"mdat" in head else 10 ** 9)
    # run log written
    assert '"stage":"export"' in ctx.cache.runs.read_text(encoding="utf-8").replace(" ", "")
    # served through /media
    client = TestClient(create_app(ctx.settings))
    response = client.get(f"/media/{LESSON_ID}/{VARIANT}/lesson.mp4")
    assert response.status_code == 200 and response.content == (folder / "lesson.mp4").read_bytes()
    assert client.get(f"/media/{LESSON_ID}/{VARIANT}/../../index.json").status_code in {400, 404}


@needs_tools
def test_cache_hit_only_when_sha1_matches_and_mp4_valid(env, monkeypatch):
    ctx, folder, *_ = env
    run_export(ctx)
    monkeypatch.setattr(R, "run_renderer", lambda *a, **k: pytest.fail("should be a cache hit"))
    again = ExportContext(job=JobRecord(lesson_id=LESSON_ID, variant=VARIANT, device_profile="cpu"),
                          language="en", settings=ctx.settings, cache=ctx.cache)
    run_export(again)
    assert stage_of(again).status == "cached"
    # mp4 alone is not proof: remove the sha1 -> re-render attempted
    (folder / "props.sha1").unlink()
    with pytest.raises(pytest.fail.Exception):
        run_export(again)


@needs_tools
def test_stale_sha1_or_corrupt_mp4_rerenders(env):
    ctx, folder, *_ = env
    run_export(ctx)
    (folder / "props.sha1").write_text("0" * 40)
    first = (folder / "lesson.mp4").stat().st_mtime_ns
    run_export(ctx)
    assert stage_of(ctx).status != "cached" and (folder / "lesson.mp4").stat().st_mtime_ns != first
    (folder / "lesson.mp4").write_bytes(b"garbage")
    run_export(ctx)
    frames = Timeline.model_validate_json((folder / "timeline.json").read_text(encoding="utf-8")).duration_frames
    validate_mp4(folder / "lesson.mp4", frames / 30, ctx.settings.ffprobe)


# ---- renderer failures ----
@pytest.mark.parametrize("mode,message", [("fail", "chrome exploded"), ("errorjson", "composition Lesson not found"),
                                          ("silentdone", "without reporting done"), ("nofile", "raw.mp4 was not written")])
@needs_tools
def test_renderer_failures(env, monkeypatch, mode, message):
    ctx, folder, *_ = env
    monkeypatch.setenv("FAKE_MODE", mode)
    with pytest.raises(ExportError, match=message):
        run_measured_stage(ctx, "export", run_export, ctx.cache)
    assert stage_of(ctx).status == "error" and message in stage_of(ctx).note
    assert not (folder / "lesson.mp4").exists() and not (folder / "props.sha1").exists()
    assert '"ok":false' in ctx.cache.runs.read_text(encoding="utf-8").replace(" ", "")


# ---- ffprobe validation ----
@pytest.mark.parametrize("mode,message", [("badres", "640x360"), ("noaudio", "AAC audio"), ("shortdur", "differs from timeline")])
@needs_tools
def test_ffprobe_rejections_remove_output(env, monkeypatch, mode, message):
    ctx, folder, *_ = env
    monkeypatch.setenv("FAKE_MODE", mode)
    with pytest.raises(ExportError, match=message):
        run_export(ctx)
    assert not (folder / "lesson.mp4").exists() and not (folder / "props.sha1").exists()


def test_validate_rejects_missing_and_empty(tmp_path):
    with pytest.raises(ExportError):
        validate_mp4(tmp_path / "x.mp4", 1, "ffprobe")
    (tmp_path / "e.mp4").write_bytes(b"")
    with pytest.raises(ExportError):
        validate_mp4(tmp_path / "e.mp4", 1, "ffprobe")


# ---- timeout ----
@needs_tools
def test_timeout_kills_entire_process_tree(env, monkeypatch, tmp_path):
    ctx, folder, *_ = env
    pids = tmp_path / "pids.txt"
    monkeypatch.setenv("FAKE_MODE", "hang")
    monkeypatch.setenv("FAKE_PIDS", str(pids))
    with pytest.raises(ExportError, match="timed out"):
        run_export(with_settings(ctx, render_timeout_seconds=3))
    parent, child = map(int, pids.read_text().split())
    assert not psutil.pid_exists(parent) and not psutil.pid_exists(child)
    assert not (folder / "lesson.mp4").exists()


# ---- safe paths ----
def test_unsafe_ids_rejected(env):
    ctx, *_ = env
    for lesson_id, variant in (("../escape", VARIANT), (LESSON_ID, "../../x"), ("0123456789ab/..", VARIANT)):
        bad = ExportContext(job=JobRecord(lesson_id=lesson_id, variant=variant, device_profile="cpu"),
                            language="en", settings=ctx.settings, cache=ctx.cache)
        with pytest.raises(ValueError):
            run_export(bad)


def test_popen_never_uses_shell(env, monkeypatch):
    ctx, folder, *_ = env
    calls = []
    real = R.subprocess.Popen

    def spy(*a, **k):
        calls.append(k)
        return real(*a, **k)

    monkeypatch.setattr(R.subprocess, "Popen", spy)
    monkeypatch.setenv("FAKE_MODE", "fail")
    with pytest.raises(ExportError):
        run_export(ctx)
    assert calls and all(c.get("shell") is False for c in calls)
