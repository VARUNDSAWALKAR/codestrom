"""Task 2 command: python -m backend.generate_narration (local fallback only)."""
from __future__ import annotations

from .app.config import ROOT, get_settings

import json
from .app.cache import Cache, variant_key
from .app.jobs import JobRecord, run_measured_stage
from .app.planner.schema import Lesson
from .app.speech.engines import NarrationContext, run_voice
from .app.speech.kokoro_engine import KokoroEngine
from .app.speech.audio import SAMPLE_RATE
from .app.timeline.build import run_timeline


def generate() -> NarrationContext:
    settings = get_settings()
    lesson = Lesson.model_validate_json((ROOT / "data" / "fallback" / "python_loop.en.json").read_text(encoding="utf-8"))
    cache = Cache(settings.cache_dir)
    cache.initialize()
    ctx = NarrationContext(job=JobRecord(lesson_id=lesson.lesson_id, variant=variant_key("en", "female", 1),
                           device_profile="cpu"), language="en", lesson=lesson, settings=settings,
                           cache=cache, engine=KokoroEngine(settings))
    for name, stage in (("voice", run_voice), ("timeline", run_timeline)):
        run_measured_stage(ctx, name, stage, cache)
        print(json.dumps({"stage": name, **next(s for s in ctx.job.stages if s.name == name).model_dump()}), flush=True)
    print(json.dumps({"output": str(cache.lesson_dir(lesson.lesson_id, ctx.job.variant)),
                      "speech_seconds_before_tempo": sum(c.samples for c in ctx.clips) / SAMPLE_RATE,
                      "lesson_seconds": ctx.timeline.duration_frames / ctx.timeline.fps,
                      "tempo": ctx.timeline.tempo, "warnings": ctx.job.warnings}), flush=True)
    return ctx


if __name__ == "__main__":
    generate()
