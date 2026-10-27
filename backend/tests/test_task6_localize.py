"""Localization tests run without importing or loading translation/TTS models."""
from __future__ import annotations
import json
from pathlib import Path
from threading import Event, Thread
import time

import pytest

from backend.app.config import ROOT, Settings
from backend.app.localize import localize_lesson
from backend.app.localize import model
from backend.app.localize.terms import mask, restore
from backend.app.localize.translate import fields, fingerprint, TAGS, verify_structure
from backend.app.planner.schema import Lesson


class Fake:
    identity = "fake-translator-v1"
    def __init__(self, transform=None):
        self.calls = []
        self.transform = transform

    def translate(self, texts, target_tag, *, num_beams):
        self.calls.append((texts, target_tag, num_beams))
        if self.transform:
            return [self.transform(t, num_beams) for t in texts]
        # Preserve placeholders, replace every other English word with script text.
        import re
        word = "ಕನ್ನಡ" if target_tag == "kan_Knda" else "हिन्दी"
        return [re.sub(r"<ID\d+>|[A-Za-z]+", lambda m: m[0] if m[0].startswith("<ID") else word, t) for t in texts]


@pytest.fixture
def lesson():
    return Lesson.model_validate_json((ROOT / "data/samples/planner/water_cycle.json").read_text(encoding="utf-8"))


@pytest.fixture
def settings(tmp_path):
    return Settings(device="cpu", cache_dir=tmp_path / "cache")


def test_protected_prose_and_round_trip():
    source = "Use range(3), x = 2 and 9.8 m/s² with H₂O, user_id and binarySearch."
    item = mask(source, ["range", "H₂O"])
    assert item.eligible and "Use" in item.masked and "with" in item.masked
    assert all(any(term in span for span in item.spans) for term in ("range(3)", "x = 2", "m/s²", "H₂O", "user_id", "binarySearch"))
    assert "9.8 m/s²" in item.spans
    assert restore(item.masked, item) == source
    assert not mask("i = 0", []).eligible
    literal = mask("Use <ID101> and range(3)", [])
    assert restore(literal.masked, literal) == literal.source
    with pytest.raises(ValueError):
        restore(item.masked + item.placeholders[0], item)


def test_localizes_table_and_preserves_structure(lesson, settings):
    before = lesson.model_dump(mode="json")
    result = localize_lesson(lesson, "hi", settings, Fake())
    assert result.localization_quality == "complete" and result.english_fraction == 0
    assert result.lesson.title != lesson.title and result.lesson.language == "hi"
    verify_structure(lesson, result.lesson)
    assert lesson.model_dump(mode="json") == before
    for d in result.diagnostics:
        assert all(span in d.target for span in d.protected)
        assert d.status == "protected" or d.script_ratio >= 0.7


def test_batches_deduplicates_and_cache_reuses(lesson, settings):
    fake = Fake()
    first = localize_lesson(lesson, "kn", settings, fake)
    assert all(len(texts) <= 16 for texts, _, _ in fake.calls)
    assert sum(len(texts) for texts, _, _ in fake.calls) == first.stats["unique_strings"]
    assert len(first.diagnostics) > first.stats["unique_strings"]
    count = len(fake.calls)
    second = localize_lesson(lesson, "kn", settings, fake)
    assert second.cached and len(fake.calls) == count
    third = localize_lesson(lesson, "kn", settings, fake, voice="male", speed=0.85)
    assert not third.cached and third.stats["cache_hits"] == third.stats["unique_strings"]
    assert len(fake.calls) == count


def test_cache_invalidates_on_plan_model_and_metadata(lesson, settings):
    fake = Fake()
    first = localize_lesson(lesson, "hi", settings, fake)
    folder = settings.cache_dir / "lessons" / lesson.lesson_id / "hi-female-1"
    original_plan = lesson.model_dump()
    path = folder / "localization.json"
    entry = json.loads(path.read_text(encoding="utf-8"))
    entry["metadata"]["version"] = "stale"
    path.write_text(json.dumps(entry), encoding="utf-8")
    assert not localize_lesson(lesson, "hi", settings, fake).cached
    (folder / "lesson.json").write_text("{}")
    assert not localize_lesson(lesson, "hi", settings, fake).cached
    changed = lesson.model_copy(deep=True, update={"title": "Water Cycle Explained"})
    assert not localize_lesson(changed, "hi", settings, fake).cached
    fake.identity = "fake-v2"
    assert not localize_lesson(changed, "hi", settings, fake).cached
    assert lesson.model_dump() == original_plan


def test_string_cache_checksum_rejects_corruption(lesson, settings):
    fake = Fake()
    localize_lesson(lesson, "hi", settings, fake)
    folder = settings.cache_dir / "lessons" / lesson.lesson_id / "hi-female-1"
    # A different variant misses the variant cache and must inspect string records.
    path = settings.cache_dir / "translations/hi.json"
    records = json.loads(path.read_text(encoding="utf-8"))
    for entry in records.values():
        entry["text"] = "corrupt"
    path.write_text(json.dumps(records), encoding="utf-8")
    before = len(fake.calls)
    result = localize_lesson(lesson, "hi", settings, fake, voice="male")
    assert result.stats["cache_hits"] == 0 and len(fake.calls) > before


def test_missing_placeholder_retries_unmasked_then_falls_back(lesson, settings):
    fake = Fake(lambda text, beams: "यह उदाहरण है।")
    result = localize_lesson(lesson, "hi", settings, fake)
    protected = [d for d in result.diagnostics if d.protected and d.status == "fallback"]
    assert protected and all(d.reason == "protected_span_restore_failed" for d in protected)
    assert result.stats["restore_retries"] > 0
    assert result.localization_quality == "partial"
    assert any(d.status == "translated" for d in result.diagnostics)


def test_unmasked_retry_accepted_only_with_verbatim_terms(lesson, settings):
    import re
    def translate(text, beams):
        if "<ID" in text:
            return "यह उदाहरण है।"  # intentionally destroy placeholders
        result = text
        for term in lesson.keep_terms:
            result = result.replace(term, f"<{term}>")
        return re.sub(r"<[^>]+>|[A-Za-z]+", lambda m: m[0][1:-1] if m[0].startswith("<") else "हिन्दी", result)
    result = localize_lesson(lesson, "hi", settings, Fake(translate))
    assert result.stats["restore_retries"] > 0
    assert result.english_fraction == 0
    assert all(d.status != "fallback" for d in result.diagnostics)


def test_script_retry_once_beam_five_then_english_fraction(lesson, settings):
    fake = Fake(lambda text, beams: text)
    result = localize_lesson(lesson, "hi", settings, fake)
    assert result.english_fraction == 1 and result.localization_quality == "partial"
    assert {beams for _, _, beams in fake.calls} == {2, 5}
    assert result.stats["script_failures"] == result.stats["unique_strings"]
    assert all(d.reason == "script_check_failed" for d in result.diagnostics if d.status == "fallback")


def test_script_recovery_and_display_lengths_warn_only(lesson, settings):
    base = Fake()
    fake = Fake(lambda text, beams: text if beams == 2 else base.translate([text], "hin_Deva", num_beams=5)[0] + " हिन्दी" * 40)
    result = localize_lesson(lesson, "hi", settings, fake)
    assert result.localization_quality == "complete" and result.warnings
    assert any("localized length" in warning for warning in result.warnings)


def test_unknown_string_field_warning(lesson):
    data = lesson.model_dump()
    data["scenes"][0]["new_label"] = "Future label"
    warnings = []
    list(fields(data, warnings))
    assert any("new_label" in warning for warning in warnings)


def test_formula_fragments_units_and_code_only_beats(settings):
    lesson = Lesson.model_validate_json((ROOT / "data/samples/newtons_second_law.en.json").read_text(encoding="utf-8"))
    lesson = lesson.model_copy(deep=True, update={"lesson_id": "123abc456def"})
    result = localize_lesson(lesson, "hi", settings, Fake())
    for source, target in zip(lesson.scenes, result.lesson.scenes):
        assert source.expression == target.expression
        if source.type == "formula":
            for a, b in zip(source.steps, target.steps):
                assert a.text == b.text
    item = mask("A mass of 2 kg and force of 3 N.", [])
    assert any("kg" in span for span in item.spans) and any("N" in span for span in item.spans) and item.eligible
    assert not mask("A loop repeats.", []).spans  # article A is not an ampere unit
    for scene in lesson.scenes:
        if scene.narration:
            scene.narration = "range(3)"
        for step in scene.steps:
            step.narration = "i = 0"
    protected = localize_lesson(lesson, "hi", settings, Fake(lambda text, beams: text))
    assert protected.stats["eligible_narration_beats"] == 0
    assert protected.english_fraction == 0


def test_script_retry_losing_placeholder_gets_unmasked_once(lesson, settings):
    def translate(text, beams):
        if beams == 5:
            return "यह उदाहरण है।"  # loss occurs only on the script retry
        if "<ID" in text:
            return text  # English fails script check and proceeds to beam 5
        return "यह उदाहरण है।"
    result = localize_lesson(lesson, "hi", settings, Fake(translate))
    assert result.stats["restore_retries"] > 0
    assert any(d.reason == "protected_span_restore_failed" for d in result.diagnostics)


@pytest.mark.parametrize("lang", list(TAGS))
def test_all_translation_tags(lesson, settings, lang):
    # Check tag forwarding independently of script output for bonus languages.
    fake = Fake(lambda text, beams: text)
    result = localize_lesson(lesson, lang, settings, fake)
    assert {tag for _, tag, _ in fake.calls} == {TAGS[lang]}
    assert result.lesson.language == lang


def test_bad_batch_never_publishes_localized_lesson(lesson, settings):
    class Bad(Fake):
        def translate(self, *args, **kwargs):
            return []
    with pytest.raises(ValueError, match="batch shape"):
        localize_lesson(lesson, "hi", settings, Bad())
    assert not list(settings.cache_dir.rglob("lesson.json"))


def test_atomic_commit_failure_is_rejected(lesson, settings, monkeypatch):
    from backend.app.cache import Cache
    original = Cache.write_json
    def fail_commit(self, path, value):
        if path.name == "localization.json":
            raise OSError("Simulated interrupted publication")
        original(self, path, value)
    with monkeypatch.context() as context:
        context.setattr(Cache, "write_json", fail_commit)
        with pytest.raises(OSError):
            localize_lesson(lesson, "hi", settings, Fake())
    result = localize_lesson(lesson, "hi", settings, Fake())
    assert not result.cached  # orphan lesson.json is never a localization cache hit


def test_finished_variant_requires_current_source_provenance(lesson, settings, monkeypatch):
    from backend.app.cache import Cache
    from backend.app.localize import translate
    cache = Cache(settings.cache_dir)
    fake = Fake()
    monkeypatch.setattr(translate, "get_translator", lambda config: fake)
    plan_path = cache.lesson_dir(lesson.lesson_id) / "plan.json"
    cache.write_json(plan_path, lesson.model_dump(mode="json", exclude_unset=True))
    localize_lesson(lesson, "hi", settings, fake)
    folder = cache.lesson_dir(lesson.lesson_id, "hi-female-1")
    assert translate.localization_artifact_valid(folder, settings)
    source = lesson.model_copy(update={"title": "Water Cycle Changed"})
    cache.write_json(plan_path, source.model_dump(mode="json", exclude_unset=True))
    assert not translate.localization_artifact_valid(folder, settings)


def test_non_english_export_verification_rechecks_changed_provenance(lesson, settings):
    from dataclasses import replace
    from backend.app.cache import Cache
    from backend.app.orchestrator import Orchestrator
    from backend.app.pipeline_ops import production_ops
    cache = Cache(settings.cache_dir)
    folder = cache.lesson_dir(lesson.lesson_id, "hi-female-1")
    folder.mkdir(parents=True)
    (folder / "lesson.mp4").write_bytes(b"test-only-file-no-render")
    checked = []
    ops = replace(production_ops(settings=settings), export_complete=lambda *args: checked.append(True) or True)
    orchestrator = Orchestrator(settings, cache, "cpu", ops)
    assert orchestrator.export_verified(folder) and orchestrator.export_verified(folder)
    assert len(checked) == 1
    cache.write_json(folder.parent / "plan.json", {"new": "canonical source"})
    assert orchestrator.export_verified(folder) and len(checked) == 2
    cache.write_json(folder / "localization.json", {"new": "localization commit"})
    assert orchestrator.export_verified(folder) and len(checked) == 3


def test_release_waits_for_operation_lock(settings, monkeypatch):
    instance = model.get_translator(settings)
    entered, finished = Event(), Event()
    monkeypatch.setattr(instance, "release", lambda: (entered.set(), finished.set()))
    with model.OPERATION_LOCK:
        thread = Thread(target=model.release_translator, args=(settings,))
        thread.start()
        assert not entered.wait(0.03)
    thread.join(2)
    assert finished.is_set()


@pytest.mark.parametrize("name", ["water_cycle", "binary_search", "python_for_loop"])
@pytest.mark.parametrize("lang", ["hi", "kn"])
def test_real_localized_fixtures_validate_without_models(name, lang):
    from backend.app.localize.translate import LocalizeResult, _validate_result
    root = ROOT / "data/samples"
    source = Lesson.model_validate_json((root / f"planner/{name}.json").read_text(encoding="utf-8"))
    stored = Lesson.model_validate_json((root / f"localized/{name}.{lang}.json").read_text(encoding="utf-8"))
    result = LocalizeResult.model_validate_json((root / f"localized/{name}.{lang}.localization.json").read_text(encoding="utf-8"))
    assert result.lesson == stored and stored.lesson_id == source.lesson_id
    _validate_result(source, result, lang)
    assert result.english_fraction <= 0.2
