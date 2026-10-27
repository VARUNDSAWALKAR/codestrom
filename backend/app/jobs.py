"""One worker, ordered stages, sampled peak process RSS and JSON-line logs.

Stage implementations and fallback assets arrive in later tasks. Submission is
disabled until every stage and the fallback handler have been registered.
"""

from __future__ import annotations

import logging
from collections import deque
from collections.abc import Callable, Mapping
from threading import Condition, Event, Thread
from time import perf_counter
from typing import Literal
from uuid import uuid4

import psutil
from pydantic import BaseModel, ConfigDict, Field

from .cache import Cache
from .config import DeviceProfile, Language

StageName = Literal["plan", "validate", "translate", "voice", "timeline", "export"]
STAGES: tuple[StageName, ...] = ("plan", "validate", "translate", "voice", "timeline", "export")
StageStatus = Literal["pending", "running", "done", "cached", "skipped", "error"]
logger = logging.getLogger(__name__)


class StageRecord(BaseModel):
    name: StageName
    status: StageStatus = "pending"
    ms: int | None = None
    rss_mb: float | None = None
    note: str = ""


class JobRecord(BaseModel):
    job_id: str = Field(default_factory=lambda: "j_" + uuid4().hex[:12])
    kind: Literal["create", "revoice", "edit"] = "create"
    status: Literal["queued", "running", "done", "error"] = "queued"
    queue_position: int = 0
    lesson_id: str
    variant: str
    playable: bool = False
    fallback: bool = False
    fallback_reason: str | None = None
    progress: float = Field(default=0.0, ge=0.0, le=1.0)
    stages: list[StageRecord] = Field(default_factory=lambda: [StageRecord(name=s) for s in STAGES])
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None
    total_ms: int = 0
    device_profile: DeviceProfile


class JobContext(BaseModel):
    """Typed foundation context; stages will add validated lesson artifacts later."""

    model_config = ConfigDict(validate_assignment=True)
    job: JobRecord
    language: Language


class RunRecord(BaseModel):
    job_id: str
    stage: StageName
    ms: int
    rss_mb: float
    device: DeviceProfile
    ok: bool
    note: str


StageFunction = Callable[[JobContext], JobContext]
FallbackFunction = Callable[[JobContext, StageName, Exception], JobContext]


class PeakRSS:
    """Sample the backend's RSS, not GPU memory or child-process memory."""

    def __init__(self) -> None:
        self._process = psutil.Process()
        self._stop = Event()
        self.peak = self._process.memory_info().rss
        self._thread = Thread(target=self._sample, name="rss-sampler", daemon=True)

    def _sample(self) -> None:
        while not self._stop.wait(0.02):
            self.peak = max(self.peak, self._process.memory_info().rss)

    def __enter__(self) -> PeakRSS:
        self._thread.start()
        return self

    def __exit__(self, *args: object) -> None:
        self._stop.set()
        self._thread.join()
        self.peak = max(self.peak, self._process.memory_info().rss)

    @property
    def mb(self) -> float:
        return round(self.peak / (1024 * 1024), 2)


class JobRunner:
    def __init__(self, cache: Cache, profile: DeviceProfile,
                 stages: Mapping[StageName, StageFunction] | None = None,
                 fallback: FallbackFunction | None = None) -> None:
        self.cache = cache
        self.profile = profile
        self._stages = dict(stages or {})
        self._fallback = fallback
        self._condition = Condition()
        self._pending: deque[JobContext] = deque()
        self._jobs: dict[str, JobRecord] = {}
        self._thread: Thread | None = None
        self._closing = False

    @property
    def queue_length(self) -> int:
        with self._condition:
            return len(self._pending)

    def start(self) -> None:
        with self._condition:
            if self._thread is not None and self._thread.is_alive():
                return
            self._closing = False
            self._thread = Thread(target=self._work, name="lesson-worker", daemon=True)
            self._thread.start()

    def close(self) -> None:
        """Drain accepted jobs before shutdown; never start a second worker."""
        with self._condition:
            self._closing = True
            self._condition.notify_all()
        if self._thread is not None:
            self._thread.join()

    def submit(self, lesson_id: str, variant: str, language: Language) -> JobRecord:
        with self._condition:
            if self._closing or self._thread is None or not self._thread.is_alive():
                raise RuntimeError("Job runner is not accepting jobs")
            if set(self._stages) != set(STAGES) or self._fallback is None:
                raise RuntimeError("Pipeline stages and fallback are not implemented yet")
            self.cache.lesson_dir(lesson_id, variant)  # validates cache identifiers
            job = JobRecord(lesson_id=lesson_id, variant=variant, device_profile=self.profile)
            ctx = JobContext(job=job, language=language)
            self._jobs[job.job_id] = job.model_copy(deep=True)
            self._pending.append(ctx)
            self._condition.notify()
            return self.snapshot(job.job_id)

    def snapshot(self, job_id: str) -> JobRecord:
        with self._condition:
            job = self._jobs[job_id].model_copy(deep=True)
            for position, ctx in enumerate(self._pending, 1):
                if ctx.job.job_id == job_id:
                    job.queue_position = position
                    break
            return job

    def _publish(self, ctx: JobContext, started: float) -> None:
        ctx.job.total_ms = round((perf_counter() - started) * 1000)
        with self._condition:
            self._jobs[ctx.job.job_id] = ctx.job.model_copy(deep=True)

    def _work(self) -> None:
        while True:
            with self._condition:
                self._condition.wait_for(lambda: bool(self._pending) or self._closing)
                if not self._pending:
                    return
                ctx = self._pending.popleft()
            started = perf_counter()
            try:
                self._run(ctx, started)
            except Exception as exc:
                # A logging or infrastructure failure must not kill the worker.
                logger.exception("Job %s failed", ctx.job.job_id)
                ctx.job.status = "error"
                ctx.job.error = str(exc)
                self._publish(ctx, started)

    def _run(self, ctx: JobContext, started: float) -> None:
        ctx.job.status = "running"
        self._publish(ctx, started)
        for index, name in enumerate(STAGES):
            stage = ctx.job.stages[index]
            if name == "translate" and ctx.language == "en":
                stage.status = "skipped"
                stage.note = "English requires no translation"
            elif stage.status not in {"cached", "skipped"}:
                stage.status = "running"
            self._publish(ctx, started)
            stage_started = perf_counter()
            failure: Exception | None = None
            with PeakRSS() as memory:
                try:
                    if stage.status == "running":
                        result = self._stages[name](ctx)
                        if result is not ctx:
                            raise ValueError("Foundation stages must return the supplied context")
                        if stage.status == "running":
                            stage.status = "done"
                except Exception as exc:
                    failure = exc
                    stage.status = "error"
                    stage.note = str(exc)
            stage.ms = round((perf_counter() - stage_started) * 1000)
            stage.rss_mb = memory.mb
            self.cache.append_run(RunRecord(
                job_id=ctx.job.job_id, stage=name, ms=stage.ms, rss_mb=stage.rss_mb,
                device=self.profile, ok=failure is None, note=stage.note,
            ))
            if failure is not None:
                ctx.job.fallback = True
                ctx.job.fallback_reason = str(failure)
                assert self._fallback is not None
                result = self._fallback(ctx, name, failure)
                if result is not ctx:
                    raise ValueError("Fallback must return the supplied context")
                if name not in {"plan", "validate"}:
                    if not ctx.job.playable:
                        raise RuntimeError("Fallback did not supply a playable package")
                    ctx.job.status = "done"
                    self._publish(ctx, started)
                    return
            if name == "timeline":
                ctx.job.playable = True
            self._publish(ctx, started)
        ctx.job.status = "done"
        ctx.job.progress = 1.0
        self._publish(ctx, started)


def run_measured_stage(ctx: JobContext, name: StageName, function: StageFunction, cache: Cache) -> JobContext:
    """Measure standalone Task 2 stages before the full pipeline is registered."""
    stage = next(s for s in ctx.job.stages if s.name == name)
    stage.status = "running"
    started = perf_counter()
    ok = False
    memory = PeakRSS()
    try:
        with memory:
            result = function(ctx)
            if result is not ctx:
                raise ValueError("Stage must return its context")
            if stage.status == "running":
                stage.status = "done"
            ok = True
    except Exception as exc:
        stage.status = "error"
        stage.note = str(exc)
        raise
    finally:
        stage.ms = round((perf_counter() - started) * 1000)
        stage.rss_mb = memory.mb
        cache.append_run(RunRecord(job_id=ctx.job.job_id, stage=name, ms=stage.ms,
                                  rss_mb=stage.rss_mb, device=ctx.job.device_profile, ok=ok, note=stage.note))
    return ctx
