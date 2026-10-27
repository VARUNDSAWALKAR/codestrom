"""Task 3 command: python -m backend.export_lesson (needs the backend running on 127.0.0.1:8000)."""
from __future__ import annotations

from .app.config import get_settings

import json
from .app.cache import Cache, variant_key
from .app.export.render import ExportContext, run_export
from .app.jobs import JobRecord, run_measured_stage


def export(lesson_id: str = "fallback-python-loop", variant: str = variant_key("en", "female", 1)) -> ExportContext:
    settings = get_settings()
    cache = Cache(settings.cache_dir)
    cache.initialize()
    ctx = ExportContext(job=JobRecord(lesson_id=lesson_id, variant=variant, device_profile="cpu"),
                        language=variant.split("-")[0], settings=settings, cache=cache)
    run_measured_stage(ctx, "export", run_export, cache)
    stage = next(s for s in ctx.job.stages if s.name == "export")
    print(json.dumps({"stage": "export", **stage.model_dump(), "mp4": f"/media/{lesson_id}/{variant}/lesson.mp4"}), flush=True)
    return ctx


if __name__ == "__main__":
    export()
