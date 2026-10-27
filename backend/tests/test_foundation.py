from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from threading import Event, get_ident
from unittest.mock import patch

from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.app.cache import Cache, plan_key, variant_key
from backend.app.config import ROOT, Settings, read_env_file
from backend.app.contracts import ConfigResponse, HealthResponse
from backend.app.jobs import STAGES, JobContext, JobRunner
from backend.app.main import create_app


class FoundationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.settings = Settings(device="cpu", cache_dir=self.root / "cache",
                                 web_dist=self.root / "web", render_bundle=self.root / "bundle")

    def test_settings_paths_offline_and_profiles(self) -> None:
        self.assertTrue(self.settings.offline)
        self.assertEqual(self.settings.resolve_profile(), "cpu")
        self.assertEqual(Settings(cache_dir="cache").cache_dir, ROOT / "cache")
        self.assertEqual(self.settings.kokoro_model.parent, self.settings.models_dir / "kokoro")
        self.assertEqual(self.settings.planner_model("gpu"), "qwen3:8b")
        with patch.dict("sys.modules", {"torch": None}):
            self.assertEqual(Settings(device="auto").resolve_profile(), "cpu")
            with self.assertRaises(ValueError):
                Settings(device="cuda").resolve_profile()

    def test_env_preserves_windows_paths(self) -> None:
        env = self.root / ".env"
        env.write_text('# comment\nMODELS_DIR="C:\\models\\local"\nDEVICE=cpu\n', encoding="utf-8")
        self.assertEqual(read_env_file(env), {"MODELS_DIR": r"C:\models\local", "DEVICE": "cpu"})
        env.write_text("bad line", encoding="utf-8")
        with self.assertRaises(ValueError):
            read_env_file(env)

    def test_reject_external_service_and_invalid_settings(self) -> None:
        for url in ("https://example.com", "http://127.0.0.1:9000", "http://user@localhost:11434"):
            with self.assertRaises(ValidationError):
                Settings(ollama_url=url)
        with self.assertRaises(ValidationError):
            Settings(device="gpu")

    def test_health_config_and_static_media(self) -> None:
        application = create_app(self.settings)
        with TestClient(application) as client:
            health = client.get("/api/health")
            self.assertEqual(health.status_code, 200)
            result = HealthResponse.model_validate(health.json())
            self.assertFalse(result.ok)
            self.assertTrue(result.offline)
            self.assertEqual(result.device_profile, "cpu")
            self.assertTrue(result.models.tts_parler.enabled)  # Task 7 supports CPU; still lazy/unloaded
            self.assertFalse(result.models.tts_parler.ready)
            self.assertEqual(result.queue_length, 0)
            configuration = client.get("/api/config")
            self.assertEqual(configuration.status_code, 200)
            config = ConfigResponse.model_validate(configuration.json())
            self.assertEqual(config.target_seconds.model_dump(), {"min": 30, "max": 90, "step": 15, "default": 60})
            self.assertEqual([x.code for x in config.languages[:3]], ["en", "hi", "kn"])
            self.assertEqual(config.languages[2].native, "ಕನ್ನಡ")
            self.assertEqual([x.code for x in config.languages if x.available], ["en"])  # production is English-only
            media = application.state.cache.lesson_dir("012345abcdef", "en-female-1")
            media.mkdir(parents=True)
            (media / "lesson.srt").write_text("sample captions", encoding="utf-8")
            self.assertEqual(client.get("/media/012345abcdef/en-female-1/lesson.srt").text, "sample captions")
            self.assertEqual(client.get("/media/missing.mp4").status_code, 404)
            self.assertEqual(client.get("/docs").status_code, 404)
            self.assertEqual(client.get("/api/missing").json()["error"]["code"], "404")
            self.assertEqual(client.post("/api/lessons", json={}).status_code, 422)
            self.assertEqual(client.post("/api/lessons", json={"topic": "Water Cycle", "language": "hi"}).status_code, 422)  # production is English-only
        self.assertFalse(application.state.runner._thread.is_alive())

    def test_built_web_mount_is_optional(self) -> None:
        self.settings.web_dist.mkdir()
        (self.settings.web_dist / "index.html").write_text("<p>Blu</p>", encoding="utf-8")
        with TestClient(create_app(self.settings)) as client:
            self.assertEqual(client.get("/").text, "<p>Blu</p>")
            self.assertEqual(client.get("/api/config").status_code, 200)

    def test_cache_keys_atomic_roundtrip_and_traversal(self) -> None:
        cache = Cache(self.settings.cache_dir)
        cache.initialize()
        key = plan_key(" Python loop? ", "beginner", 60, "model", "p1", "1.0")
        self.assertEqual(key, plan_key("python loop", "beginner", 60, "model", "p1", "1.0"))
        self.assertNotEqual(key, plan_key("python loop", "beginner", 60, "model", "p2", "1.0"))
        self.assertEqual(variant_key("hi", "female", 1.0), "hi-female-1")
        cache.write_json(cache.index, [{"title": "ಕನ್ನಡ"}])
        cache.initialize()
        self.assertEqual(json.loads(cache.index.read_text(encoding="utf-8")), [{"title": "ಕನ್ನಡ"}])
        for lesson, variant in (("../outside", None), (key, "../outside")):
            with self.assertRaises(ValueError):
                cache.lesson_dir(lesson, variant)
        with self.assertRaises(ValueError):
            cache.write_json(self.root / "outside.json", {})

    def test_runner_rejects_unimplemented_pipeline(self) -> None:
        runner = JobRunner(Cache(self.settings.cache_dir), "cpu")
        runner.start()
        try:
            with self.assertRaisesRegex(RuntimeError, "not implemented"):
                runner.submit("012345abcdef", "en-female-1", "en")
        finally:
            runner.close()

    def test_single_worker_stage_order_queue_and_logs(self) -> None:
        entered, release = Event(), Event()
        calls: list[tuple[str, str, int]] = []

        def handler(name: str):
            def run(ctx: JobContext) -> JobContext:
                calls.append((ctx.job.job_id, name, get_ident()))
                if name == "plan" and len(calls) == 1:
                    entered.set()
                    if not release.wait(5):
                        raise TimeoutError("Test did not release worker")
                return ctx
            return run

        cache = Cache(self.settings.cache_dir)
        cache.initialize()
        runner = JobRunner(cache, "cpu", {name: handler(name) for name in STAGES}, lambda ctx, name, exc: ctx)
        runner.start()
        try:
            first = runner.submit("012345abcdef", "en-female-1", "en")
            self.assertTrue(entered.wait(5))
            second = runner.submit("abcdef012345", "hi-female-1", "hi")
            self.assertEqual(runner.queue_length, 1)
            self.assertEqual(runner.snapshot(second.job_id).queue_position, 1)
            snapshot = runner.snapshot(first.job_id)
            snapshot.status = "error"
            self.assertEqual(runner.snapshot(first.job_id).status, "running")
        finally:
            release.set()
            runner.close()
        self.assertEqual([name for job, name, tid in calls if job == first.job_id],
                         [name for name in STAGES if name != "translate"])
        self.assertEqual(len({tid for job, name, tid in calls}), 1)
        self.assertEqual([job for job, name, tid in calls], [first.job_id] * 5 + [second.job_id] * 6)
        for job in (first, second):
            result = runner.snapshot(job.job_id)
            self.assertEqual(result.status, "done")
            self.assertTrue(result.playable)
            self.assertTrue(all(s.ms >= 0 and s.rss_mb > 0 for s in result.stages))
        records = [json.loads(line) for line in cache.runs.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(records), 12)
        self.assertEqual(set(records[0]), {"job_id", "stage", "ms", "rss_mb", "device", "ok", "note"})

    def test_failed_fallback_does_not_kill_worker(self) -> None:
        def fail(ctx: JobContext) -> JobContext:
            raise ValueError("synthetic stage failure")

        def fallback(ctx: JobContext, name: str, exc: Exception) -> JobContext:
            raise RuntimeError("synthetic fallback failure")

        cache = Cache(self.settings.cache_dir)
        runner = JobRunner(cache, "cpu", {name: fail for name in STAGES}, fallback)
        runner.start()
        with self.assertLogs("backend.app.jobs", level="ERROR"):
            jobs = [runner.submit(key, "en-female-1", "en") for key in ("012345abcdef", "abcdef012345")]
            runner.close()
        for job in jobs:
            result = runner.snapshot(job.job_id)
            self.assertEqual(result.status, "error")
            self.assertTrue(result.fallback)
            self.assertEqual(result.error, "synthetic fallback failure")
            self.assertFalse(result.playable)
        self.assertEqual(len(cache.runs.read_text(encoding="utf-8").splitlines()), 2)


if __name__ == "__main__":
    unittest.main()
