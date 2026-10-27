"""M0b compatibility: real planner cache and orchestration; model calls are mocked."""
from __future__ import annotations

import json
from pathlib import Path

import httpx
import numpy as np
import pytest

from backend.app import orchestrator as orchestration, pipeline_ops
from backend.app.cache import Cache, plan_key, variant_key
from backend.app.config import ROOT, Settings
from backend.app.contracts import LessonRequest
from backend.app.jobs import JobContext, JobRecord
from backend.app.orchestrator import Orchestrator, PipelineRun
from backend.app.planner import ollama_client as planner
from backend.app.planner.ollama_client import PlanRequest, lesson_key
from backend.app.planner.prompt import PROMPT_VERSION
from backend.app.planner.schema import Lesson
from backend.app.planner.validate import validate_plan
from backend.app.speech import engines as speech
from backend.app.speech.engines import NarrationContext, run_voice
from backend.app.speech.kokoro_engine import KokoroEngine

MODEL = "qwen3:4b-instruct-2507-q4_K_M"
LEGACY_ID = "c1f63f0ed69b"


@pytest.fixture
def environment(tmp_path):
    settings = Settings(device="cpu", cache_dir=tmp_path / "cache")
    cache = Cache(settings.cache_dir)
    return Orchestrator(settings, cache, "cpu", pipeline_ops.production_ops())


def request_for(**changes) -> LessonRequest:
    return LessonRequest.model_validate({"topic": "Water Cycle", "subject": "science", **changes})


def make_run(environment: Orchestrator, request: LessonRequest) -> PipelineRun:
    job = JobRecord(lesson_id=environment.lesson_id_for(request),
                    variant=variant_key(request.language, request.voice, request.speed), device_profile="cpu")
    ctx = JobContext(job=job, language=request.language, request=request)
    return PipelineRun(environment, ctx, environment.settings, environment.cache)


def cached_plan(environment: Orchestrator) -> tuple[Path, Lesson]:
    lesson = Lesson.model_validate_json((ROOT / "data/samples/planner/water_cycle.json").read_text(encoding="utf-8"))
    assert lesson.lesson_id == LEGACY_ID
    assert lesson.model == MODEL and lesson.prompt_version == PROMPT_VERSION
    validate_plan(lesson, "science")
    path = environment.cache.lesson_dir(LEGACY_ID) / "plan.json"
    environment.cache.write_json(path, lesson.model_dump(mode="json", exclude_unset=True))
    return path, lesson


def test_existing_english_id_is_unchanged(environment):
    assert lesson_key(PlanRequest(topic="Water Cycle", subject="science"), MODEL) == LEGACY_ID
    assert environment.lesson_id_for(request_for()) == LEGACY_ID


@pytest.mark.parametrize("language", ["en", "hi", "kn"])
def test_planning_key_receives_english_request(environment, monkeypatch, language):
    """Regression: key equality alone missed a noncanonical planning request."""
    seen = []
    original = orchestration.lesson_key

    def record(request, model):
        seen.append(request.language)
        return original(request, model)

    monkeypatch.setattr(orchestration, "lesson_key", record)
    assert environment.lesson_id_for(request_for(language=language)) == LEGACY_ID
    assert seen == ["en"]


@pytest.mark.parametrize("language", ["en", "hi", "kn"])
def test_production_plan_reuses_unchanged_english_cache(environment, monkeypatch, language):
    path, expected = cached_plan(environment)
    before, modified = path.read_bytes(), path.stat().st_mtime_ns
    requests = []
    original = planner.plan_lesson

    def no_network(*args, **kwargs):
        pytest.fail("A valid canonical plan must require zero Ollama HTTP calls")

    def record(request, settings):
        requests.append(request.language)
        return original(request, settings)

    monkeypatch.setattr(planner.httpx, "Client", no_network)
    monkeypatch.setattr(pipeline_ops, "plan_lesson", record)
    run = make_run(environment, request_for(language=language))
    environment._execute("plan", run)
    environment._execute("validate", run)
    assert requests == ["en"]
    assert run.lesson == expected
    assert run.lesson_id == run.lesson.lesson_id == LEGACY_ID
    assert run.language == language and run.request.language == language
    assert run.folder == environment.cache.lesson_dir(LEGACY_ID, f"{language}-female-1")
    assert run.ctx.job.stages[0].status == "cached"
    assert path.read_bytes() == before and path.stat().st_mtime_ns == modified


@pytest.mark.parametrize("changes", [
    {"topic": "Photosynthesis"}, {"level": "intermediate"}, {"target_seconds": 45},
    {"subject": "other"}, {"subject": "programming"},
])
def test_planning_inputs_remain_isolated(environment, changes):
    assert environment.lesson_id_for(request_for(**changes)) != LEGACY_ID


def test_model_prompt_and_schema_components_remain_isolated(environment, monkeypatch):
    request = PlanRequest(topic="Water Cycle", subject="science")
    other = Orchestrator(environment.settings.model_copy(update={"planner_model_cpu": "another-local-model"}),
                         environment.cache, "cpu", environment.ops)
    assert other.lesson_id_for(request_for()) != LEGACY_ID
    monkeypatch.setattr(planner, "PROMPT_VERSION", PROMPT_VERSION + "-test")
    assert environment.lesson_id_for(request_for()) != LEGACY_ID
    # The existing schema component is fixed at 1.0 by lesson_key; no schema bump here.
    assert plan_key(request.topic, request.level, request.target_seconds, MODEL,
                    f"{PROMPT_VERSION}:science", "1.1") != LEGACY_ID


def test_effective_subject_and_variants_share_the_plan(environment):
    assert environment.lesson_id_for(request_for(subject=None)) == LEGACY_ID
    folders = set()
    for language in ("en", "hi", "kn"):
        for voice in ("female", "male"):
            for speed in (0.85, 1.0, 1.15):
                run = make_run(environment, request_for(language=language, voice=voice, speed=speed))
                assert run.lesson_id == LEGACY_ID
                folders.add(run.folder)
    assert len(folders) == 18


def test_second_language_after_generation_uses_zero_fresh_inference(environment, monkeypatch):
    sample = json.loads((ROOT / "data/samples/planner/water_cycle.json").read_text(encoding="utf-8"))
    content = {key: sample[key] for key in ("title", "subject", "keep_terms", "scenes")}
    content["title_card"] = content["scenes"].pop(0)
    calls = []

    def reply(request):
        calls.append(request.url.path)
        if request.url.path == "/api/show":
            return httpx.Response(200, json={"capabilities": ["completion"]})
        assert request.url.path == "/api/chat"
        return httpx.Response(200, json={"done": True, "message": {"content": json.dumps(content)}})

    def plan(request, settings):
        return planner.plan_lesson(request, settings, transport=httpx.MockTransport(reply),
                                   debug_dir=settings.cache_dir / "debug")

    monkeypatch.setattr(pipeline_ops, "plan_lesson", plan)
    english = make_run(environment, request_for())
    environment._execute("plan", english)
    assert calls == ["/api/show", "/api/chat"]
    path = environment.cache.lesson_dir(LEGACY_ID) / "plan.json"
    before = path.read_bytes()
    for language in ("hi", "kn"):
        run = make_run(environment, request_for(language=language))
        environment._execute("plan", run)
        assert run.lesson == english.lesson
        assert run.lesson_id == LEGACY_ID
        assert run.ctx.job.stages[0].status == "cached"
    assert calls == ["/api/show", "/api/chat"]
    assert path.read_bytes() == before


def test_localized_hindi_narration_passes_real_identity_checks(environment, monkeypatch):
    _, english = cached_plan(environment)
    run = make_run(environment, request_for(language="hi", voice="male", speed=0.85))
    localized = english.model_copy(deep=True, update={"language": "hi"})
    for scene in localized.scenes:
        if scene.narration:
            scene.narration = "यह एक उदाहरण है।"
        for step in scene.steps:
            step.narration = "यह एक उदाहरण है।"
    localized = Lesson.model_validate(localized.model_dump(mode="json", exclude_unset=True))

    class FakeKokoro(KokoroEngine):
        @property
        def engine_version(self):
            return "identity-test-no-model"

        def synthesize(self, text, language, voice_id, speed):
            assert language == "hi" and voice_id == "hm_omega" and speed == 0.85
            return np.ones(240, dtype=np.float32) * 0.1, 24000

    monkeypatch.setattr(speech, "process_audio", lambda audio, rate, ffmpeg: audio)
    ctx = NarrationContext(job=run.ctx.job, language=run.language, request=run.request,
                           lesson=localized, settings=run.settings, cache=run.cache,
                           engine=FakeKokoro(run.settings), gender=run.request.voice, speed=run.request.speed)
    run_voice(ctx)
    assert ctx.clips and ctx.job.lesson_id == ctx.lesson.lesson_id == run.lesson_id == LEGACY_ID
    assert ctx.job.variant == "hi-male-0.85"
    assert ctx.lesson.language == "hi" and english.language == "en"
