"""Validated lesson data consumed by speech; no planning or code execution."""
from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from ..config import Language

SceneType = Literal["title_card", "code_walkthrough", "diagram", "formula", "recap"]


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Step(ContractModel):
    text: str
    narration: str = Field(min_length=1)
    note: str = ""
    lines: list[int] = Field(default_factory=list)
    output: str = ""
    in_expression: bool = True


class Scene(ContractModel):
    id: str = Field(pattern=r"^s[1-9][0-9]*$")
    type: SceneType
    heading: str = Field(min_length=1)
    narration: str
    steps: list[Step]
    subtitle: str = ""
    code: str = ""
    code_language: Literal["python", "javascript", "java", "c", "cpp", "other"] = "other"
    layout: Literal["flow", "cycle", "labelled"] = "flow"
    center: str = ""
    expression: str = ""

    @model_validator(mode="after")
    def check_scene(self) -> Scene:
        limits = {"title_card": (0, 0), "code_walkthrough": (1, 5),
                  "diagram": (2, 6), "formula": (1, 5), "recap": (2, 4)}
        lo, hi = limits[self.type]
        if not lo <= len(self.steps) <= hi:
            raise ValueError(f"{self.type} requires {lo}–{hi} steps")
        if self.type == "title_card" and not self.narration.strip():
            raise ValueError("Title card requires narration")
        if any(not s.narration.strip() for s in self.steps):
            raise ValueError("Empty step narration")
        if self.type == "code_walkthrough":
            lines = self.code.splitlines()
            if not self.code.strip() or len(lines) > 12 or any(len(x) > 60 for x in lines):
                raise ValueError("Invalid code display dimensions")
            if any(n < 1 or n > len(lines) for step in self.steps for n in step.lines):
                raise ValueError("Code highlight outside code")
        if self.type == "formula" and not self.expression.strip():
            raise ValueError("Formula requires expression")
        return self


class Lesson(ContractModel):
    schema_version: Literal["1.0"]
    lesson_id: str = Field(pattern=r"^(?:[a-f0-9]{12}(?:-v[0-9]+)?|fallback-python-loop|sample-[a-z0-9-]+)$")
    topic: str = Field(min_length=3, max_length=120)
    level: Literal["beginner", "intermediate"]
    target_seconds: int = Field(ge=30, le=90)
    language: Language
    source: Literal["llm", "fallback", "sample", "edited"]
    model: str
    prompt_version: str
    warnings: list[str] = Field(default_factory=list)
    title: str = Field(min_length=1)
    subject: Literal["programming", "physics", "chemistry", "biology", "math", "other"]
    keep_terms: list[str] = Field(max_length=8)
    scenes: list[Scene] = Field(min_length=3, max_length=6)

    @model_validator(mode="after")
    def check_lesson(self) -> Lesson:
        if self.scenes[0].type != "title_card" or sum(s.type == "title_card" for s in self.scenes) != 1:
            raise ValueError("Exactly one initial title card required")
        if len({s.id for s in self.scenes}) != len(self.scenes):
            raise ValueError("Duplicate scene ids")
        types = {s.type for s in self.scenes}
        if not types.intersection({"code_walkthrough", "diagram", "formula"}):
            raise ValueError("Lesson needs an explaining scene")
        if self.subject == "programming" and "code_walkthrough" not in types:
            raise ValueError("Programming lesson requires code walkthrough")
        return self
