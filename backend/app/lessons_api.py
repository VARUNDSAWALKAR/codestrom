"""Task 5A routes: POST /api/lessons, GET /api/jobs/{id}, GET /api/lessons/{id} (api-contracts.md sections 3-5)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .contracts import CORE_LANGUAGES, LessonRequest
from .jobs import ExportStatus, JobRecord, PipelineError
from .orchestrator import BusyError, read_meta, read_preview
from .planner.schema import Lesson
from .timeline.schema import Timeline


def api_error(status: int, code: str, message: str, headers: dict[str, str] | None = None,
              **extra: Any) -> JSONResponse:
    return JSONResponse(status_code=status, headers=headers,
                        content={"error": {"code": code, "message": message, **extra}})


class SubmitResponse(BaseModel):
    job_id: str
    lesson_id: str
    variant: str
    cached: bool
    mock: bool = False


class Media(BaseModel):
    audio_web: str | None = None
    audio_wav: str | None = None
    mp4: str | None = None
    srt: str | None = None


class LessonMeta(BaseModel):
    source: str
    model: str
    warnings: list[str] = Field(default_factory=list)
    stage_ms: dict[str, int] = Field(default_factory=dict)
    variants: list[str] = Field(default_factory=list)
    job_id: str | None = None


class LessonResponse(BaseModel):
    lesson_id: str
    variant: str
    preview_ready: bool = True  # this response exists only when the preview files verified on disk
    export_status: ExportStatus
    mock: bool = False
    lesson: Lesson
    timeline: Timeline
    media: Media
    meta: LessonMeta


def preview_variants(lesson_dir: Path, cache: Any, lesson_id: str) -> list[tuple[float, str]]:
    """Variants whose preview verifies on disk, newest first."""
    found: list[tuple[float, str]] = []
    for child in lesson_dir.iterdir() if lesson_dir.is_dir() else ():
        try:
            folder = cache.lesson_dir(lesson_id, child.name)
        except ValueError:
            continue  # not a variant folder
        try:
            read_preview(folder)
        except PipelineError:
            continue
        found.append(((folder / "timeline.json").stat().st_mtime, child.name))
    return sorted(found, reverse=True)


def register_lesson_routes(application: FastAPI) -> None:
    @application.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, exc: RequestValidationError) -> JSONResponse:
        fields = [{"field": ".".join(str(part) for part in e["loc"][1:]) or "body", "message": e["msg"]}
                  for e in exc.errors()]
        return api_error(422, "validation_error", "Invalid request", fields=fields)

    @application.post("/api/lessons", status_code=202, response_model=SubmitResponse)
    def create_lesson(body: LessonRequest, request: Request) -> SubmitResponse | JSONResponse:
        orchestrator = request.app.state.orchestrator
        if orchestrator is None:
            return api_error(503, "pipeline_unavailable",
                             "The lesson pipeline is not connected to this backend yet (Task 5B)")
        if body.language not in CORE_LANGUAGES:
            return api_error(422, "language_unavailable",
                             f"Language '{body.language}' is a bonus language and is not enabled; "
                             f"use one of {sorted(CORE_LANGUAGES)}")
        try:
            job, cached = orchestrator.submit(body)
        except PipelineError as exc:
            return api_error(422, exc.code, str(exc))
        except BusyError as exc:
            return api_error(429, "busy", str(exc), headers={"Retry-After": str(exc.retry_after)},
                             retry_after=exc.retry_after)
        except RuntimeError as exc:
            return api_error(503, "runner_unavailable", str(exc))
        return SubmitResponse(job_id=job.job_id, lesson_id=job.lesson_id, variant=job.variant,
                              cached=cached, mock=job.mock)

    @application.get("/api/jobs/{job_id}", response_model=JobRecord)
    def get_job(job_id: str, request: Request) -> JobRecord | JSONResponse:
        try:
            return request.app.state.runner.snapshot(job_id)
        except KeyError:
            return api_error(404, "job_not_found", f"Unknown job '{job_id}'")

    @application.get("/api/lessons/{lesson_id}", response_model=LessonResponse)
    def get_lesson(lesson_id: str, request: Request,
                   variant: str | None = Query(default=None)) -> LessonResponse | JSONResponse:
        cache, runner = request.app.state.cache, request.app.state.runner
        try:
            lesson_dir = cache.lesson_dir(lesson_id)
            if variant is not None:
                cache.lesson_dir(lesson_id, variant)
        except ValueError:
            return api_error(404, "lesson_not_found", "Unknown lesson or variant")
        ready = preview_variants(lesson_dir, cache, lesson_id)
        names = [name for _, name in ready]
        chosen = variant or (names[0] if names else None)
        if chosen is None or chosen not in names:
            job = runner.latest(lesson_id, variant) if variant else None
            if job is not None or lesson_dir.is_dir():
                return api_error(404, "preview_not_ready", "Preview artifacts are not available yet",
                                 job_id=job.job_id if job else None)
            return api_error(404, "lesson_not_found", "Unknown lesson or variant")
        folder = cache.lesson_dir(lesson_id, chosen)
        lesson, timeline = read_preview(folder)
        meta = read_meta(folder)
        job = runner.latest(lesson_id, chosen)
        orchestrator = request.app.state.orchestrator
        has_mp4 = orchestrator.export_verified(folder) if orchestrator else False
        if has_mp4:
            export_status: ExportStatus = "completed"
        else:  # a stale "completed" with no file means the MP4 is gone
            export_status = job.export_status if job and job.export_status != "completed" else "pending"
        prefix = f"/media/{lesson_id}/{chosen}"
        exists = lambda name: f"{prefix}/{name}" if (folder / name).is_file() and (folder / name).stat().st_size else None
        return LessonResponse(
            lesson_id=lesson_id, variant=chosen, export_status=export_status, mock=bool(meta.get("mock")),
            lesson=lesson, timeline=timeline,
            media=Media(audio_web=exists("narration.m4a") if timeline.audio else None,
                        audio_wav=exists("narration.wav") if timeline.audio else None,
                        mp4=exists("lesson.mp4") if has_mp4 else None, srt=exists("lesson.srt")),
            meta=LessonMeta(source=str(meta.get("source", lesson.source)), model=str(meta.get("model", lesson.model)),
                            warnings=list(meta.get("warnings", lesson.warnings)),
                            stage_ms={k: int(v) for k, v in dict(meta.get("stage_ms", {})).items()},
                            variants=sorted(names), job_id=meta.get("job_id")))
