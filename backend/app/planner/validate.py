"""Practical checks on top of the existing rendering contract. Never runs code."""
from __future__ import annotations

import ast
import re
import unicodedata

from .schema import Lesson

# English narration pace including short pauses and scene transitions (about 120 words
# for 60 s). Only clearly insufficient narration is rejected (below MIN_WPS).
TARGET_WPS = 2.0
MIN_WPS = 1.5
MAX_WPS = 3.0


def narration_range(seconds: int) -> tuple[int, int]:
    """Words to ask Ollama for: 110-130 for 60 s, scaled proportionally."""
    return round(seconds * 11 / 6), round(seconds * 13 / 6)


def validate_plan(lesson: Lesson, subject: str | None = None) -> Lesson:
    """`subject` is the effective request subject (programming/science/other) if known."""
    if lesson.language != "en":
        raise ValueError("Planner content must be English")
    has_code = any(scene.type == "code_walkthrough" for scene in lesson.scenes)
    if subject == "programming" and (lesson.subject != "programming" or not has_code):
        raise ValueError("Programming topic requires subject programming and a code_walkthrough scene")
    if subject in {"science", "other"} and (lesson.subject == "programming" or has_code):
        raise ValueError(f"Non-programming ({subject}) topic must not use subject programming or code_walkthrough")
    spoken: list[str] = []
    visible = [lesson.title]
    for scene in lesson.scenes:
        if scene.type not in {"title_card", "diagram", "code_walkthrough"}:
            raise ValueError("Task 4 supports title_card, diagram, code_walkthrough only")
        allowed = {"id", "type", "heading", "narration", "steps"} | {
            "title_card": {"subtitle"}, "diagram": {"layout", "center"},
            "code_walkthrough": {"code", "code_language"},
        }[scene.type]
        if scene.model_fields_set - allowed:
            raise ValueError(f"Unsupported properties for {scene.type}: {scene.model_fields_set - allowed}")
        if not scene.heading.strip() or len(scene.heading) > 60 or len(scene.subtitle) > 120:
            raise ValueError("Scene heading/subtitle empty or too long")
        visible.extend([scene.heading, scene.subtitle, scene.center])
        spoken.append(scene.narration)
        if scene.type == "diagram":
            if "layout" not in scene.model_fields_set:
                raise ValueError("Diagram requires explicit layout")
            if scene.layout == "flow" and "center" in scene.model_fields_set:
                raise ValueError("Flow must omit center (rendering contract)")
            if scene.layout == "labelled" and not scene.center.strip():
                raise ValueError("Labelled diagram requires center")
            if scene.code or scene.expression:
                raise ValueError("Diagram cannot contain code or expression")
        if scene.type == "code_walkthrough":
            if lesson.subject != "programming" or "code_language" not in scene.model_fields_set:
                raise ValueError("Code requires programming subject and code_language")
            if any(not step.lines for step in scene.steps):
                raise ValueError("Code steps require line highlights")
            if re.search(r"\b(import|exec|eval|compile|__import__|subprocess|fetch|require)\b|os\.|https?://", scene.code):
                raise ValueError("Code must be a self-contained display example, without executable commands")
            if scene.code_language == "python":
                ast.parse(scene.code)  # Syntax only: never execute model text.
        for step in scene.steps:
            if not step.text.strip() or len(step.text) > 60 or len(step.note) > 90:
                raise ValueError("Step label empty or label/note too long")
            if scene.type == "diagram" and (step.lines or step.output):
                raise ValueError("Diagram steps cannot use code properties")
            visible.extend([step.text, step.note])
            spoken.append(step.narration)
    narration = " ".join(spoken)
    words = len(narration.split())
    low, high = lesson.target_seconds * MIN_WPS, lesson.target_seconds * MAX_WPS
    if not low <= words <= high:
        lo, hi = narration_range(lesson.target_seconds)
        raise ValueError(f"Narration has {words} words; require {low:g}-{high:g} (aim for {lo}-{hi}). "
                         + (f"Add about {lo - words} words of meaningful explanation across step narrations."
                            if words < low else f"Remove about {words - hi} words."))
    text = " ".join(visible + spoken)
    if any(c.isalpha() and "LATIN" not in unicodedata.name(c, "") for c in text):
        raise ValueError("Narration and labels must use English, not translated scripts")
    stop = set("how does do a an the is are what why work works explain introduction to of in and for".split())
    tokens = set(re.findall(r"[a-z0-9]+", lesson.topic.lower())) - stop
    content_tokens = set(re.findall(r"[a-z0-9]+", text.lower()))
    if tokens and len(tokens & content_tokens) < max(1, (len(tokens) + 1) // 2):
        raise ValueError("Lesson content does not align with requested topic keywords")
    return lesson
