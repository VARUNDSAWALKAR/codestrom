"""Task 6 production bridge/API tests; no model or real media generation."""
from dataclasses import replace
import json
import time

from fastapi.testclient import TestClient
import pytest

from backend.app import pipeline_ops
from backend.app.cache import Cache
from backend.app.config import ROOT, Settings
from backend.app.localize import localize_lesson
from backend.app.localize import model
from backend.app.main import create_app
from backend.app.planner.schema import Lesson
from backend.app.timeline.schema import RenderProps
from backend.app.timeline.srt import render_srt
from backend.tests.test_task5b import synthetic_timeline
from backend.tests.test_task6_localize import Fake

KEY = "c1f63f0ed69b"
BODY = {"topic": "Water Cycle", "subject": "science", "language": "hi"}


def seed(settings):
    lesson = Lesson.model_validate_json((ROOT / "data/samples/planner/water_cycle.json").read_text(encoding="utf-8"))
    Cache(settings.cache_dir).write_json(settings.cache_dir / "lessons" / KEY / "plan.json",
                                         lesson.model_dump(mode="json", exclude_unset=True))


def wait(client, job_id):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] in {"done", "error"}:
            return job
        time.sleep(0.01)
    pytest.fail("Mock job timed out")


@pytest.fixture
def bridge(tmp_path, monkeypatch):
    settings = Settings(device="cpu", cache_dir=tmp_path / "cache", approved_languages="en,hi")
    seed(settings)
    fake = Fake()
    contexts = []

    def translate(lesson, lang, config, **kwargs):
        return localize_lesson(lesson, lang, config, fake, **kwargs)

    def voice(ctx):
        contexts.append(ctx)
        assert ctx.lesson.language == ctx.language == ctx.request.language
        assert ctx.lesson.lesson_id == ctx.job.lesson_id == KEY
        return ctx

    def timeline(ctx):
        timing = synthetic_timeline(ctx.lesson, ctx.job.variant)
        folder = ctx.cache.lesson_dir(KEY, ctx.job.variant)
        props = RenderProps(lesson=ctx.lesson, timeline=timing)
        for name, obj in (("lesson.json", ctx.lesson), ("timeline.json", timing), ("props.json", props)):
            ctx.cache.write_json(folder / name, obj)
        (folder / "lesson.srt").write_text(render_srt(timing), encoding="utf-8")
        (folder / "narration.wav").write_bytes(b"synthetic-test-wave")
        (folder / "narration.m4a").write_bytes(b"synthetic-test-m4a")
        return ctx

    monkeypatch.setattr(pipeline_ops, "localize_lesson", translate)
    monkeypatch.setattr(pipeline_ops, "run_voice", voice)
    monkeypatch.setattr(pipeline_ops, "run_timeline", timeline)
    ops = replace(pipeline_ops.production_ops(settings=settings), export=lambda run: run.skip("Mock test; no MP4"))
    return settings, fake, contexts, ops


def test_default_approval_and_explicit_kannada_approval(tmp_path):
    for approval in ("en", "en,hi,kn,ta"):
        settings = Settings(device="cpu", cache_dir=tmp_path / approval.replace(",", "-"),
                            approved_languages=approval, parler_seed=21, parler_max_new_tokens=1500)
        with TestClient(create_app(settings)) as client:
            available = {x["code"] for x in client.get("/api/config").json()["languages"] if x["available"]}
            assert available == ({"en"} if approval == "en" else {"en", "hi", "kn"})
            for lang in ("ta",) + (("hi", "kn") if approval == "en" else ()):
                reply = client.post("/api/lessons", json={**BODY, "language": lang})
                assert reply.status_code == 422 and reply.json()["error"]["code"] == "language_unavailable"


def test_settings_parse_approval_and_ceiling():
    assert Settings(approved_languages=" en, hi,en ").approved_languages == ("en", "hi")
    assert Settings().approved_languages == ("en",)
    with pytest.raises(ValueError):
        Settings(approved_languages="en,unknown")
    with pytest.raises(ValueError):
        Settings(localize_max_english_fraction=1.1)


def test_hindi_bridge_identity_preview_and_cache(bridge, monkeypatch):
    settings, fake, contexts, ops = bridge
    from backend.app.planner import ollama_client
    monkeypatch.setattr(ollama_client.httpx, "Client", lambda *a, **k: pytest.fail("Cached plan must not contact Ollama"))
    with TestClient(create_app(settings, ops)) as client:
        first = client.post("/api/lessons", json=BODY).json()
        job = wait(client, first["job_id"])
        assert job["status"] == "done" and job["preview_ready"]
        assert job["export_status"] == "skipped" and job["variant"] == "hi-female-1"
        assert job["lesson_id"] == KEY and contexts[0].lesson.language == "hi"
        response = client.get(f"/api/lessons/{KEY}?variant=hi-female-1").json()
        assert response["media"]["mp4"] is None and response["media"]["srt"]
        assert response["lesson"]["title"] != "Water Cycle"
        before = len(fake.calls)
        again = client.post("/api/lessons", json=BODY).json()
        repeated = wait(client, again["job_id"])
        assert repeated["stages"][2]["status"] == "cached"
        assert len(fake.calls) == before


def test_incomplete_translation_stops_before_voice(bridge):
    settings, fake, contexts, ops = bridge
    fake.transform = lambda text, beams: text  # guaranteed English/script failure
    with TestClient(create_app(settings, ops)) as client:
        reply = client.post("/api/lessons", json=BODY).json()
        job = wait(client, reply["job_id"])
        assert job["status"] == "error" and job["error_detail"]["code"] == "translate_incomplete"
        assert not job["preview_ready"] and not contexts
        assert job["stages"][3]["status"] == "pending"
        assert (settings.cache_dir / "lessons" / KEY / "hi-female-1/localization.json").is_file()


def test_translation_exception_is_structured(bridge, monkeypatch):
    settings, fake, contexts, ops = bridge
    def fail(*args, **kwargs):
        raise RuntimeError("Local model load failed")
    monkeypatch.setattr(pipeline_ops, "localize_lesson", fail)
    with TestClient(create_app(settings, ops)) as client:
        reply = client.post("/api/lessons", json=BODY).json()
        job = wait(client, reply["job_id"])
        assert job["error_detail"] == {"stage": "translate", "code": "translate_failed", "message": "Local model load failed"}
        assert not contexts and not job["fallback"]


def test_english_skips_translation(bridge, monkeypatch):
    settings, _, contexts, ops = bridge
    monkeypatch.setattr(pipeline_ops, "localize_lesson", lambda *a, **k: pytest.fail("English must skip localization"))
    with TestClient(create_app(settings, ops)) as client:
        reply = client.post("/api/lessons", json={**BODY, "language": "en"}).json()
        job = wait(client, reply["job_id"])
        assert job["status"] == "done" and job["stages"][2]["status"] == "skipped"
        assert contexts[0].lesson.language == "en"


def test_health_requires_successful_init_and_tracks_release(tmp_path):
    settings = Settings(device="cpu", cache_dir=tmp_path / "cache", indictrans_model=tmp_path / "unloaded")
    instance = model.get_translator(settings)
    with TestClient(create_app(settings, replace(pipeline_ops.production_ops(settings=settings), precheck=None))) as client:
        assert not client.get("/api/health").json()["models"]["translator"]["ready"]
        instance.model = object()  # successful initialization stand-in; no model imported
        try:
            assert client.get("/api/health").json()["models"]["translator"]["ready"]
        finally:
            model.release_translator(settings)
        assert not client.get("/api/health").json()["models"]["translator"]["ready"]


def test_low_ram_release_occurs_after_commit(bridge, monkeypatch):
    settings, fake, _, _ = bridge
    settings = settings.model_copy(update={"low_ram": True})
    from backend.app.localize import translate
    released = []
    monkeypatch.setattr(translate, "get_translator", lambda settings: fake)
    def release(config):
        assert (config.cache_dir / "lessons" / KEY / "hi-female-1/localization.json").is_file()
        assert (config.cache_dir / "translations/hi.json").is_file()
        released.append(True)
    monkeypatch.setattr(translate, "release_translator", release)
    source = Lesson.model_validate_json((settings.cache_dir / "lessons" / KEY / "plan.json").read_text(encoding="utf-8"))
    localize_lesson(source, "hi", settings)
    assert released == [True]
