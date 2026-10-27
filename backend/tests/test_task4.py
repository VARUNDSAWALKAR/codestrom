from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

import httpx

from backend.app.config import ROOT, Settings
from backend.app.planner.ollama_client import PlanRequest, output_schema, plan_lesson
from backend.app.planner.subject import classify_subject, effective_subject
from backend.app.planner.validate import narration_range


class PlannerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.settings = Settings(device="cpu", cache_dir=self.root / "cache")
        sample = json.loads((ROOT / "data/samples/water_cycle.en.json").read_text(encoding="utf-8"))
        self.content = {k: sample[k] for k in ("title", "subject", "keep_terms", "scenes")}
        self.content["scenes"] = self.content["scenes"][:3]
        self.content["scenes"][1]["layout"] = "flow"
        self.content["scenes"][1].pop("center", None)
        self.calls: list[dict] = []

    def run_plan(self, replies: list, *, language: str = "en", topic: str = "Water Cycle",
                 thinking: bool = True, subject: str | None = None):
        def handle(request: httpx.Request) -> httpx.Response:
            payload = json.loads(request.content)
            self.assertEqual(request.url.host, "127.0.0.1")
            if request.url.path == "/api/show":
                return httpx.Response(200, json={"capabilities": ["completion"] + (["thinking"] if thinking else [])})
            self.calls.append(payload)
            self.assertEqual(request.extensions["timeout"]["read"], 180)
            item = replies.pop(0)
            if isinstance(item, Exception):
                raise item
            if isinstance(item, httpx.Response):
                return item
            return httpx.Response(200, json={"done": True, "message": {"content": item}})
        return plan_lesson(PlanRequest(topic=topic, language=language, subject=subject), self.settings,
                           transport=httpx.MockTransport(handle), debug_dir=self.root / "debug")

    def good(self) -> str:
        return self.gen(self.content)

    @staticmethod
    def gen(content: dict) -> str:
        """Generation shape: title card split from the explaining scenes."""
        data = copy.deepcopy(content)
        data["title_card"], *data["scenes"] = data["scenes"]
        if data["subject"] == "programming":
            data["code_scene"], data["diagram_scene"] = data.pop("scenes")[:2]
        return json.dumps(data)

    def test_valid_settings_and_cache(self) -> None:
        result = self.run_plan([self.good()])
        self.assertIsNone(result.error)
        self.assertEqual(result.lesson.language, "en")
        call = self.calls[0]
        self.assertFalse(call["think"])
        self.assertEqual(call["keep_alive"], "10m")
        self.assertEqual(call["options"]["temperature"], .3)
        self.assertEqual(call["options"]["num_gpu"], 0)
        self.assertIn("$defs", call["format"])
        self.assertEqual(len(call["format"]["anyOf"]), 1)  # Water Cycle is classified as science
        self.assertFalse((self.root / "debug").exists())
        self.assertTrue(self.run_plan([]).cached)

    def test_english_with_requested_language(self) -> None:
        for language in ("hi", "kn"):
            result = self.run_plan([self.good()], language=language)
            self.assertEqual(result.request.language, language)
            self.assertEqual(result.lesson.language, "en")
            self.assertNotIn(language, self.calls[0]["messages"][1]["content"])

    def test_invalid_json_and_repair_failure(self) -> None:
        result = self.run_plan(["not json", "{}"]) 
        self.assertEqual(result.error.code, "validation_failed")
        self.assertIsNone(result.lesson)
        self.assertEqual(len(self.calls), 2)
        files = list((self.root / "debug").glob("*.json"))
        self.assertEqual(len(files), 2)
        self.assertTrue(all("validation_error" in json.loads(p.read_text()) for p in files))

    def test_repair_success(self) -> None:
        result = self.run_plan(["{}", self.good()])
        self.assertIsNone(result.error)
        self.assertEqual(result.attempts, 2)
        self.assertEqual(len(list((self.root / "debug").glob("*.json"))), 1)

    def test_invalid_contracts(self) -> None:
        cases = []
        missing = copy.deepcopy(self.content); del missing["scenes"][1]["steps"][0]["narration"]; cases.append(missing)
        scene = copy.deepcopy(self.content); scene["scenes"][1]["type"] = "animation"; cases.append(scene)
        layout = copy.deepcopy(self.content); layout["scenes"][1]["layout"] = "grid"; cases.append(layout)
        props = copy.deepcopy(self.content); props["scenes"][1]["nodes"] = []; cases.append(props)
        animation = copy.deepcopy(self.content); animation["scenes"][1]["animation"] = "spin"; cases.append(animation)
        center = copy.deepcopy(self.content); center["scenes"][1]["center"] = "water"; cases.append(center)
        labelled = copy.deepcopy(self.content); del labelled["scenes"][2]["center"]; cases.append(labelled)
        code = copy.deepcopy(self.content); code["scenes"][1]["steps"][0]["lines"] = [1]; cases.append(code)
        empty = copy.deepcopy(self.content); empty["scenes"][1]["steps"][0]["text"] = " "; cases.append(empty)
        translated = copy.deepcopy(self.content); translated["title"] = "ನೀರು"; cases.append(translated)
        too_short = copy.deepcopy(self.content)
        for s in too_short["scenes"]:
            s["narration"] = "Water."
            for step in s["steps"]:
                step["narration"] = "Water."
        cases.append(too_short)
        for bad in cases:
            with self.subTest(bad=bad):
                result = self.run_plan([self.gen(bad)] * 2)
                self.assertEqual(result.error.code, "validation_failed")

    def test_timeout_no_retry(self) -> None:
        result = self.run_plan([httpx.ReadTimeout("slow")])
        self.assertEqual(result.error.code, "timeout")
        self.assertEqual(len(self.calls), 1)

    def test_unavailable_no_retry(self) -> None:
        result = self.run_plan([httpx.ConnectError("offline")])
        self.assertEqual(result.error.code, "unavailable")
        self.assertEqual(len(self.calls), 1)

    def test_rejected_options_are_explicit(self) -> None:
        result = self.run_plan([httpx.Response(400, json={"error": "think unsupported"})])
        self.assertEqual(result.error.code, "ollama_rejected")
        self.assertIn("think unsupported", result.error.message)
        self.assertEqual(len(self.calls), 1)

    def test_non_thinking_instruct_is_explicit(self) -> None:
        result = self.run_plan([self.good()], thinking=False)
        self.assertIsNone(result.error)
        self.assertNotIn("think", self.calls[0])
        self.assertIn("omitted", result.notes[0])

    def test_no_unrelated_fallback(self) -> None:
        for topic in ("Binary Search", "Photosynthesis", "Python loops"):
            result = self.run_plan(["{}", "{}"], topic=topic)
            self.assertIsNone(result.lesson)
            self.assertEqual(result.error.code, "validation_failed")

    def test_topic_mismatch(self) -> None:
        result = self.run_plan([self.good()] * 2, topic="Binary Search")
        self.assertEqual(result.error.code, "validation_failed")

    def test_code_display_validation(self) -> None:
        sample = json.loads((ROOT / "data/fallback/python_loop.en.json").read_text(encoding="utf-8"))
        self.content = {k: sample[k] for k in ("title", "subject", "keep_terms", "scenes")}
        self.content["scenes"] = self.content["scenes"][:3]
        good = copy.deepcopy(self.content)
        self.content["scenes"][1]["code"] = "import os\nos.system('anything')"
        result = self.run_plan([self.good()] * 2, topic="Python loop")
        self.assertEqual(result.error.code, "validation_failed")
        self.content = good
        self.assertIsNone(self.run_plan([self.good()], topic="Python loop").error)

    def test_malformed_envelope(self) -> None:
        result = self.run_plan([httpx.Response(200, json=[])])
        self.assertEqual(result.error.code, "planner_error")

    def test_missing_model(self) -> None:
        def handle(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404, json={"error": "model not found"})
        result = plan_lesson(PlanRequest(topic="Water Cycle"), self.settings,
                             transport=httpx.MockTransport(handle), debug_dir=self.root / "debug")
        self.assertEqual(result.error.code, "ollama_rejected")
        self.assertEqual(result.attempts, 0)
        self.assertIsNone(result.lesson)


    # Task 4b: deterministic subject classification and narration-length checks.

    def programming_content(self) -> None:
        sample = json.loads((ROOT / "data/fallback/python_loop.en.json").read_text(encoding="utf-8"))
        self.content = {k: sample[k] for k in ("title", "subject", "keep_terms", "scenes")}
        self.content["scenes"] = self.content["scenes"][:3]

    def test_keyword_classification(self) -> None:
        cases = {"Binary Search": "programming", "Python for loop": "programming", "Merge Sort": "programming",
                 "Water Cycle": "science", "Photosynthesis": "science", "How do trees absorb water?": "science",
                 "Genetic code": "science", "Graph traversal": "programming", "Roman Empire": None}
        for topic, expected in cases.items():
            with self.subTest(topic=topic):
                self.assertEqual(classify_subject(topic), expected)

    def test_ambiguous_words_do_not_force_programming(self) -> None:
        for topic in ("Tree rings and climate", "The human heart function"):
            self.assertNotEqual(classify_subject(topic), "programming")

    def test_explicit_subject_overrides_keywords(self) -> None:
        self.assertEqual(effective_subject("Binary Search", "other"), "other")
        self.assertEqual(effective_subject("Water Cycle", "programming"), "programming")
        self.run_plan([self.good()], subject="science")
        self.assertEqual(self.calls[0]["format"]["anyOf"][0]["properties"]["subject"]["enum"],
                         ["physics", "chemistry", "biology"])
        self.assertNotIn("code_scene", output_schema("other")["anyOf"][0]["properties"])
        self.assertEqual(list(output_schema("programming")["anyOf"][0]["properties"]["subject"].values())[0], "programming")

    def test_programming_requires_code_walkthrough(self) -> None:
        self.programming_content()
        result = self.run_plan([self.good()], topic="Python loop")
        self.assertIsNone(result.error)
        self.assertIn("code_walkthrough", {s.type for s in result.lesson.scenes})
        self.assertIn("code_scene", self.calls[0]["format"]["anyOf"][0]["properties"])
        self.assertIn("programming topic", self.calls[0]["messages"][0]["content"])
        science = self.run_plan([self.good()] * 2, topic="Python loop", subject="science")
        self.assertEqual(science.error.code, "validation_failed")
        water = self.run_plan([self.good()] * 2, topic="Water Cycle", subject="programming")
        self.assertEqual(water.error.code, "validation_failed")

    def test_non_programming_prompt_forbids_code(self) -> None:
        self.run_plan([self.good()])
        self.assertIn("never use code_walkthrough", self.calls[0]["messages"][0]["content"])
        self.assertNotIn("code_scene", self.calls[0]["format"]["anyOf"][0]["properties"])

    def test_subject_changes_cache_key(self) -> None:
        self.assertFalse(self.run_plan([self.good()], subject="science").cached)
        self.assertTrue(self.run_plan([], subject="science").cached)
        self.assertFalse(self.run_plan([self.good()], subject="other").cached)

    def test_code_dimensions_not_relaxed_and_repair_is_precise(self) -> None:
        self.programming_content()
        self.content["scenes"][1]["code"] = "\n".join(f"x{i} = {i}" for i in range(13))
        self.content["scenes"][1]["steps"][0]["lines"] = [1]
        result = self.run_plan([self.good()] * 3, topic="Python loop")
        self.assertEqual(result.error.code, "validation_failed")
        self.assertEqual(len(self.calls), 2)
        self.assertIn("13 lines", self.calls[1]["messages"][-1]["content"])

    def test_insufficient_narration_triggers_single_repair(self) -> None:
        short = copy.deepcopy(self.content)
        for scene in short["scenes"]:
            scene["narration"] = "Water moves."
            for step in scene["steps"]:
                step["narration"] = "Water moves."
        result = self.run_plan([self.gen(short), self.good()])
        self.assertIsNone(result.error)
        self.assertEqual(result.attempts, 2)
        self.assertIn("Add about", self.calls[1]["messages"][-1]["content"])
        failed = self.run_plan([self.gen(short)] * 3, subject="other")  # new cache key
        self.assertEqual(failed.error.code, "validation_failed")
        self.assertEqual(len(self.calls), 4)  # two attempts per run: one repair only

    def test_acceptable_narration_and_word_range(self) -> None:
        self.assertEqual(narration_range(60), (110, 130))
        self.assertEqual(narration_range(30), (55, 65))
        self.assertIsNone(self.run_plan([self.good()]).error)
        payload = json.loads(self.calls[0]["messages"][1]["content"])
        self.assertEqual(payload["narration_word_range"], [110, 130])


if __name__ == "__main__":
    unittest.main()
