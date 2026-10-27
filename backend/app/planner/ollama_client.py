"""Bounded localhost planner interface for future orchestration (no stages wired)."""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from time import perf_counter
from typing import Literal
from uuid import uuid4

import httpx
from pydantic import Field, ValidationError, field_validator

from ..cache import Cache, plan_key
from ..config import ROOT, Language, Settings
from .prompt import PROMPT_VERSION, system_prompt
from .schema import ContractModel, Lesson, Scene
from .subject import RequestSubject, effective_subject
from .validate import narration_range, validate_plan


class PlanRequest(ContractModel):
    topic: str = Field(min_length=3, max_length=120)
    level: Literal["beginner", "intermediate"] = "beginner"
    language: Language = "en"
    target_seconds: int = Field(default=60, ge=30, le=90)
    subject: RequestSubject | None = None  # explicit choice overrides keyword classification

    @field_validator("topic", mode="before")
    @classmethod
    def trim_topic(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else value


class PlanContent(ContractModel):
    title: str = Field(min_length=1, max_length=120)
    subject: Literal["programming", "physics", "chemistry", "biology", "math", "other"]
    keep_terms: list[str] = Field(max_length=8)
    scenes: list[Scene] = Field(min_length=3, max_length=6)


class PlanError(ContractModel):
    code: str
    message: str


def output_schema(subject: RequestSubject | None = None) -> dict:
    """Narrow the shared permissive Scene to its existing renderer variants.

    A known `subject` keeps only the matching branch: programming -> code + worked
    example; science/other -> diagram scenes with a non-programming Lesson subject.
    Reuse field definitions; conditional requirements in Pydantic validators are
    otherwise invisible to Ollama's JSON-schema grammar.
    """
    schema = PlanContent.model_json_schema()
    scene = schema["$defs"]["Scene"]
    step = schema["$defs"]["Step"]
    variants = []
    for kind, extra, count in (
        ("title_card", ["subtitle"], (0, 0)),
        ("diagram", ["layout", "center"], (2, 4)),  # narrower than the 2-6 contract: bounds narration
        ("code_walkthrough", ["code", "code_language"], (2, 4)),
    ):
        names = ["id", "type", "heading", "narration", "steps"] + extra
        properties = {k: deepcopy(scene["properties"][k]) for k in names}
        properties["type"] = {"const": kind, "type": "string"}
        steps = deepcopy(step)
        allowed = ["text", "narration", "note"] + (["lines", "output"] if kind == "code_walkthrough" else [])
        steps["properties"] = {k: steps["properties"][k] for k in allowed}
        if kind == "code_walkthrough":
            steps["required"] = ["text", "narration", "lines"]
        properties["steps"] = {"type": "array", "items": steps, "minItems": count[0], "maxItems": count[1]}
        required = ["id", "type", "heading", "narration", "steps"]
        if kind == "code_walkthrough":
            required += ["code", "code_language"]
        if kind == "diagram":
            required += ["layout"]
        variants.append({"type": "object", "additionalProperties": False,
                         "properties": properties, "required": required})
    # Small models repeat title cards or skip the code scene under a plain anyOf, so
    # the schema is conditional on `subject`: programming lessons have fixed
    # title_card / code_scene / diagram_scene fields; other subjects have a
    # title_card plus diagram-only scenes.
    title, diagram, code = variants
    props = schema.pop("properties")
    schema.pop("required", None)
    common = {k: props[k] for k in ("title", "keep_terms")}
    worked = deepcopy(diagram)  # worked example: flow only, so center cannot be emitted
    worked["properties"].pop("center")
    worked["properties"]["layout"] = {"const": "flow", "type": "string"}
    layouts = []  # per-layout variants: flow omits center, labelled requires it
    for layout in ("flow", "cycle", "labelled"):
        variant = deepcopy(diagram)
        variant["properties"]["layout"] = {"const": layout, "type": "string"}
        if layout == "flow":
            variant["properties"].pop("center")
        elif layout == "labelled":
            variant["required"] = [*variant["required"], "center"]
        layouts.append(variant)
    programming = {**common, "subject": {"const": "programming", "type": "string"},
                   "title_card": title, "code_scene": code, "diagram_scene": worked}
    non_programming = [x for x in props["subject"]["enum"] if x != "programming"]
    other_subjects = {"science": ["physics", "chemistry", "biology"],
                      "other": ["math", "other"]}.get(subject, non_programming)
    other = {**common, "subject": {"enum": other_subjects, "type": "string"}, "title_card": title,
             "scenes": {"type": "array", "items": {"anyOf": layouts}, "minItems": 2, "maxItems": 4}}
    branches = {"programming": [programming], "science": [other], "other": [other]}.get(
        subject, [programming, other])
    schema["anyOf"] = [{"type": "object", "additionalProperties": False, "properties": p,
                        "required": list(p)} for p in branches]
    schema["type"] = "object"
    return schema


def repair_hint(error: str, raw: object) -> str:
    """Precise, actionable feedback for the single repair attempt."""
    hints = []
    if "code display" in error or "Code highlight" in error:
        try:
            data = json.loads(raw) if isinstance(raw, str) else {}
            code = (data.get("code_scene") or {}).get("code", "")
            lines = code.splitlines()
            hints.append(f"Your code has {len(lines)} lines, longest {max(map(len, lines), default=0)} characters; "
                         "required: 1-12 lines, each at most 60 characters, and every step lines value "
                         "between 1 and the number of lines.")
        except (ValueError, AttributeError, TypeError):
            hints.append("Code must be 1-12 lines of at most 60 characters.")
    if "requires center" in error:
        hints.append("Every labelled diagram needs a non-empty center; use layout flow (no center) for processes.")
    if "requires subject programming" in error:
        hints.append("Use subject programming with a code_scene and a flow diagram_scene.")
    if "must not use" in error:
        hints.append("Remove code scenes and use a non-programming subject.")
    return " ".join(hints)


def merge_title_card(raw: str) -> str:
    """Turn the generation shape (title_card + scenes) into the Lesson content shape; scene ids become s1..sN."""
    data = json.loads(raw)
    if not isinstance(data, dict) or not isinstance(data.get("title_card"), dict):
        raise ValueError("Expected a title_card object")
    if data.get("subject") == "programming":
        parts = [data.pop(k, None) for k in ("code_scene", "diagram_scene")]
        scenes = [data.pop("title_card"), *parts]
    elif isinstance(data.get("scenes"), list):
        scenes = [data.pop("title_card"), *data["scenes"]]
    else:
        raise ValueError("Expected a scenes array")
    data["scenes"] = scenes
    for number, scene in enumerate(data["scenes"], 1):  # ids are bookkeeping, assigned here
        if isinstance(scene, dict):
            scene["id"] = f"s{number}"
    return json.dumps(data)


class PlanResult(ContractModel):
    request: PlanRequest
    model: str
    lesson: Lesson | None = None
    error: PlanError | None = None
    attempts: int = 0
    generation_seconds: float = 0
    cached: bool = False
    notes: list[str] = Field(default_factory=list)


def lesson_key(request: PlanRequest, model: str) -> str:
    """Content-addressed lesson id; also used by Task 5 to name the lesson before planning."""
    subject = effective_subject(request.topic, request.subject)
    return plan_key(request.topic, request.level, request.target_seconds, model,
                    f"{PROMPT_VERSION}:{subject or 'auto'}", "1.0")


def plan_lesson(request: PlanRequest, settings: Settings, *,
                transport: httpx.BaseTransport | None = None,
                debug_dir: Path = ROOT / "scratch" / "planner") -> PlanResult:
    """Return validated English lesson or structured error; never substitute a demo.

    Requested translation language remains in result.request.language. The Lesson
    language stays en. Only successful validated plans enter the content cache.
    """
    profile = settings.resolve_profile()
    model = settings.planner_model(profile)
    result = PlanResult(request=request, model=model)
    subject = effective_subject(request.topic, request.subject)
    key = lesson_key(request, model)
    cache = Cache(settings.cache_dir)
    path = cache.lesson_dir(key) / "plan.json"
    metadata = dict(schema_version="1.0", lesson_id=key, topic=request.topic,
                    level=request.level, target_seconds=request.target_seconds,
                    language="en", source="llm", model=model, prompt_version=PROMPT_VERSION)
    try:
        if path.exists():
            try:
                lesson = cache.read_model(path, Lesson)
                if any(getattr(lesson, k) != v for k, v in metadata.items()):
                    raise ValueError("Cached plan metadata mismatch")
                result.lesson = validate_plan(lesson, subject)
                result.cached = True
                return result
            except (ValueError, SyntaxError):
                result.notes.append("Invalid cached plan ignored")
        with httpx.Client(base_url=settings.ollama_url, timeout=180,
                          trust_env=False, follow_redirects=False, transport=transport) as client:
            show = client.post("/api/show", json={"model": model})
            show.raise_for_status()
            info = show.json()
            if not isinstance(info, dict):
                raise ValueError("Ollama /api/show must return an object")
            capabilities = info.get("capabilities", [])
            body = {"model": model, "stream": False,
                    "format": output_schema(subject), "keep_alive": "10m",
                    "options": {"temperature": 0.3, "num_predict": 3500,
                                **({"num_gpu": 0} if profile == "cpu" else {})}}
            if model.lower().startswith("qwen3"):
                if "thinking" in capabilities:
                    body["think"] = False
                elif "instruct" in model.lower() and "completion" in capabilities:
                    result.notes.append("Non-thinking instruct model: think option omitted based on capabilities")
                else:
                    result.error = PlanError(code="unsupported_options", message="Cannot establish Qwen3 think:false support from /api/show")
                    return result
            messages = [{"role": "system", "content": system_prompt(subject)},
                        {"role": "user", "content": json.dumps({
                            "topic": request.topic, "level": request.level,
                            "target_seconds": request.target_seconds,
                            "subject": subject or "unspecified",
                            "narration_word_range": list(narration_range(request.target_seconds))})}]
            for attempt in range(1, 3):
                result.attempts = attempt
                start = perf_counter()
                try:
                    response = client.post("/api/chat", json={**body, "messages": messages})
                finally:
                    result.generation_seconds += perf_counter() - start
                response.raise_for_status()
                envelope = response.json()
                if not isinstance(envelope, dict) or not isinstance(envelope.get("message", {}), dict):
                    raise ValueError("Malformed Ollama response envelope")
                if envelope.get("error"):
                    result.error = PlanError(code="ollama_error", message=str(envelope["error"])[:2000])
                    return result
                raw = envelope.get("message", {}).get("content", "")
                try:
                    if not isinstance(raw, str):
                        raise ValueError("Ollama message.content must be a string")
                    if envelope.get("done") is not True or envelope.get("done_reason") == "length":
                        raise ValueError("Ollama response incomplete or hit token limit")
                    if envelope.get("message", {}).get("thinking"):
                        raise ValueError("Ollama returned thinking despite disabled thinking")
                    content = PlanContent.model_validate_json(merge_title_card(raw), strict=True)
                    lesson = Lesson.model_validate({**content.model_dump(exclude_unset=True), **metadata})
                    result.lesson = validate_plan(lesson, subject)
                    cache.write_json(path, result.lesson.model_dump(mode="json", exclude_unset=True))
                    return result
                except (ValueError, SyntaxError, ValidationError) as exc:
                    debug_dir.mkdir(parents=True, exist_ok=True)
                    debug = debug_dir / f"{key}-{uuid4().hex[:8]}-attempt{attempt}.json"
                    error = str(exc)[:6000]
                    debug.write_text(json.dumps({"model": model, "request": request.model_dump(),
                                     "raw": raw, "validation_error": error}, ensure_ascii=False, indent=2), encoding="utf-8")
                    result.notes.append(f"Validation failure saved to {debug}")
                    messages.extend([{"role": "assistant", "content": raw if isinstance(raw, str) else str(raw)},
                                     {"role": "user", "content": "Repair this JSON. Return full corrected content only. Errors: " + error
                                     + " " + repair_hint(error, raw)}])
            result.error = PlanError(code="validation_failed", message=error)
    except httpx.TimeoutException:
        result.error = PlanError(code="timeout", message="Local Ollama call timed out (180 seconds); no further retry")
    except httpx.HTTPStatusError as exc:
        result.error = PlanError(code="ollama_rejected", message=f"HTTP {exc.response.status_code}: {exc.response.text[:2000]}. No options silently removed.")
    except httpx.RequestError as exc:
        result.error = PlanError(code="unavailable", message=f"Local Ollama unavailable: {exc}")
    except (ValueError, OSError) as exc:
        result.lesson = None
        result.error = PlanError(code="planner_error", message=str(exc))
    return result
