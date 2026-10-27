"""Task 5A orchestration: lesson request -> queued job -> stage wrappers around injected operations.

The wrappers own bookkeeping only (identity checks, preview verification, meta.json). The
actual planner, localiser, voice, timeline and export code is supplied as `PipelineOps`;
Task 5A tests inject mocks and Task 5B supplies the production operations. Nothing here
loads a model, calls Ollama or renders video.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any

from .cache import Cache, variant_key
from .config import DeviceProfile, Settings
from .contracts import LessonRequest
from .jobs import (
    STAGES, JobContext, JobRecord, JobRunner, PipelineError, StageFunction, StageName, StageRecord,
)
from .planner.ollama_client import PlanRequest, lesson_key
from .planner.schema import Lesson
from .planner.subject import effective_subject
from .planner.validate import validate_plan
from .timeline.schema import RenderProps, Timeline

# Files that make a lesson playable in the browser before the MP4 exists.
PREVIEW_FILES = ("lesson.json", "timeline.json", "props.json", "lesson.srt")
AUDIO_FILES = ("narration.m4a", "narration.wav")  # required whenever timeline.audio is not null
MOCK_MODEL = "mock-pipeline"


class BusyError(Exception):
    """The worker and its waiting queue are full."""

    def __init__(self, retry_after: int = 30) -> None:
        super().__init__("Lesson queue is full; try again shortly")
        self.retry_after = retry_after


class PipelineRun:
    """What an operation sees: the request, the working lesson, the variant folder, callbacks.

    Operations read `request`/`lesson`, write artifacts under `folder`, and may set `lesson`
    (plan, localize). The timeline operation calls `preview_ready()` right after the
    timeline, props and captions are persisted.
    """

    def __init__(self, orchestrator: Orchestrator, ctx: JobContext, settings: Settings, cache: Cache) -> None:
        assert ctx.request is not None
        self._orchestrator = orchestrator
        self.ctx = ctx
        self.request: LessonRequest = ctx.request
        self.settings = settings
        self.cache = cache
        self.lesson_id = ctx.job.lesson_id
        self.variant = ctx.job.variant
        self.language = ctx.language
        self.folder: Path = cache.lesson_dir(self.lesson_id, self.variant)
        self.mock = orchestrator.ops.mock
        self.lesson: Lesson | None = None  # English plan after `plan`, localized after `translate`
        self.data: dict[str, Any] = {}  # scratch space shared between operations of one job
        self.stage: StageName = "plan"

    def preview_ready(self) -> None:
        """Call immediately after timeline.json, props.json, lesson.json, lesson.srt (and audio) are persisted."""
        self._orchestrator.mark_preview_ready(self)

    def progress(self, value: float) -> None:
        self.ctx.job.progress = min(1.0, max(0.0, value))
        self._orchestrator.runner.update(self.ctx)

    def note(self, text: str) -> None:
        self._stage_record().note = text

    def warn(self, text: str) -> None:
        if text not in self.ctx.job.warnings:
            self.ctx.job.warnings.append(text)

    def cached(self, note: str) -> None:
        """Mark the current stage a cache hit (the planner does not set this itself)."""
        record = self._stage_record()
        record.status, record.note = "cached", note

    def skip(self, note: str) -> None:
        """Mark the current stage skipped (for example, mock export)."""
        record = self._stage_record()
        record.status, record.note = "skipped", note

    def _stage_record(self) -> StageRecord:
        return next(s for s in self.ctx.job.stages if s.name == self.stage)


Operation = Callable[[PipelineRun], None]


def default_validate(run: PipelineRun) -> None:
    assert run.lesson is not None
    try:
        validate_plan(run.lesson, effective_subject(run.request.topic, run.request.subject))
    except (ValueError, SyntaxError) as exc:
        raise PipelineError("validation_failed", str(exc)) from exc


@dataclass(frozen=True)
class PipelineOps:
    plan: Operation
    localize: Operation  # called only for non-English requests
    voice: Operation
    timeline: Operation
    export: Operation
    validate: Operation = default_validate
    precheck: Callable[[LessonRequest], None] | None = None  # cheap request check; raises PipelineError
    # Production: does lesson.mp4 really count as a finished export (props fingerprint + ffprobe)?
    # Without it (tests, mock) an existing non-empty MP4 counts.
    export_complete: Callable[[Path, Settings], bool] | None = None
    mock: bool = False


def read_preview(folder: Path) -> tuple[Lesson, Timeline]:
    """Load and cross-check the preview artifacts; raise PipelineError if any is missing or invalid."""

    def present(name: str) -> bool:
        path = folder / name
        return path.is_file() and path.stat().st_size > 0

    missing = [name for name in PREVIEW_FILES if not present(name)]
    if missing:
        raise PipelineError("preview_incomplete", f"Preview files missing: {', '.join(missing)}")
    try:
        lesson = Lesson.model_validate_json((folder / "lesson.json").read_text(encoding="utf-8"))
        timeline = Timeline.model_validate_json((folder / "timeline.json").read_text(encoding="utf-8"))
        RenderProps(lesson=lesson, timeline=timeline)
        props = RenderProps.model_validate_json((folder / "props.json").read_text(encoding="utf-8"))
    except ValueError as exc:
        raise PipelineError("preview_invalid", f"Preview files are invalid: {exc}") from exc
    if props.timeline != timeline or props.lesson != lesson:
        raise PipelineError("preview_invalid", "props.json does not match lesson.json and timeline.json")
    if timeline.audio is not None:
        absent = [name for name in AUDIO_FILES if not present(name)]
        if absent:
            raise PipelineError("preview_incomplete", f"Narration audio missing: {', '.join(absent)}")
    return lesson, timeline


def mp4_present(folder: Path) -> bool:
    path = folder / "lesson.mp4"
    return path.is_file() and path.stat().st_size > 0


class Orchestrator:
    def __init__(self, settings: Settings, cache: Cache, profile: DeviceProfile, ops: PipelineOps) -> None:
        self.settings, self.cache, self.profile, self.ops = settings, cache, profile, ops
        self.runner: JobRunner  # bound by bind(); the runner needs stages() first
        self._runs: dict[str, PipelineRun] = {}
        self._submit_lock = Lock()
        self._verify_lock = Lock()
        self._verified: dict[Path, tuple[tuple[int, int, int], bool]] = {}

    def bind(self, runner: JobRunner) -> None:
        self.runner = runner

    def stages(self) -> dict[StageName, StageFunction]:
        return {name: self._stage(name) for name in STAGES}

    # ---- submission -------------------------------------------------------------------
    def lesson_id_for(self, request: LessonRequest) -> str:
        model = MOCK_MODEL if self.ops.mock else self.settings.planner_model(self.profile)
        plan_request = PlanRequest(topic=request.topic, level=request.level, language=request.language,
                                   target_seconds=request.target_seconds, subject=request.subject)
        return lesson_key(plan_request, model)

    def submit(self, request: LessonRequest) -> tuple[JobRecord, bool]:
        """Return (job, cached). Raises PipelineError (rejected request) or BusyError."""
        if self.ops.precheck is not None:
            self.ops.precheck(request)
        lesson_id = self.lesson_id_for(request)
        variant = variant_key(request.language, request.voice, request.speed)
        with self._submit_lock:
            active = self.runner.find_active(lesson_id, variant)
            if active is not None:
                return active, False
            if self.is_complete(lesson_id, variant):
                return self.runner.add_completed(self._completed_job(lesson_id, variant)), True
            if self.runner.active_count >= 1 + self.settings.max_queued_jobs:
                raise BusyError()
            job = self.runner.submit(lesson_id, variant, request.language, request, mock=self.ops.mock)
            return job, False

    def export_verified(self, folder: Path) -> bool:
        """True when the folder holds a finished MP4: an existing file alone is not enough in production."""
        if not mp4_present(folder):
            return False
        if self.ops.export_complete is None:
            return True
        stat, sha = (folder / "lesson.mp4").stat(), folder / "props.sha1"
        key = (stat.st_mtime_ns, stat.st_size, sha.stat().st_mtime_ns if sha.is_file() else 0)
        with self._verify_lock:
            known = self._verified.get(folder)
            if known is None or known[0] != key:  # unchanged files are not re-probed on every GET
                known = self._verified[folder] = (key, self.ops.export_complete(folder, self.settings))
            return known[1]

    def is_complete(self, lesson_id: str, variant: str) -> bool:
        """A variant is cached only when the preview verifies on disk and the export is verified."""
        folder = self.cache.lesson_dir(lesson_id, variant)
        if not self.export_verified(folder):
            return False
        try:
            read_preview(folder)
        except PipelineError:
            return False
        return True

    def _completed_job(self, lesson_id: str, variant: str) -> JobRecord:
        stages = [StageRecord(name=name, status="cached", note="Served from cache") for name in STAGES]
        return JobRecord(lesson_id=lesson_id, variant=variant, status="done", playable=True, preview_ready=True,
                         export_status="completed", progress=1.0, stages=stages, device_profile=self.profile,
                         mock=self.ops.mock)

    # ---- stage wrappers ---------------------------------------------------------------
    def _run_for(self, ctx: JobContext) -> PipelineRun:
        run = self._runs.get(ctx.job.job_id)
        if run is None:
            run = self._runs[ctx.job.job_id] = PipelineRun(self, ctx, self.settings, self.cache)
        return run

    def _stage(self, name: StageName) -> StageFunction:
        def run_stage(ctx: JobContext) -> JobContext:
            run = self._run_for(ctx)
            run.stage = name
            try:
                self._execute(name, run)
            except BaseException:
                self._runs.pop(ctx.job.job_id, None)
                raise
            if name == "export":
                self._runs.pop(ctx.job.job_id, None)
            return ctx

        return run_stage

    def _execute(self, name: StageName, run: PipelineRun) -> None:
        if name == "plan":
            self.ops.plan(run)
            if not isinstance(run.lesson, Lesson) or run.lesson.lesson_id != run.lesson_id or run.lesson.language != "en":
                raise PipelineError("plan_invalid", "Planner must supply an English Lesson with the job's lesson_id")
        elif name == "validate":
            self.ops.validate(run)
        elif name == "translate":
            self.ops.localize(run)
            if not isinstance(run.lesson, Lesson) or run.lesson.language != run.language:
                raise PipelineError("localize_invalid", f"Localizer must supply a {run.language} lesson")
        elif name == "voice":
            self.ops.voice(run)
        elif name == "timeline":
            self.ops.timeline(run)
            if not run.ctx.job.preview_ready:  # the operation forgot the callback: verify anyway
                run.preview_ready()
        else:
            if not run.ctx.job.preview_ready:
                raise PipelineError("preview_not_ready", "Export requires verified preview artifacts")
            self.ops.export(run)

    # ---- preview ----------------------------------------------------------------------
    def mark_preview_ready(self, run: PipelineRun) -> None:
        """Verify the preview files on disk, then expose them on the job right away."""
        lesson, timeline = read_preview(run.folder)
        if (lesson.lesson_id, timeline.variant, lesson.language) != (run.lesson_id, run.variant, run.language):
            raise PipelineError("preview_invalid", "Preview files belong to a different lesson, variant or language")
        job = run.ctx.job
        stage_ms = {s.name: s.ms for s in job.stages if s.ms is not None}
        self.cache.write_json(run.folder / "meta.json", {
            "job_id": job.job_id, "mock": job.mock, "source": lesson.source, "model": lesson.model,
            "warnings": [*lesson.warnings, *job.warnings], "stage_ms": stage_ms,
        })
        job.preview_ready = True
        job.playable = True
        self.runner.update(run.ctx)


def read_meta(folder: Path) -> dict[str, Any]:
    try:
        value = json.loads((folder / "meta.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}
