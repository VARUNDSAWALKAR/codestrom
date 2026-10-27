"""Content keys and local cache layout. No model or generation logic."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from threading import RLock
from typing import TypeVar
from uuid import uuid4

from pydantic import BaseModel, JsonValue, TypeAdapter

Model = TypeVar("Model", bound=BaseModel)


def normalize_topic(topic: str) -> str:
    return " ".join("".join(c for c in topic.lower() if c.isalnum() or c.isspace()).split())


def plan_key(topic: str, level: str, target_seconds: int, model: str,
             prompt_version: str, schema_version: str) -> str:
    content = "|".join((normalize_topic(topic), level, str(target_seconds), model,
                        prompt_version, schema_version))
    return hashlib.sha1(content.encode("utf-8")).hexdigest()[:12]


def variant_key(language: str, voice: str, speed: float) -> str:
    if language not in {"en", "hi", "kn", "ta", "te", "bn", "mr"} or voice not in {"female", "male"}:
        raise ValueError("Invalid language or voice")
    if not 0.8 <= speed <= 1.2:
        raise ValueError("Speed must be between 0.8 and 1.2")
    return f"{language}-{voice}-{speed:g}"


class Cache:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.lessons = self.root / "lessons"
        self.audio = self.root / "audio"
        self.translations = self.root / "translations"
        self.index = self.root / "index.json"
        self.runs = self.root / "runs.jsonl"
        self._lock = RLock()

    def initialize(self) -> None:
        with self._lock:
            for directory in (self.lessons, self.audio, self.translations):
                directory.mkdir(parents=True, exist_ok=True)
            if not self.index.exists():
                self.write_json(self.index, [])

    def lesson_dir(self, lesson_id: str, variant: str | None = None) -> Path:
        if lesson_id != "fallback-python-loop" and not re.fullmatch(r"[a-f0-9]{12}(?:-v[2-9][0-9]*|-v1[0-9]+)?", lesson_id):
            raise ValueError("Invalid lesson id")
        path = self.lessons / lesson_id
        if variant is not None:
            if not re.fullmatch(r"(?:en|hi|kn|ta|te|bn|mr)-(?:female|male)-[0-9]+(?:\.[0-9]+)?", variant):
                raise ValueError("Invalid variant")
            path /= variant
        return self._inside(path)

    def _inside(self, path: Path) -> Path:
        resolved = path.resolve()
        if not resolved.is_relative_to(self.root):
            raise ValueError("Cache path escapes cache root")
        return resolved

    def write_json(self, path: Path, value: BaseModel | JsonValue) -> None:
        path = self._inside(path)
        payload = value.model_dump(mode="json") if isinstance(value, BaseModel) else value
        payload = TypeAdapter(JsonValue).validate_python(payload)
        with self._lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
            try:
                temporary.write_text(json.dumps(payload, ensure_ascii=False, allow_nan=False), encoding="utf-8")
                temporary.replace(path)
            finally:
                temporary.unlink(missing_ok=True)

    def read_model(self, path: Path, model: type[Model]) -> Model:
        return model.model_validate_json(self._inside(path).read_text(encoding="utf-8"))

    def append_run(self, record: BaseModel) -> None:
        with self._lock:
            self.root.mkdir(parents=True, exist_ok=True)
            with self.runs.open("a", encoding="utf-8") as stream:
                stream.write(record.model_dump_json() + "\n")
