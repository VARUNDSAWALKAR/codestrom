"""Task 5B: production PipelineOps bridge. The underlying functions (plan_lesson, Kokoro, run_voice,
run_timeline, run_export, the Ollama unload/probe calls) are mocked; the bridge, orchestrator, runner and
API are real. No Ollama, TTS model or renderer is touched."""
from __future__ import annotations

import tempfile
import time
import unittest
from contextlib import ExitStack
from dataclasses import replace
from pathlib import Path
from threading import Event
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient

from backend.app import mock_pipeline, pipeline_ops
from backend.app.config import Settings
from backend.app.main import create_app
from backend.app.orchestrator import PipelineOps
from backend.app.planner.ollama_client import PlanRequest, PlanResult, PlanError, lesson_key
from backend.app.planner.prompt import PROMPT_VERSION
from backend.app.speech.kokoro_engine import KokoroEngine
from backend.app.config import ROOT
from backend.app.planner.schema import Lesson
from backend.app.timeline.schema import AudioURLs, Beat, Caption, RenderProps, SceneTiming, Timeline, Voice
from backend.app.timeline.srt import render_srt

BODY = {"topic": "Water Cycle", "level": "beginner", "language": "en", "target_seconds": 60,
        "subject": "science", "voice": "female", "speed": 1.0}
MODEL = "qwen3:4b-instruct-2507-q4_K_M"


def fixture_lesson(request: PlanRequest, key: str) -> Lesson:
    """A real validated planner output (Task 4 sample), re-keyed for the request."""
    sample = Lesson.model_validate_json((ROOT / "data/samples/planner/water_cycle.json").read_text(encoding="utf-8"))
    return sample.model_copy(update={"lesson_id": key, "model": MODEL, "prompt_version": PROMPT_VERSION,
                                     "topic": request.topic, "level": request.level,
                                     "target_seconds": request.target_seconds})


def synthetic_timeline(lesson: Lesson, variant: str) -> Timeline:
    """Contiguous 1-second beats in the shape run_timeline produces (30 fps, with audio URLs)."""
    frame, scenes = 0, []
    for scene in lesson.scenes:
        start, beats = frame, []
        for index in ([None] if scene.narration.strip() else []) + list(range(len(scene.steps))):
            suffix = "intro" if index is None else f"step{index}"
            beats.append(Beat(beat_id=f"{scene.id}.{suffix}", step_index=index, start_frame=frame, end_frame=frame + 30,
                              captions=[Caption(text="caption", start_frame=frame, end_frame=frame + 30)]))
            frame += 30
        scenes.append(SceneTiming(scene_id=scene.id, type=scene.type, start_frame=start,
                                  duration_frames=frame - start, beats=beats))
    prefix = f"/media/{lesson.lesson_id}/{variant}"
    return Timeline(lesson_id=lesson.lesson_id, language=lesson.language, variant=variant, duration_frames=frame,
                    audio=AudioURLs(web=f"{prefix}/narration.m4a", wav=f"{prefix}/narration.wav"),
                    voice=Voice(engine="kokoro", voice_id="hf_alpha", speed=1.0), scenes=scenes)


class Harness(unittest.TestCase):
    """Patches the stage functions with recording fakes that write real, schema-valid artifacts."""

    low_ram = False

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.settings = Settings(device="cpu", cache_dir=Path(self.temp.name) / "cache", low_ram=self.low_ram)
        self.events: list[str] = []
        self.plan_requests: list[PlanRequest] = []
        self.engines: list[object] = []
        self.loads = 0
        self.errors: dict[str, Exception] = {}
        self.seen: set[tuple[str, str]] = set()
        self.plan_result_override = None
        self.export_gate: Event | None = None
        self.mp4_valid = True
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        for name in ("plan_lesson", "run_voice", "run_timeline", "run_export", "unload_planner",
                     "ollama_has_model", "export_complete"):
            self.stack.enter_context(patch.object(pipeline_ops, name, getattr(self, "fake_" + name)))
        harness = self

        def load(engine: KokoroEngine) -> None:  # a plain function so it binds like the real method
            harness.fake_load(engine)

        self.stack.enter_context(patch.object(KokoroEngine, "load", load))
        self.stack.enter_context(patch.object(pipeline_ops, "PROGRESS_INTERVAL", 0.01))
        self.stack.enter_context(patch.object(pipeline_ops, "PROBE_TTL", 0))
        self.client = TestClient(create_app(self.settings))
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)

    # ---- fakes ---------------------------------------------------------------------------
    def fake_plan_lesson(self, request: PlanRequest, settings: Settings) -> PlanResult:
        self.events.append("plan")
        self.plan_requests.append(request)
        if "plan" in self.errors:
            raise self.errors["plan"]
        if self.plan_result_override is not None:
            return self.plan_result_override
        key = lesson_key(request, settings.planner_model("cpu"))
        cached = ("plan", key) in self.seen
        self.seen.add(("plan", key))
        return PlanResult(request=request, model=MODEL, lesson=fixture_lesson(request, key), attempts=0 if cached else 1,
                          generation_seconds=0.0, cached=cached)

    def fake_run_voice(self, ctx):
        self.events.append("voice")
        self.engines.append(ctx.engine)
        ctx.engine.load()  # what the first uncached beat does
        if "voice" in self.errors:
            raise self.errors["voice"]
        key = ("voice", ctx.job.lesson_id)
        stage = next(s for s in ctx.job.stages if s.name == "voice")
        stage.status = "cached" if key in self.seen else "done"
        self.seen.add(key)
        return ctx

    def fake_load(self, engine: KokoroEngine) -> None:
        if getattr(engine, "_model", None) is None:
            self.loads += 1
            engine._model = object()

    def fake_run_timeline(self, ctx):
        self.events.append("timeline")
        if "timeline" in self.errors:
            raise self.errors["timeline"]
        folder = ctx.cache.lesson_dir(ctx.lesson.lesson_id, ctx.job.variant)
        folder.mkdir(parents=True, exist_ok=True)
        timeline = synthetic_timeline(ctx.lesson, ctx.job.variant)
        props = RenderProps(lesson=ctx.lesson, timeline=timeline)
        for name, value in (("lesson.json", props.lesson), ("timeline.json", timeline), ("props.json", props)):
            ctx.cache.write_json(folder / name, value)
        (folder / "lesson.srt").write_text(render_srt(timeline), encoding="utf-8")
        (folder / "narration.wav").write_bytes(b"RIFF....WAVE")
        if not getattr(self, "skip_m4a", False):
            (folder / "narration.m4a").write_bytes(b"m4a")
        ctx.job.playable = True  # the real run_timeline does this itself
        stage = next(s for s in ctx.job.stages if s.name == "timeline")
        key = ("timeline", ctx.job.lesson_id)
        stage.status = "cached" if key in self.seen else "done"
        self.seen.add(key)
        return ctx

    def fake_run_export(self, ctx):
        self.events.append("export")
        if self.export_gate is not None:
            ctx.job.progress = 0.4
            self.export_entered.set()
            self.export_gate.wait(10)
        if "export" in self.errors:
            raise self.errors["export"]
        folder = ctx.cache.lesson_dir(ctx.job.lesson_id, ctx.job.variant)
        (folder / "lesson.mp4").write_bytes(b"fake mp4")
        stage = next(s for s in ctx.job.stages if s.name == "export")
        key = ("export", ctx.job.lesson_id)
        stage.status = "cached" if key in self.seen else "done"
        self.seen.add(key)
        ctx.job.progress = 1.0
        return ctx

    def fake_unload_planner(self, settings: Settings, model: str, transport=None) -> None:
        self.events.append("unload")
        self.unloaded = getattr(self, "unloaded", []) + [model]
        if "unload" in self.errors:
            raise self.errors["unload"]

    def fake_ollama_has_model(self, settings: Settings, model: str, transport=None) -> bool:
        return getattr(self, "ollama_models", ()) and model in self.ollama_models

    def fake_export_complete(self, folder: Path, settings: Settings) -> bool:
        return self.mp4_valid and (folder / "lesson.mp4").is_file()

    # ---- helpers -------------------------------------------------------------------------
    def post(self, **changes: object) -> dict:
        response = self.client.post("/api/lessons", json={**BODY, **changes})
        self.assertEqual(response.status_code, 202, response.text)
        return response.json()

    def wait(self, job_id: str, predicate=lambda job: job["status"] in {"done", "error"}) -> dict:
        deadline = time.monotonic() + 10
        job: dict = {}
        while time.monotonic() < deadline:
            job = self.client.get(f"/api/jobs/{job_id}").json()
            if predicate(job):
                return job
            time.sleep(0.02)
        self.fail(f"Job did not reach the expected state: {job}")

    def run_job(self, **changes: object) -> tuple[dict, dict]:
        accepted = self.post(**changes)
        return accepted, self.wait(accepted["job_id"])

    def assert_failed(self, job: dict, stage: str, code: str) -> None:
        self.assertEqual(job["status"], "error")
        self.assertEqual((job["error_detail"]["stage"], job["error_detail"]["code"]), (stage, code))
        self.assertFalse(job["fallback"])


class SelectionAndLanguageTests(Harness):
    def test_production_is_default_and_independent_of_mock(self) -> None:
        ops = self.client.app.state.orchestrator.ops
        self.assertFalse(ops.mock)
        self.assertIs(ops.plan, pipeline_ops.plan)
        self.assertIsNotNone(ops.export_complete)
        health = self.client.get("/api/health").json()
        self.assertFalse(health["mock_pipeline"])

    def test_injected_ops_and_mock_mode_override_production(self) -> None:
        injected = replace(mock_pipeline.build_mock_ops(), mock=False, precheck=None)
        with patch.object(pipeline_ops, "production_ops", side_effect=AssertionError("production must not be built")), \
                patch("backend.app.main.production_ops", side_effect=AssertionError("production must not be built")):
            with TestClient(create_app(self.settings, injected)) as client:
                self.assertIs(client.app.state.orchestrator.ops, injected)
            mock_settings = Settings.model_validate({**self.settings.model_dump(), "mock_pipeline": True})
            with TestClient(create_app(mock_settings)) as client:
                self.assertTrue(client.app.state.orchestrator.ops.mock)
                self.assertTrue(client.get("/api/health").json()["mock_pipeline"])
                hindi = client.post("/api/lessons", json={"topic": "Water Cycle", "language": "hi"})
                self.assertEqual(hindi.status_code, 202)  # mock keeps its labelled hi/kn behaviour
                self.assertTrue(hindi.json()["mock"])

    def test_production_is_english_only(self) -> None:
        for language in ("hi", "kn", "ta", "te", "bn", "mr"):
            with self.subTest(language=language):
                response = self.client.post("/api/lessons", json={**BODY, "language": language})
                self.assertEqual(response.status_code, 422)
                self.assertEqual(response.json()["error"]["code"], "language_unavailable")
        hindi = self.client.post("/api/lessons", json={**BODY, "language": "kn"}).json()["error"]["message"]
        self.assertIn("Hindi/Kannada need translation and voice integration that is not connected yet", hindi)
        self.assertEqual(self.events, [])  # rejected before any job ran

    def test_localize_refuses_instead_of_relabelling(self) -> None:
        run = type("Run", (), {})()
        with self.assertRaises(pipeline_ops.PipelineError) as raised:
            pipeline_ops.localize(run)
        self.assertEqual(raised.exception.code, "localize_unavailable")


class PlanAndIdentityTests(Harness):
    def test_planner_receives_request_and_lesson_id_matches_job(self) -> None:
        accepted, job = self.run_job(level="intermediate", target_seconds=45)
        self.assertEqual(job["status"], "done", job)
        request = self.plan_requests[0]
        self.assertEqual((request.topic, request.level, request.language, request.target_seconds, request.subject),
                         ("Water Cycle", "intermediate", "en", 45, "science"))
        self.assertEqual(accepted["lesson_id"], lesson_key(request, MODEL))
        lesson = self.client.get(f"/api/lessons/{accepted['lesson_id']}").json()
        self.assertEqual(lesson["lesson"]["lesson_id"], accepted["lesson_id"])
        self.assertEqual(self.events.count("plan"), 1)  # validate made no second planner/Ollama call

    def test_lesson_id_mismatch_is_diagnosed_not_overwritten(self) -> None:
        def wrong(request: PlanRequest, settings: Settings) -> PlanResult:
            return PlanResult(request=request, model=MODEL, lesson=fixture_lesson(request, "0" * 12))

        with patch.object(pipeline_ops, "plan_lesson", wrong):
            accepted, job = self.run_job()
        self.assert_failed(job, "plan", "plan_invalid")
        self.assertEqual(self.client.get(f"/api/lessons/{accepted['lesson_id']}").status_code, 404)

    def test_planner_errors_keep_their_codes_and_no_fallback_appears(self) -> None:
        for code in ("validation_failed", "timeout", "unavailable", "ollama_rejected"):
            with self.subTest(code=code):
                self.plan_result_override = PlanResult(request=PlanRequest(topic="Water Cycle"), model=MODEL,
                                                       error=PlanError(code=code, message=f"{code} detail"))
                accepted, job = self.run_job(topic=f"Water Cycle {code}")
                self.assert_failed(job, "plan", code)
                self.assertEqual(job["error_detail"]["message"], f"{code} detail")
                self.assertEqual([s["status"] for s in job["stages"][1:]], ["pending"] * 5)
        lessons = self.settings.cache_dir / "lessons"
        self.assertFalse((lessons / "fallback-python-loop").exists())
        self.assertNotIn("voice", self.events)


class VoiceTests(Harness):
    def test_kokoro_loads_lazily_and_is_reused(self) -> None:
        self.assertEqual(self.loads, 0)  # app start and health do not load it
        self.assertFalse(self.client.get("/api/health").json()["models"]["tts_kokoro"]["ready"])
        _, first = self.run_job()
        _, second = self.run_job(topic="Water Cycle Basics")
        self.assertEqual((first["status"], second["status"]), ("done", "done"))
        self.assertEqual(self.loads, 1)
        self.assertEqual(len(self.engines), 2)
        self.assertIs(self.engines[0], self.engines[1])

    def test_errors_map_to_stage_codes(self) -> None:
        cases = (("voice", RuntimeError("synthesis exploded"), "voice", "tts_failed"),
                 ("timeline", ValueError("bad clip lengths"), "timeline", "timeline_failed"),
                 ("export", RuntimeError("renderer exit 1"), "export", "export_failed"))
        for key, error, stage, code in cases:
            with self.subTest(code=code):
                self.errors = {key: error}
                _, job = self.run_job(topic=f"Water Cycle {code}")
                self.assert_failed(job, stage, code)
                self.assertIn(str(error), job["error_detail"]["message"])

    def test_health_readiness_follows_real_events(self) -> None:
        self.ollama_models = ()
        models = lambda: self.client.get("/api/health").json()["models"]  # noqa: E731
        self.assertFalse(models()["planner"]["ready"])  # Ollama does not list the model
        self.ollama_models = (MODEL,)
        self.assertTrue(models()["planner"]["ready"])
        self.assertFalse(models()["tts_kokoro"]["ready"])
        self.run_job()
        health = self.client.get("/api/health").json()
        self.assertTrue(health["models"]["tts_kokoro"]["ready"])
        self.assertFalse(health["models"]["translator"]["ready"])
        self.assertFalse(health["ok"])  # translator is not built yet


class PreviewTests(Harness):
    def test_preview_before_export_and_export_failure_keeps_it(self) -> None:
        self.export_gate, self.export_entered = Event(), Event()
        self.errors = {"export": RuntimeError("renderer exit 1")}
        accepted = self.post()
        self.assertTrue(self.export_entered.wait(10))
        job = self.client.get(f"/api/jobs/{accepted['job_id']}").json()
        self.assertEqual((job["preview_ready"], job["playable"], job["export_status"]), (True, True, "running"))
        lesson = self.client.get(f"/api/lessons/{accepted['lesson_id']}").json()
        prefix = f"/media/{accepted['lesson_id']}/en-female-1"
        self.assertEqual(lesson["media"], {"audio_web": f"{prefix}/narration.m4a", "audio_wav": f"{prefix}/narration.wav",
                                           "mp4": None, "srt": f"{prefix}/lesson.srt"})
        self.assertEqual(lesson["export_status"], "running")
        self.export_gate.set()
        job = self.wait(accepted["job_id"])
        self.assert_failed(job, "export", "export_failed")
        self.assertTrue(job["preview_ready"] and job["playable"])
        self.assertEqual(job["export_status"], "failed")
        again = self.client.get(f"/api/lessons/{accepted['lesson_id']}")
        self.assertEqual((again.status_code, again.json()["preview_ready"]), (200, True))

    def test_failed_preview_check_leaves_playable_false(self) -> None:
        self.skip_m4a = True  # the fake timeline claims playable but a narration file is missing
        _, job = self.run_job()
        self.assert_failed(job, "timeline", "preview_incomplete")
        self.assertFalse(job["playable"] or job["preview_ready"])
        self.assertNotIn("export", self.events)

    def test_timeline_exception_leaves_playable_false(self) -> None:
        self.errors = {"timeline": RuntimeError("ffmpeg missing")}
        _, job = self.run_job()
        self.assert_failed(job, "timeline", "timeline_failed")
        self.assertFalse(job["playable"])


class CacheTests(Harness):
    def test_repeat_request_is_cached_and_fast(self) -> None:
        accepted, first = self.run_job()
        self.assertEqual(first["export_status"], "completed")
        started = time.monotonic()
        again = self.post()
        self.assertTrue(again["cached"])
        job = self.client.get(f"/api/jobs/{again['job_id']}").json()
        self.assertEqual({s["name"]: s["status"] for s in job["stages"]},
                         {"plan": "cached", "validate": "cached", "translate": "cached", "voice": "cached",
                          "timeline": "cached", "export": "cached"})
        self.assertLess(time.monotonic() - started, 1)
        self.assertEqual(self.events.count("plan"), 1)

    def test_damaged_mp4_is_not_a_cache_hit_and_stages_report_cached(self) -> None:
        accepted, _ = self.run_job()
        self.mp4_valid = False  # the exporter's props.sha1 / ffprobe check rejects the file
        again = self.post()
        self.assertFalse(again["cached"])
        job = self.wait(again["job_id"])
        self.assertEqual(job["status"], "done")
        by_name = {s["name"]: s["status"] for s in job["stages"]}
        self.assertEqual((by_name["plan"], by_name["voice"], by_name["timeline"], by_name["export"]),
                         ("cached", "cached", "cached", "cached"))
        lesson = self.client.get(f"/api/lessons/{accepted['lesson_id']}").json()
        self.assertEqual(lesson["export_status"], "pending" if lesson["media"]["mp4"] is None else "completed")

    def test_unverified_mp4_is_not_offered_as_media(self) -> None:
        accepted, _ = self.run_job()
        self.mp4_valid = False
        lesson = self.client.get(f"/api/lessons/{accepted['lesson_id']}").json()
        self.assertIsNone(lesson["media"]["mp4"])
        self.assertNotEqual(lesson["export_status"], "completed")

    def test_partial_preview_is_not_a_cache_hit(self) -> None:
        accepted, _ = self.run_job()
        folder = self.client.app.state.cache.lesson_dir(accepted["lesson_id"], accepted["variant"])
        (folder / "lesson.srt").unlink()
        self.assertFalse(self.post()["cached"])


class LowRamOnTests(Harness):
    low_ram = True

    def test_unload_runs_once_between_plan_and_voice(self) -> None:
        _, job = self.run_job()
        self.assertEqual(job["status"], "done")
        self.assertEqual(self.events[:3], ["plan", "unload", "voice"])
        self.assertEqual(self.events.count("unload"), 1)
        self.assertEqual(self.unloaded, [MODEL])

    def test_unload_failure_is_a_warning_not_a_failure(self) -> None:
        self.errors = {"unload": httpx.ConnectError("ollama went away")}
        _, job = self.run_job()
        self.assertEqual(job["status"], "done")
        self.assertTrue(any(w.startswith("LOW_RAM:") for w in job["warnings"]))


class LowRamOffTests(Harness):
    def test_no_unload_request_when_low_ram_is_off(self) -> None:
        _, job = self.run_job()
        self.assertEqual(job["status"], "done")
        self.assertNotIn("unload", self.events)


class RealHttpHelpersTests(unittest.TestCase):
    """The unload and probe helpers themselves, against a mock Ollama transport."""

    def test_unload_posts_keep_alive_zero_for_the_planner_model(self) -> None:
        import json
        seen: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            return httpx.Response(200, json={})

        settings = Settings(device="cpu")
        pipeline_ops.unload_planner(settings, MODEL, httpx.MockTransport(handler))
        self.assertEqual((seen[0].method, seen[0].url.path, json.loads(seen[0].content)),
                         ("POST", "/api/chat", {"model": MODEL, "keep_alive": 0}))

    def test_probe_requires_ollama_to_list_the_model(self) -> None:
        settings = Settings(device="cpu")

        def listing(*names: str):
            return httpx.MockTransport(lambda r: httpx.Response(200, json={"models": [{"name": n} for n in names]}))

        self.assertTrue(pipeline_ops.ollama_has_model(settings, MODEL, listing(MODEL, "llama3.2:3b")))
        self.assertFalse(pipeline_ops.ollama_has_model(settings, MODEL, listing("llama3.2:3b")))

        def down(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("refused")

        self.assertFalse(pipeline_ops.ollama_has_model(settings, MODEL, httpx.MockTransport(down)))


if __name__ == "__main__":
    unittest.main()
