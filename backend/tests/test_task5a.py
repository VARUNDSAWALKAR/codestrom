"""Task 5A: lesson API and job lifecycle with injected mock operations (no Ollama, TTS or renderer)."""
from __future__ import annotations

import tempfile
import time
import unittest
from dataclasses import replace
from pathlib import Path
from threading import Event

from fastapi.testclient import TestClient

from backend.app import mock_pipeline
from backend.app.config import Settings
from backend.app.jobs import PipelineError
from backend.app.main import create_app
from backend.app.orchestrator import PipelineOps, PipelineRun

BODY = {"topic": "Water Cycle", "level": "beginner", "language": "en", "target_seconds": 60,
        "voice": "female", "speed": 1.0}


def write_mp4(run: PipelineRun) -> None:
    (run.folder / "lesson.mp4").write_bytes(b"not a real mp4")


def fake_ops(**overrides: object) -> PipelineOps:
    """Fixture-backed operations that look like a real (non-mock) pipeline to the orchestrator."""
    return replace(mock_pipeline.build_mock_ops(), **{"mock": False, "precheck": None, "export": write_mp4, **overrides})


def failing(code: str, message: str):
    def run(_: PipelineRun) -> None:
        raise PipelineError(code, message)
    return run


class LessonApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.settings = Settings(device="cpu", cache_dir=Path(self.temp.name) / "cache", max_queued_jobs=1)

    def client(self, ops: PipelineOps | None = None, settings: Settings | None = None) -> TestClient:
        client = TestClient(create_app(settings or self.settings, ops))
        client.__enter__()
        self.addCleanup(client.__exit__, None, None, None)
        return client

    def post(self, client: TestClient, **changes: object) -> dict:
        response = client.post("/api/lessons", json={**BODY, **changes})
        self.assertEqual(response.status_code, 202, response.text)
        return response.json()

    def wait(self, client: TestClient, job_id: str, predicate=lambda job: job["status"] in {"done", "error"}) -> dict:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            job = client.get(f"/api/jobs/{job_id}").json()
            if predicate(job):
                return job
            time.sleep(0.02)
        self.fail(f"Job did not reach the expected state: {job}")

    # ---- happy path and response shapes -------------------------------------------------
    def test_create_poll_and_fetch_lesson(self) -> None:
        client = self.client(fake_ops())
        accepted = self.post(client)
        self.assertEqual(set(accepted), {"job_id", "lesson_id", "variant", "cached", "mock"})
        self.assertEqual((accepted["variant"], accepted["cached"], accepted["mock"]), ("en-female-1", False, False))
        job = self.wait(client, accepted["job_id"])
        self.assertEqual(job["status"], "done")
        self.assertEqual([s["name"] for s in job["stages"]],
                         ["plan", "validate", "translate", "voice", "timeline", "export"])
        self.assertEqual(job["stages"][2]["status"], "skipped")  # English needs no translation
        self.assertTrue(job["preview_ready"] and job["playable"])
        self.assertEqual((job["export_status"], job["fallback"], job["error"], job["error_detail"]),
                         ("completed", False, None, None))
        lesson = client.get(f"/api/lessons/{accepted['lesson_id']}").json()
        self.assertEqual((lesson["variant"], lesson["preview_ready"], lesson["export_status"], lesson["mock"]),
                         ("en-female-1", True, "completed", False))
        self.assertEqual(lesson["lesson"]["lesson_id"], accepted["lesson_id"])
        self.assertEqual(lesson["timeline"]["variant"], "en-female-1")
        media = f"/media/{accepted['lesson_id']}/en-female-1"
        self.assertEqual(lesson["media"], {"audio_web": None, "audio_wav": None,
                                           "mp4": f"{media}/lesson.mp4", "srt": f"{media}/lesson.srt"})
        self.assertEqual(lesson["meta"]["variants"], ["en-female-1"])
        self.assertEqual(client.get(f"{media}/lesson.srt").status_code, 200)

    def test_non_english_job_runs_translate_stage(self) -> None:
        client = self.client(fake_ops())
        accepted = self.post(client, language="hi")
        job = self.wait(client, accepted["job_id"])
        self.assertEqual(accepted["variant"], "hi-female-1")
        self.assertEqual(job["stages"][2]["status"], "done")

    def test_cached_variant_finishes_immediately(self) -> None:
        client = self.client(fake_ops())
        first = self.post(client)
        self.wait(client, first["job_id"])
        second = self.post(client)
        self.assertTrue(second["cached"])
        self.assertEqual(second["lesson_id"], first["lesson_id"])
        job = client.get(f"/api/jobs/{second['job_id']}").json()
        self.assertEqual((job["status"], job["export_status"], job["preview_ready"]), ("done", "completed", True))
        self.assertTrue(all(s["status"] == "cached" for s in job["stages"]))

    # ---- failure lifecycle --------------------------------------------------------------
    def assert_failed(self, client: TestClient, job_id: str, stage: str, code: str) -> dict:
        job = self.wait(client, job_id)
        self.assertEqual(job["status"], "error")
        self.assertFalse(job["fallback"])  # no silent substitute lesson
        self.assertEqual(job["error_detail"]["stage"], stage)
        self.assertEqual(job["error_detail"]["code"], code)
        self.assertEqual(job["error"], job["error_detail"]["message"])
        by_name = {s["name"]: s for s in job["stages"]}
        self.assertEqual(by_name[stage]["status"], "error")
        return job

    def test_planner_failure_preserves_structured_error(self) -> None:
        client = self.client(fake_ops(plan=failing("validation_failed", "Narration has 261 words; require 90-180")))
        accepted = self.post(client)
        job = self.assert_failed(client, accepted["job_id"], "plan", "validation_failed")
        self.assertIn("261 words", job["error_detail"]["message"])
        self.assertEqual([s["status"] for s in job["stages"][1:]], ["pending"] * 5)
        self.assertFalse(job["preview_ready"] or job["playable"])
        self.assertEqual(client.get(f"/api/lessons/{accepted['lesson_id']}").status_code, 404)

    def test_voice_failure_marks_job_failed(self) -> None:
        client = self.client(fake_ops(voice=failing("tts_failed", "Kokoro could not synthesize")))
        job = self.assert_failed(client, self.post(client)["job_id"], "voice", "tts_failed")
        self.assertFalse(job["preview_ready"])

    def test_timeline_failure_marks_job_failed(self) -> None:
        client = self.client(fake_ops(timeline=failing("timeline_failed", "Clip measurement failed")))
        accepted = self.post(client)
        job = self.assert_failed(client, accepted["job_id"], "timeline", "timeline_failed")
        self.assertFalse(job["preview_ready"] or job["playable"])
        self.assertEqual(client.get(f"/api/lessons/{accepted['lesson_id']}").status_code, 404)

    def test_export_failure_keeps_preview_usable(self) -> None:
        client = self.client(fake_ops(export=failing("render_failed", "Renderer exited 1")))
        accepted = self.post(client)
        job = self.assert_failed(client, accepted["job_id"], "export", "render_failed")
        self.assertTrue(job["preview_ready"] and job["playable"])
        self.assertEqual(job["export_status"], "failed")
        response = client.get(f"/api/lessons/{accepted['lesson_id']}")
        self.assertEqual(response.status_code, 200)
        lesson = response.json()
        self.assertEqual((lesson["preview_ready"], lesson["export_status"]), (True, "failed"))
        self.assertIsNone(lesson["media"]["mp4"])
        self.assertTrue(lesson["media"]["srt"])
        folder = client.app.state.cache.lesson_dir(accepted["lesson_id"], accepted["variant"])
        for name in ("lesson.json", "timeline.json", "props.json", "lesson.srt", "meta.json"):
            self.assertTrue((folder / name).is_file(), name)

    # ---- preview contract ---------------------------------------------------------------
    def test_preview_visible_while_export_is_running(self) -> None:
        entered, release = Event(), Event()

        def slow_export(run: PipelineRun) -> None:
            run.progress(0.4)
            entered.set()
            release.wait(10)
            write_mp4(run)

        client = self.client(fake_ops(export=slow_export))
        accepted = self.post(client)
        self.assertTrue(entered.wait(10))
        job = client.get(f"/api/jobs/{accepted['job_id']}").json()
        self.assertEqual((job["status"], job["preview_ready"], job["playable"], job["export_status"]),
                         ("running", True, True, "running"))
        self.assertEqual(job["progress"], 0.4)
        lesson = client.get(f"/api/lessons/{accepted['lesson_id']}").json()
        self.assertEqual((lesson["preview_ready"], lesson["export_status"]), (True, "running"))
        self.assertIsNone(lesson["media"]["mp4"])
        release.set()
        self.assertEqual(self.wait(client, accepted["job_id"])["export_status"], "completed")
        self.assertTrue(client.get(f"/api/lessons/{accepted['lesson_id']}").json()["media"]["mp4"])

    def test_callback_publishes_before_timeline_stage_ends(self) -> None:
        entered, release = Event(), Event()

        def timeline_then_wait(run: PipelineRun) -> None:
            mock_pipeline.timeline(run)  # persists the files and calls run.preview_ready()
            entered.set()
            release.wait(10)

        client = self.client(fake_ops(timeline=timeline_then_wait))
        accepted = self.post(client)
        self.assertTrue(entered.wait(10))
        job = client.get(f"/api/jobs/{accepted['job_id']}").json()
        self.assertTrue(job["preview_ready"])
        self.assertEqual(job["stages"][4]["status"], "running")
        release.set()
        self.wait(client, accepted["job_id"])

    def test_readiness_requires_files_not_just_stage_or_callback(self) -> None:
        def claim_without_files(run: PipelineRun) -> None:
            run.preview_ready()  # nothing was persisted

        def forget_everything(run: PipelineRun) -> None:
            return None

        for timeline in (claim_without_files, forget_everything):
            with self.subTest(timeline=timeline.__name__):
                client = self.client(fake_ops(timeline=timeline),
                                     replace_cache(self.settings, self.temp.name, timeline.__name__))
                job = self.assert_failed(client, self.post(client)["job_id"], "timeline", "preview_incomplete")
                self.assertFalse(job["preview_ready"] or job["playable"])
                self.assertEqual(job["export_status"], "pending")

    def test_preview_artifacts_must_agree(self) -> None:
        def corrupt_props(run: PipelineRun) -> None:
            run.cache.write_json(run.folder / "lesson.json", run.lesson)
            run.cache.write_json(run.folder / "timeline.json", {"timeline_version": 1})
            run.cache.write_json(run.folder / "props.json", {})
            (run.folder / "lesson.srt").write_text("1\n", encoding="utf-8")

        client = self.client(fake_ops(timeline=corrupt_props))
        self.assert_failed(client, self.post(client)["job_id"], "timeline", "preview_invalid")

    # ---- request handling ---------------------------------------------------------------
    def test_invalid_requests_return_422_with_fields(self) -> None:
        client = self.client(fake_ops())
        cases = [{"topic": "ab"}, {"language": "fr"}, {"target_seconds": 10}, {"speed": 3}, {"level": "expert"},
                 {"voice": "robot"}, {"unexpected": 1}]
        for change in cases:
            with self.subTest(change=change):
                response = client.post("/api/lessons", json={**BODY, **change})
                self.assertEqual(response.status_code, 422)
                error = response.json()["error"]
                self.assertEqual(error["code"], "validation_error")
                self.assertTrue(error["fields"])
        self.assertEqual(client.post("/api/lessons", json={**BODY, "topic": "  ab  "}).status_code, 422)

    def test_bonus_language_is_rejected(self) -> None:
        response = self.client(fake_ops()).post("/api/lessons", json={**BODY, "language": "ta"})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "language_unavailable")

    def test_busy_queue_returns_429(self) -> None:
        entered, release = Event(), Event()

        def blocked_plan(run: PipelineRun) -> None:
            entered.set()
            release.wait(10)
            mock_pipeline.plan(run)

        client = self.client(fake_ops(plan=blocked_plan))
        first = self.post(client)
        self.assertTrue(entered.wait(10))
        second = self.post(client, topic="Python loop")  # max_queued_jobs=1: one may wait
        self.assertEqual(self.wait(client, second["job_id"], lambda j: True)["queue_position"], 1)
        busy = client.post("/api/lessons", json={**BODY, "topic": "Newtons second law"})
        self.assertEqual(busy.status_code, 429)
        self.assertEqual(busy.json()["error"]["code"], "busy")
        self.assertEqual(busy.headers["Retry-After"], "30")
        again = client.post("/api/lessons", json=BODY)  # same lesson as the running job: not a new job
        self.assertEqual(again.status_code, 202)
        self.assertEqual(again.json()["job_id"], first["job_id"])
        release.set()
        self.wait(client, second["job_id"])

    def test_unknown_ids_return_404(self) -> None:
        client = self.client(fake_ops())
        self.assertEqual(client.get("/api/jobs/j_missing").json()["error"]["code"], "job_not_found")
        for path in ("/api/lessons/0123456789ab", "/api/lessons/not-an-id", "/api/lessons/0123456789ab?variant=xx"):
            self.assertEqual(client.get(path).status_code, 404, path)

    def test_variant_selection_and_listing(self) -> None:
        client = self.client(fake_ops())
        english = self.post(client)
        self.wait(client, english["job_id"])
        hindi = self.post(client, language="hi")
        self.wait(client, hindi["job_id"])
        lesson_id = english["lesson_id"]
        self.assertEqual(client.get(f"/api/lessons/{lesson_id}").json()["variant"], "hi-female-1")  # most recent
        chosen = client.get(f"/api/lessons/{lesson_id}?variant=en-female-1").json()
        self.assertEqual(chosen["variant"], "en-female-1")
        self.assertEqual(chosen["meta"]["variants"], ["en-female-1", "hi-female-1"])

    def test_cors_allows_only_local_dev_origins(self) -> None:
        client = self.client(fake_ops())
        for origin, allowed in (("http://localhost:5173", True), ("http://127.0.0.1:5173", True),
                                ("http://localhost:3000", True), ("https://example.com", False)):
            response = client.options("/api/lessons", headers={"Origin": origin, "Access-Control-Request-Method": "POST",
                                                               "Access-Control-Request-Headers": "content-type"})
            self.assertEqual(response.headers.get("access-control-allow-origin") == origin, allowed, origin)

    # ---- default behaviour and mock mode ------------------------------------------------
    def test_default_is_production_not_unavailable_or_mock(self) -> None:
        client = self.client()  # no injected ops, MOCK_PIPELINE off: production pipeline (Task 5B)
        self.assertFalse(client.app.state.orchestrator.ops.mock)
        self.assertFalse(client.get("/api/health").json()["mock_pipeline"])
        response = client.post("/api/lessons", json={**BODY, "language": "hi"})  # rejected before any job exists
        self.assertEqual((response.status_code, response.json()["error"]["code"]), (422, "language_unavailable"))
        self.assertFalse(Settings().mock_pipeline)

    def test_mock_mode_marks_everything_and_never_substitutes(self) -> None:
        client = self.client(settings=replace_settings(self.settings, mock_pipeline=True))
        self.assertTrue(client.get("/api/health").json()["mock_pipeline"])
        accepted = self.post(client, language="hi")
        self.assertTrue(accepted["mock"])
        job = self.wait(client, accepted["job_id"])
        self.assertEqual((job["status"], job["mock"], job["export_status"], job["fallback"]),
                         ("done", True, "skipped", False))
        lesson = client.get(f"/api/lessons/{accepted['lesson_id']}").json()
        self.assertTrue(lesson["mock"] and lesson["preview_ready"])
        self.assertEqual((lesson["lesson"]["source"], lesson["lesson"]["model"]), ("sample", "mock-pipeline"))
        self.assertTrue(any("MOCK" in w for w in lesson["meta"]["warnings"]))
        self.assertIsNone(lesson["media"]["mp4"])
        # Same topic as a real run gets a different lesson id: mock output can never be served as real.
        real_id = self.client(fake_ops(), replace_cache(self.settings, self.temp.name, "real")).post(
            "/api/lessons", json={**BODY, "language": "hi"}).json()["lesson_id"]
        self.assertNotEqual(real_id, accepted["lesson_id"])
        # A topic without a fixture is refused, not answered with an unrelated sample.
        refused = client.post("/api/lessons", json={**BODY, "topic": "Binary Search"})
        self.assertEqual((refused.status_code, refused.json()["error"]["code"]), (422, "mock_topic_unavailable"))


def replace_settings(settings: Settings, **changes: object) -> Settings:
    return Settings.model_validate({**settings.model_dump(), **changes})


def replace_cache(settings: Settings, root: str, name: str) -> Settings:
    return replace_settings(settings, cache_dir=Path(root) / name)


if __name__ == "__main__":
    unittest.main()
