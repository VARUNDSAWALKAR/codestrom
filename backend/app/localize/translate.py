"""Validated localization, protected prose translation and atomic cache publication."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from time import perf_counter
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ..cache import Cache, variant_key
from ..config import Settings
from ..planner.schema import Lesson
from .model import OPERATION_LOCK, Translator, get_translator, release_translator
from .terms import MASK_VERSION, TOKEN, Masked, mask, outside_protected, protected_verbatim, restore

LOCALIZATION_VERSION = "localize-v1"
TAGS = {"hi": "hin_Deva", "kn": "kan_Knda", "ta": "tam_Taml", "te": "tel_Telu",
        "bn": "ben_Beng", "mr": "mar_Deva"}
BLOCKS = {"hi": (0x0900, 0x097F), "mr": (0x0900, 0x097F), "kn": (0x0C80, 0x0CFF),
          "ta": (0x0B80, 0x0BFF), "te": (0x0C00, 0x0C7F), "bn": (0x0980, 0x09FF)}
FIELDS = {"lesson": ("title",), "scene": ("heading", "narration", "subtitle", "center"),
          "step": ("text", "note", "narration")}
KNOWN = {"lesson": set(Lesson.model_fields),
         "scene": {"id", "type", "heading", "narration", "steps", "subtitle", "code", "code_language", "layout", "center", "expression"},
         "step": {"text", "note", "narration", "lines", "output", "in_expression"}}


class Boundary(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Diagnostic(Boundary):
    path: str
    status: Literal["translated", "protected", "fallback"]
    source: str
    target: str
    protected: list[str] = Field(default_factory=list)
    reason: str = ""
    script_ratio: float = 1.0


class LocalizeResult(Boundary):
    lesson: Lesson
    localization_quality: Literal["complete", "partial"]
    english_fraction: float = Field(ge=0, le=1)
    diagnostics: list[Diagnostic]
    warnings: list[str]
    stats: dict[str, float | int]
    metadata: dict[str, str]
    cached: bool = False


def fingerprint(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def source_fingerprint(lesson: Lesson) -> str:
    return fingerprint(lesson.model_dump(mode="json", exclude_unset=True))


def script_ratio(text: str, item: Masked, lang: str) -> float:
    letters = [c for c in outside_protected(text, item) if c.isalpha()]
    lo, hi = BLOCKS[lang]
    return sum(lo <= ord(c) <= hi for c in letters) / len(letters) if letters else 0.0


def fields(data: dict, warnings: list[str]):
    """Yield mutable owner/key/path without changing the scene or step ordering."""
    def selected(owner, kind, prefix):
        for key, value in owner.items():
            if key not in KNOWN[kind] and isinstance(value, str) and value:
                warnings.append(f"Unknown user-facing string field {prefix}{key}; retained unchanged")
        for key in FIELDS[kind]:
            if owner.get(key):
                yield owner, key, f"{prefix}{key}"
    yield from selected(data, "lesson", "")
    for i, scene in enumerate(data["scenes"]):
        yield from selected(scene, "scene", f"scenes.{i}.")
        for j, step in enumerate(scene["steps"]):
            yield from selected(step, "step", f"scenes.{i}.steps.{j}.")


def technical_terms(lesson: Lesson) -> list[str]:
    terms = list(lesson.keep_terms)
    keywords = {"for", "in", "if", "else", "while", "return", "and", "or", "not", "is", "True", "False", "None", "def"}
    for scene in lesson.scenes:
        terms.extend(x for x in re.findall(r"\b[A-Za-z_][A-Za-z_0-9]*\b", scene.code) if x not in keywords)
        # Formula highlight fragments must continue to match the unchanged expression.
        terms.extend(re.findall(r"\b[A-Za-z_][A-Za-z_0-9]*\b", scene.expression))
    return sorted(set(terms), key=len, reverse=True)


def structural_shape(lesson: Lesson) -> dict:
    # Persisted Pydantic models include defaults; compare semantic structure,
    # not the caller's fields_set bookkeeping.
    data = lesson.model_dump(mode="json")
    data.pop("language", None)
    data.pop("warnings", None)
    for owner, key, _ in fields(data, []):
        owner[key] = "<text>"
    return data


def verify_structure(source: Lesson, localized: Lesson) -> None:
    if structural_shape(source) != structural_shape(localized):
        raise ValueError("Localization changed protected lesson structure")


def _read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def _cache_spec(item: Masked, tag: str, identity: str) -> dict:
    return {"masked_source": item.masked, "target_tag": tag, "model": identity,
            "version": LOCALIZATION_VERSION, "masking": item.fingerprint, "mask_version": MASK_VERSION}


def _good(text: str, item: Masked, lang: str) -> bool:
    return (bool(text.strip()) and protected_verbatim(text, item)
            and not TOKEN.search(outside_protected(text, item)) and script_ratio(text, item, lang) >= 0.7)


def localize_lesson(lesson: Lesson, lang: str, settings: Settings,
                    translator: Translator | None = None, *, voice: str = "female", speed: float = 1.0) -> LocalizeResult:
    """Translate a validated canonical English plan; callers enforce production approval.

    The optional variant arguments only select artifact paths. The four positional
    arguments remain the public API. Over-threshold results are retained for review;
    the production bridge rejects them before TTS.
    """
    if lesson.language != "en" or lang not in TAGS:
        raise ValueError("Localization requires an English source and a supported Indic target")
    # One process-wide transaction prevents cross-instance string-cache lost updates.
    with OPERATION_LOCK:
        try:
            return _localize(lesson, lang, settings, translator or get_translator(settings), voice, speed)
        finally:
            # _localize persisted its caches/artifacts before returning. On failure,
            # no successful model user can still hold this operation lock.
            if translator is None and settings.low_ram:
                release_translator(settings)


def _localize(lesson: Lesson, lang: str, settings: Settings, translator: Translator,
              voice: str, speed: float) -> LocalizeResult:
    started = perf_counter()
    cache = Cache(settings.cache_dir)
    variant = variant_key(lang, voice, speed)
    folder = cache.lesson_dir(lesson.lesson_id, variant)
    metadata = {"source_plan": source_fingerprint(lesson), "target_tag": TAGS[lang], "language": lang,
                "model": translator.identity, "version": LOCALIZATION_VERSION, "mask_version": MASK_VERSION,
                "variant": variant, "lesson_id": lesson.lesson_id}
    existing = _read_json(folder / "localization.json")
    if existing.get("metadata") == metadata:
        try:
            result = LocalizeResult.model_validate(existing["result"])
            stored = Lesson.model_validate_json((folder / "lesson.json").read_text(encoding="utf-8"))
            if (existing["sha256"] == fingerprint(existing["result"]) and result.metadata == metadata
                    and stored == result.lesson and stored.language == lang):
                verify_structure(lesson, stored)
                _validate_result(lesson, result, lang)
                return result.model_copy(update={"cached": True})
        except (OSError, ValueError, KeyError, TypeError):
            pass

    warnings: list[str] = []
    data = lesson.model_dump(mode="json", exclude_unset=True)
    terms = technical_terms(lesson)
    locations = [(owner, key, path, mask(owner[key], terms)) for owner, key, path in fields(data, warnings)]
    unique = {item.source: item for _, _, _, item in locations if item.eligible}
    string_path = cache.translations / f"{lang}.json"
    records = _read_json(string_path)
    outcomes: dict[str, tuple[str, str]] = {}
    stats: dict[str, float | int] = {"unique_strings": len(unique), "cache_hits": 0, "batches": 0,
                                   "model_strings": 0, "restore_retries": 0, "script_retries": 0,
                                   "script_failures": 0, "protected_fields": 0}

    def batches(items: list[Masked], *, unmasked: bool = False, beams: int = 2):
        for start in range(0, len(items), 16):
            chunk = items[start:start + 16]
            output = translator.translate([x.source if unmasked else x.masked for x in chunk], TAGS[lang], num_beams=beams)
            if len(output) != len(chunk) or any(not isinstance(x, str) for x in output):
                raise ValueError("Translator returned an invalid batch shape")
            stats["batches"] += 1
            stats["model_strings"] += len(chunk)
            yield from zip(chunk, output)

    pending = []
    for item in unique.values():
        spec = _cache_spec(item, TAGS[lang], metadata["model"])
        entry = records.get(fingerprint(spec), {})
        if (isinstance(entry, dict) and entry.get("spec") == spec and isinstance(entry.get("text"), str)
                and entry.get("sha256") == fingerprint([spec, entry["text"]]) and _good(entry["text"], item, lang)):
            outcomes[item.source] = (entry["text"], "")
            stats["cache_hits"] += 1
        else:
            pending.append(item)

    unmasked_retry, script_retry = [], []
    for item, output in batches(pending):
        try:
            restored = restore(output.strip(), item)
        except ValueError:
            unmasked_retry.append(item)
            continue
        if _good(restored, item, lang):
            outcomes[item.source] = (restored, "")
        else:
            script_retry.append((item, False))
    stats["restore_retries"] = len(unmasked_retry)
    for item, output in batches(unmasked_retry, unmasked=True):
        output = output.strip()
        if protected_verbatim(output, item) and not TOKEN.search(outside_protected(output, item)):
            if _good(output, item, lang):
                outcomes[item.source] = (output, "")
            else:
                script_retry.append((item, True))
        else:
            outcomes[item.source] = (item.source, "protected_span_restore_failed")
    stats["script_retries"] = len(script_retry)
    late_restore_retry = []
    for use_unmasked in (False, True):
        for item, output in batches([i for i, raw in script_retry if raw == use_unmasked], unmasked=use_unmasked, beams=5):
            try:
                restored = output.strip() if use_unmasked else restore(output.strip(), item)
            except ValueError:
                late_restore_retry.append(item)
                continue
            if _good(restored, item, lang):
                outcomes[item.source] = (restored, "")
            else:
                outcomes[item.source] = (item.source, "script_check_failed")
                stats["script_failures"] += 1
    # A beam-5 script retry may itself lose a placeholder. It still gets its one
    # unmasked preservation retry; no item takes that retry twice.
    stats["restore_retries"] += len(late_restore_retry)
    for item, output in batches(late_restore_retry, unmasked=True):
        if _good(output.strip(), item, lang):
            outcomes[item.source] = (output.strip(), "")
        else:
            outcomes[item.source] = (item.source, "protected_span_restore_failed")

    for item in pending:
        text, reason = outcomes[item.source]
        if not reason:
            spec = _cache_spec(item, TAGS[lang], metadata["model"])
            records[fingerprint(spec)] = {"spec": spec, "text": text, "sha256": fingerprint([spec, text])}

    diagnostics = []
    for owner, key, path, item in locations:
        if not item.eligible:
            target, reason, status = item.source, "", "protected"
            stats["protected_fields"] += 1
        else:
            target, reason = outcomes[item.source]
            status = "fallback" if reason else "translated"
        owner[key] = target
        diagnostics.append(Diagnostic(path=path, source=item.source, target=target, status=status,
                                      protected=list(item.spans), reason=reason,
                                      script_ratio=script_ratio(target, item, lang) if item.eligible else 1.0))
        if reason:
            warnings.append(f"{path}: {reason}; retained English")
        limit = (70 if path == "title" else 60 if key == "heading" else 80 if key == "subtitle"
                 else 28 if key == "center" else 32 if key == "note" else 40 if key == "text" else None)
        if limit is not None and len(target) > limit:
            warnings.append(f"{path}: localized length {len(target)} exceeds display guide {limit}")
    narration = [d for d in diagnostics if d.path.endswith("narration") and d.status != "protected"]
    fallback = sum(d.status == "fallback" for d in narration)
    fraction = fallback / len(narration) if narration else 0.0
    data["language"] = lang
    data["warnings"] = [*lesson.warnings, *warnings]
    localized = Lesson.model_validate(data)
    verify_structure(lesson, localized)
    stats.update(eligible_narration_beats=len(narration), english_narration_beats=fallback,
                 fallback_fields=sum(d.status == "fallback" for d in diagnostics),
                 narration_char_expansion=sum(len(d.target) for d in narration) / max(1, sum(len(d.source) for d in narration)),
                 narration_word_expansion=sum(len(d.target.split()) for d in narration) / max(1, sum(len(d.source.split()) for d in narration)),
                 elapsed_ms=round((perf_counter() - started) * 1000))
    result = LocalizeResult(lesson=localized, metadata=metadata, diagnostics=diagnostics, warnings=warnings,
                            localization_quality="partial" if any(d.status == "fallback" for d in diagnostics) else "complete",
                            english_fraction=fraction, stats=stats)
    _validate_result(lesson, result, lang)
    # Each file is an atomic replacement; the checked envelope is the final commit
    # record. Readers reject a missing/stale envelope or any lesson/hash mismatch.
    cache.write_json(string_path, records)
    cache.write_json(folder / "lesson.json", localized)
    payload = result.model_dump(mode="json")
    cache.write_json(folder / "localization.json", {"metadata": metadata, "result": payload, "sha256": fingerprint(payload)})
    return result


def _validate_result(source: Lesson, result: LocalizeResult, lang: str) -> None:
    verify_structure(source, result.lesson)
    terms = technical_terms(source)
    source_data = source.model_dump(mode="json", exclude_unset=True)
    target_data = result.lesson.model_dump(mode="json", exclude_unset=True)
    expected = {p: owner[key] for owner, key, p in fields(source_data, [])}
    actual = {p: owner[key] for owner, key, p in fields(target_data, [])}
    if len(result.diagnostics) != len(expected) or set(d.path for d in result.diagnostics) != set(expected):
        raise ValueError("Incomplete localization diagnostics")
    eligible = fallback = 0
    for d in result.diagnostics:
        item = mask(expected[d.path], terms)
        if d.source != expected[d.path] or d.target != actual[d.path] or d.protected != list(item.spans):
            raise ValueError("Localization diagnostic mismatch")
        if not item.eligible:
            if d.status != "protected" or d.target != d.source:
                raise ValueError("Protected-only field changed")
        elif d.status == "translated":
            if not _good(d.target, item, lang):
                raise ValueError("Cached translation failed script/protection checks")
        elif d.status != "fallback" or d.target != d.source or not d.reason:
            raise ValueError("Invalid localization fallback")
        if d.path.endswith("narration") and item.eligible:
            eligible += 1
            fallback += d.status == "fallback"
    fraction = fallback / eligible if eligible else 0.0
    quality = "partial" if any(d.status == "fallback" for d in result.diagnostics) else "complete"
    if result.english_fraction != fraction or result.localization_quality != quality:
        raise ValueError("Localization quality metadata mismatch")


def localization_artifact_valid(folder: Path, settings: Settings) -> bool:
    """Check provenance before serving a fully cached production variant/MP4.

    This performs no inference or model initialization. The canonical plan may
    have changed since export, so MP4 validity alone is insufficient.
    """
    try:
        source = Lesson.model_validate_json((folder.parent / "plan.json").read_text(encoding="utf-8"))
        envelope = _read_json(folder / "localization.json")
        result = LocalizeResult.model_validate(envelope["result"])
        stored = Lesson.model_validate_json((folder / "lesson.json").read_text(encoding="utf-8"))
        lang = stored.language
        expected = {"source_plan": source_fingerprint(source), "target_tag": TAGS[lang], "language": lang,
                    "model": get_translator(settings).identity, "version": LOCALIZATION_VERSION,
                    "mask_version": MASK_VERSION, "variant": folder.name, "lesson_id": source.lesson_id}
        if (source.language != "en" or stored.lesson_id != source.lesson_id or result.lesson != stored
                or result.metadata != expected or envelope["metadata"] != expected
                or envelope["sha256"] != fingerprint(envelope["result"])
                or result.english_fraction > settings.localize_max_english_fraction):
            return False
        _validate_result(source, result, lang)
        return True
    except (OSError, ValueError, KeyError, TypeError):
        return False
