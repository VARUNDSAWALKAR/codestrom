"""Kannada TTS/integration tests. All synthesis/model initialization is faked."""
from dataclasses import replace
import json
from pathlib import Path
from threading import Event, Thread
import time

import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend.app import pipeline_ops
from backend.app.cache import Cache, variant_key
from backend.app.config import ROOT, Settings
from backend.app.contracts import LessonRequest
from backend.app.jobs import JobContext, JobRecord, PipelineError
from backend.app.localize import localize_lesson
from backend.app.main import create_app
from backend.app.planner import ollama_client
from backend.app.planner.schema import Lesson
from backend.app.speech.audio import read_clip
from backend.app.speech.engines import NarrationContext, run_voice
from backend.app.speech.kn_textnorm import normalize_kannada
from backend.app.speech.parler_engine import ParlerEngine, get_parler_engine, parler_ready, release_parler
from backend.app.timeline.schema import RenderProps
from backend.app.timeline.srt import render_srt


class FakeParler(ParlerEngine):
    def __init__(self, settings):
        super().__init__(settings)
        self.loads = self.calls = 0
        self.rate = 24000
        self.duration = 0.1
        self._version = "fake-local-parler-v1"

    def _load_components(self):
        self.loads += 1
        return object(), object(), object()

    def _generate(self, text, speaker):
        self.load()
        self.calls += 1
        t = np.arange(round(self.rate*self.duration)) / self.rate
        return (0.2*np.sin(2*np.pi*220*t)).astype(np.float32), self.rate


@pytest.fixture
def settings(tmp_path):
    return Settings(device="cpu", cache_dir=tmp_path / "cache")


def lesson():
    return Lesson.model_validate_json((ROOT / "data/samples/localized/water_cycle.kn.json").read_text(encoding="utf-8"))


def context(settings, engine, *, gender="female", speed=1.0, localized=None):
    source = localized or lesson()
    request = LessonRequest(topic=source.topic, subject="science", language="kn", voice=gender, speed=speed)
    return NarrationContext(job=JobRecord(lesson_id=source.lesson_id, variant=variant_key("kn", gender, speed), device_profile="cpu"),
        request=request, language="kn", lesson=source, settings=settings, cache=Cache(settings.cache_dir),
        engine=engine, gender=gender, speed=speed)


def test_lazy_load_and_safe_reuse(settings):
    engine = FakeParler(settings)
    assert engine.loads == 0 and not engine.ready
    engine.load()
    engine.load()
    assert engine.loads == 1 and engine.ready
    engine.release()
    assert not engine.ready


def test_cpu_configuration_local_assets_and_independent_tokenizers(settings, monkeypatch):
    from types import SimpleNamespace
    import sys
    calls = []
    class Tokenizer:
        @classmethod
        def from_pretrained(cls, path, **kwargs):
            calls.append(("tokenizer", path, kwargs))
            return object()
    class Model:
        @classmethod
        def from_pretrained(cls, path, **kwargs):
            calls.append(("model", path, kwargs))
            return cls()
        def to(self, device):
            assert device == "cpu"
            return self
        def eval(self):
            return self
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(set_num_threads=lambda n: None, float32="fp32", bfloat16="bf16"))
    monkeypatch.setitem(sys.modules, "transformers", SimpleNamespace(AutoTokenizer=Tokenizer))
    monkeypatch.setitem(sys.modules, "parler_tts", SimpleNamespace(ParlerTTSForConditionalGeneration=Model))
    engine = ParlerEngine(settings)
    engine.load()
    assert engine.ready
    assert len(calls) == 3 and all(kwargs["local_files_only"] for _, _, kwargs in calls)
    assert calls[0][1] == str(settings.parler_model)
    assert calls[1][1] == str(settings.parler_description_tokenizer)
    assert calls[0][1] != calls[1][1]
    assert calls[2][2]["torch_dtype"] == "fp32"


def test_concurrent_initialization_occurs_once(settings):
    engine = FakeParler(settings)
    threads = [Thread(target=engine.load) for _ in range(5)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(2)
    assert engine.loads == 1


def test_release_waits_for_active_session(settings):
    engine = FakeParler(settings)
    engine.load()
    entered = Event()
    with engine.session():
        thread = Thread(target=lambda: (engine.release(), entered.set()))
        thread.start()
        assert not entered.wait(0.03)
    thread.join(2)
    assert entered.is_set() and not engine.ready


def test_named_speakers_and_unsupported_voice(settings):
    engine = FakeParler(settings)
    engine.rate = 44100
    for speaker in ("Anu", "Suresh"):
        audio, rate = engine.synthesize("ನೀರು Python 3", "kn", speaker, 1)
        assert len(audio) and rate == 44100
    for lang, speaker in (("en", "Anu"), ("kn", "hf_alpha"), ("kn", "unknown")):
        with pytest.raises(PipelineError, match="named speakers"):
            engine.synthesize("text", lang, speaker, 1)


@pytest.mark.parametrize("raw", [np.zeros(10), np.full(10, np.nan), np.zeros((2, 10)), np.array([])])
def test_silent_invalid_audio_rejected(settings, raw, monkeypatch):
    engine = FakeParler(settings)
    monkeypatch.setattr(engine, "_generate", lambda *a: (raw, 44100))
    with pytest.raises(PipelineError) as exc:
        engine.synthesize("ನೀರು", "kn", "Anu", 1)
    assert exc.value.code == "tts_invalid_audio"


def test_kannada_audio_beat_ids_unicode_and_cache(settings):
    engine = FakeParler(settings)
    ctx = context(settings, engine)
    before = ctx.lesson.model_dump(mode="json")
    run_voice(ctx)
    expected = [f"{s.id}.intro" for s in ctx.lesson.scenes if s.narration]
    assert {c.beat_id for c in ctx.clips} >= set(expected)
    assert ctx.voice.engine == "parler" and ctx.voice.voice_id == "Anu"
    assert ctx.lesson.model_dump(mode="json") == before
    assert all(len(read_clip(c.path)) == c.samples for c in ctx.clips)
    assert all(c.narration == ctx.lesson.scenes[int(c.scene_id[1:])-1].narration if c.step_index is None
               else c.narration == ctx.lesson.scenes[int(c.scene_id[1:])-1].steps[c.step_index].narration for c in ctx.clips)
    count = engine.calls
    again = context(settings, engine)
    run_voice(again)
    assert all(c.cached for c in again.clips) and engine.calls == count


@pytest.mark.parametrize("damage", ["silent", "garbage", "manifest"])
def test_corrupt_cache_never_reports_success(settings, monkeypatch, damage):
    engine = FakeParler(settings)
    ctx = context(settings, engine)
    run_voice(ctx)
    path = ctx.clips[0].path
    if damage == "silent":
        from backend.app.speech.audio import write_wav
        write_wav(path, np.zeros(2400, dtype=np.float32))
    elif damage == "garbage":
        path.write_bytes(b"not-a-wave")
    else:
        path.with_suffix(".kn.json").write_text("{}")
    with pytest.raises(PipelineError) as exc:
        run_voice(context(settings, engine))
    assert exc.value.code == "tts_cache_invalid"


def test_cache_isolation_model_voice_speed_canonical_language(settings, monkeypatch):
    from backend.app.speech import parler_engine
    monkeypatch.setattr(parler_engine, "ffmpeg_run", lambda executable, arguments, data: data)
    engine = FakeParler(settings)
    first = context(settings, engine)
    run_voice(first)
    keys = {first.clips[0].cache_key}
    for gender, speed in (("male", 1.0), ("female", 0.85)):
        ctx = context(settings, engine, gender=gender, speed=speed)
        run_voice(ctx)
        keys.add(ctx.clips[0].cache_key)
    engine._version = "changed-model-version"
    ctx = context(settings, engine)
    run_voice(ctx)
    keys.add(ctx.clips[0].cache_key)
    other = lesson().model_copy(update={"lesson_id": "123abc456def"})
    ctx = context(settings, engine, localized=other)
    run_voice(ctx)
    keys.add(ctx.clips[0].cache_key)
    assert len(keys) == 5
    assert all("kn" == c.language for c in (first, ctx))


def test_low_ram_releases_after_cache_publication(settings):
    settings = settings.model_copy(update={"low_ram": True})
    engine = FakeParler(settings)
    ctx = context(settings, engine)
    run_voice(ctx)
    assert not engine.ready and ctx.clips
    assert all(c.path.with_suffix(".kn.json").is_file() for c in ctx.clips)


def test_speech_only_normalization_preserves_technical_content():
    text = "Python ನಲ್ಲಿ `range(3)` ಮತ್ತು print() while i = 0, m/s²."
    normalized = normalize_kannada(text)
    assert "Python" in normalized and "range 3" in normalized and "m/s²" in normalized
    assert text == "Python ನಲ್ಲಿ `range(3)` ಮತ್ತು print() while i = 0, m/s²."


def test_kn_approval_and_disabled_engine_policy(settings):
    for approved, enabled, expected in (("en,hi", True, False), ("en,hi,kn", True, True), ("en,hi,kn", False, False)):
        config = settings.model_copy(update={"approved_languages": tuple(approved.split(",")), "enable_parler": enabled, "parler_seed": 21, "parler_max_new_tokens": 1500})
        with TestClient(create_app(config)) as client:
            options = {x["code"]: x["available"] for x in client.get("/api/config").json()["languages"]}
            assert options["hi"] and options["kn"] == expected
            if not expected:
                response = client.post("/api/lessons", json={"topic": "Water Cycle", "language": "kn"})
                assert response.status_code == 422


def test_health_is_lazy_and_tracks_real_instance_state(settings):
    engine = get_parler_engine(settings)
    with TestClient(create_app(settings, replace(pipeline_ops.production_ops(settings=settings), precheck=None))) as client:
        health = client.get("/api/health").json()["models"]["tts_parler"]
        assert health == {"ready": False, "enabled": True}
        engine._model = object()
        try:
            assert client.get("/api/health").json()["models"]["tts_parler"]["ready"]
        finally:
            release_parler(settings)
        assert not parler_ready(settings)


def test_real_pipeline_kn_preview_from_cached_plan_and_translation(settings, monkeypatch):
    def wait(client, job_id):
        deadline = time.monotonic()+15
        while time.monotonic() < deadline:
            job = client.get(f"/api/jobs/{job_id}").json()
            if job["status"] in {"done", "error"}:
                return job
            time.sleep(0.02)
        pytest.fail(f"Synthetic voice + real timeline job timed out: {job}")
    config = settings.model_copy(update={"approved_languages": ("en", "hi", "kn"), "parler_seed": 21, "parler_max_new_tokens": 1500})
    cache = Cache(config.cache_dir)
    key = "c1f63f0ed69b"
    canonical = Lesson.model_validate_json((ROOT / "data/samples/planner/water_cycle.json").read_text(encoding="utf-8"))
    cache.write_json(cache.lesson_dir(key)/"plan.json", canonical.model_dump(mode="json", exclude_unset=True))
    # Transfer validated cached Kannada localization, not a relabelled English fixture.
    from backend.app.localize.translate import fingerprint
    folder = cache.lesson_dir(key, "kn-male-1")
    payload = json.loads((ROOT / "data/samples/localized/water_cycle.kn.localization.json").read_text(encoding="utf-8"))
    payload["metadata"]["variant"] = "kn-male-1"  # same validated translation; explicit test-only voice variant
    cache.write_json(folder/"lesson.json", payload["lesson"])
    cache.write_json(folder/"localization.json", {"metadata": payload["metadata"], "result": payload, "sha256": fingerprint(payload)})
    engine = FakeParler(config)
    engine.duration = 2.0  # enough frames for the real long-caption chunker
    monkeypatch.setattr(pipeline_ops, "get_parler_engine", lambda settings: engine)
    def no_plan_http(*a, **k):
        pytest.fail("Canonical English cache must prevent Ollama calls")
    monkeypatch.setattr(ollama_client.httpx, "Client", no_plan_http)
    from backend.app.localize.model import IndicTranslator
    monkeypatch.setattr(IndicTranslator, "translate", lambda *a, **k: pytest.fail("Kannada cache must prevent translation inference"))
    ops = replace(pipeline_ops.production_ops(settings=config), export=lambda run: run.skip("test no-MP4"))
    with TestClient(create_app(config, ops)) as client:
        submitted = client.post("/api/lessons", json={"topic": "Water Cycle", "subject": "science", "language": "kn", "voice": "male"})
        assert submitted.status_code == 202
        job = wait(client, submitted.json()["job_id"])
        assert job["status"] == "done", json.dumps(job, ensure_ascii=False)
        assert job["preview_ready"] and job["export_status"] == "skipped" and job["lesson_id"] == key
        assert job["stages"][0]["status"] == job["stages"][2]["status"] == "cached"
        response = client.get(f"/api/lessons/{key}?variant=kn-male-1").json()
        props = RenderProps(lesson=response["lesson"], timeline=response["timeline"])
        assert props.lesson.language == "kn" and props.timeline.voice.engine == "parler"
        assert props.timeline.audio is not None and response["media"]["mp4"] is None
        for scene, timing in zip(props.lesson.scenes, props.timeline.scenes):
            assert scene.id == timing.scene_id
            for beat in timing.beats:
                assert all(beat.start_frame <= c.start_frame < c.end_frame <= beat.end_frame for c in beat.captions)
        srt = client.get(response["media"]["srt"])
        assert srt.status_code == 200 and srt.text.splitlines() == render_srt(props.timeline).splitlines()
        assert client.get(response["media"]["audio_wav"]).content


def test_structured_synthesis_failure(settings, monkeypatch):
    engine = FakeParler(settings)
    monkeypatch.setattr(engine, "_generate", lambda *a: (_ for _ in ()).throw(RuntimeError("decoder failed")))
    with pytest.raises(PipelineError) as exc:
        run_voice(context(settings, engine))
    assert exc.value.code == "tts_failed"


def test_generation_and_normalization_versions_invalidate_cache(settings, monkeypatch, tmp_path):
    from backend.app.speech import parler_engine
    root, desc = tmp_path/"weights", tmp_path/"description"
    root.mkdir()
    desc.mkdir()
    for name in ("config.json", "generation_config.json", "model.safetensors", "tokenizer.json", "tokenizer.model",
                 "tokenizer_config.json", "special_tokens_map.json"):
        (root/name).write_bytes(b"test-local-asset")
    for name in ("tokenizer.json", "spiece.model", "tokenizer_config.json", "special_tokens_map.json"):
        (desc/name).write_bytes(b"test-description-asset")
    config = settings.model_copy(update={"parler_model":root,"parler_description_tokenizer":desc})
    engine = ParlerEngine(config)
    original = engine.engine_version
    assert not engine.ready  # hashing provenance never initializes a model
    assert ParlerEngine(config.model_copy(update={"parler_seed":8})).engine_version != original
    assert ParlerEngine(config.model_copy(update={"parler_max_new_tokens":2500})).engine_version != original
    monkeypatch.setattr(parler_engine, "KN_NORMALIZATION_VERSION", "kn-speech-new")
    assert ParlerEngine(config).engine_version != original


def test_speed_is_applied_to_audio_not_only_prompt(settings):
    engine = FakeParler(settings)
    engine.duration = 1.0
    normal, rate = engine.synthesize("ನೀರು", "kn", "Anu", 1.0)
    slower, slow_rate = engine.synthesize("ನೀರು", "kn", "Anu", 0.85)
    assert rate == slow_rate == 24000 and len(slower) > len(normal)
    assert abs(len(slower)/rate - len(normal)/rate/0.85) < 0.12


def test_low_ram_releases_on_synthesis_failure(settings, monkeypatch):
    engine = FakeParler(settings.model_copy(update={"low_ram":True}))
    engine.load()
    monkeypatch.setattr(engine, "_generate", lambda *a: (_ for _ in ()).throw(RuntimeError("decoder failed")))
    with pytest.raises(PipelineError):
        run_voice(context(engine.settings, engine))
    assert not engine.ready
