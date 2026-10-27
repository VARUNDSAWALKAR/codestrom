"""FastAPI app: foundation routes plus the Task 5A lesson API. The production pipeline is wired in Task 5B."""

from __future__ import annotations

# Offline flags must be installed before any future model-library imports.
from .config import Settings, get_settings

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException

from .cache import Cache
from .contracts import (
    CORE_LANGUAGES, LANGUAGES, ConfigResponse, Defaults, HealthResponse, LengthOptions,
    ModelHealth, NamedReadiness, ParlerReadiness, RendererHealth,
)
from .jobs import JobRunner
from .lessons_api import register_lesson_routes
from .language_policy import approved_languages
from .localize.model import translator_ready
from .speech.parler_engine import parler_ready
from .mock_pipeline import build_mock_ops
from .orchestrator import Orchestrator, PipelineOps
from .pipeline_ops import planner_probe, production_ops

logger = logging.getLogger(__name__)
# AGENTS.md hard rule 1: Vite dev, Remotion Studio and nothing else.
CORS_ORIGINS = ("http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000")


def create_app(settings: Settings | None = None, ops: PipelineOps | None = None) -> FastAPI:
    """Pipeline selection: injected `ops` (tests) win; else MOCK_PIPELINE=1 selects the fixture pipeline;
    else the production pipeline. Production never falls back to mock. No model loads at import or startup."""
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        profile = settings.resolve_profile()
        cache.initialize()
        # Do not equate files on disk with a loaded model: tts_kokoro.ready flips only after Kokoro
        # really loads; translator health reflects successful initialization, not file presence.
        models = ModelHealth(
            planner=NamedReadiness(name=settings.planner_model(profile)),
            translator=NamedReadiness(name="indictrans2-en-indic-dist-200M"),
            tts_parler=ParlerReadiness(enabled=settings.enable_parler),
        )
        application.state.planner_probe = None
        if ops is not None:
            chosen = ops
        elif settings.mock_pipeline:
            chosen = build_mock_ops()
        else:
            chosen = production_ops(on_tts_loaded=lambda: setattr(models.tts_kokoro, "ready", True), settings=settings)
            application.state.planner_probe = planner_probe(settings, models.planner.name)
        if chosen.mock:
            logger.warning("MOCK_PIPELINE is enabled: lessons are fixtures, not Ollama output. "
                           "Never use this for acceptance runs.")
        orchestrator = Orchestrator(settings, cache, profile, chosen)
        runner = JobRunner(cache, profile, orchestrator.stages(), on_failure="fail")
        orchestrator.bind(runner)
        application.state.orchestrator = orchestrator
        application.state.settings = settings
        application.state.cache = cache
        application.state.runner = runner
        application.state.profile = profile
        application.state.models = models
        runner.start()
        try:
            yield
        finally:
            runner.close()

    cache = Cache(settings.cache_dir)
    # Disable CDN-dependent Swagger/ReDoc pages. The local JSON schema remains.
    application = FastAPI(title="Blu VisualTeacher", version="0.1.0",
                          lifespan=lifespan, docs_url=None, redoc_url=None)

    application.add_middleware(CORSMiddleware, allow_origins=list(CORS_ORIGINS), allow_methods=["GET", "POST", "PATCH"],
                               allow_headers=["Content-Type"])
    register_lesson_routes(application)

    @application.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, headers=exc.headers,
                            content={"error": {"code": str(exc.status_code), "message": str(exc.detail)}})

    @application.get("/api/health", response_model=HealthResponse)
    def health(request: Request) -> HealthResponse:
        models: ModelHealth = request.app.state.models
        if request.app.state.planner_probe is not None:
            models.planner.ready = request.app.state.planner_probe()
        models.translator.ready = translator_ready(settings)
        models.tts_parler.ready = settings.enable_parler and parler_ready(settings)
        return HealthResponse(
            ok=models.planner.ready and models.translator.ready and models.tts_kokoro.ready,
            mock_pipeline=request.app.state.orchestrator is not None and request.app.state.orchestrator.ops.mock,
            device_profile=request.app.state.profile,
            offline=settings.offline,
            models=models,
            renderer=RendererHealth(bundle_ready=(settings.render_bundle / "index.html").is_file()),
            queue_length=request.app.state.runner.queue_length,
        )

    @application.get("/api/config", response_model=ConfigResponse)
    def configuration(request: Request) -> ConfigResponse:
        # Production availability uses the same explicit approval policy as precheck.
        orchestrator = request.app.state.orchestrator
        accepted = CORE_LANGUAGES if orchestrator is not None and orchestrator.ops.mock else approved_languages(settings)
        languages = [option.model_copy(update={"available": option.code in accepted}) for option in LANGUAGES]
        return ConfigResponse(languages=languages,
                              target_seconds=LengthOptions(default=settings.default_target_seconds),
                              defaults=Defaults(language=settings.default_language))

    application.mount("/media", StaticFiles(directory=cache.lessons, check_dir=False), name="media")
    # The foundation starts without Varun's build. Hash routes need only index.html.
    if (settings.web_dist / "index.html").is_file():
        application.mount("/", StaticFiles(directory=settings.web_dist, html=True), name="web")
    return application


app = create_app()
