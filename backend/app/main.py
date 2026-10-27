"""FastAPI foundation. No planning, translation, speech or export yet."""

from __future__ import annotations

# Offline flags must be installed before any future model-library imports.
from .config import Settings, get_settings

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException

from .cache import Cache
from .contracts import (
    LANGUAGES, ConfigResponse, Defaults, HealthResponse, LengthOptions,
    ModelHealth, NamedReadiness, ParlerReadiness, RendererHealth,
)
from .jobs import JobRunner


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        profile = settings.resolve_profile()
        cache.initialize()
        runner = JobRunner(cache, profile)
        application.state.settings = settings
        application.state.cache = cache
        application.state.runner = runner
        application.state.profile = profile
        # Do not equate files on disk with a successfully loaded model. Later
        # integration stages will update these after their actual warm-ups.
        application.state.models = ModelHealth(
            planner=NamedReadiness(name=settings.planner_model(profile)),
            translator=NamedReadiness(name="indictrans2-en-indic-dist-200M"),
            tts_parler=ParlerReadiness(enabled=settings.enable_parler and profile == "gpu"),
        )
        runner.start()
        try:
            yield
        finally:
            runner.close()

    cache = Cache(settings.cache_dir)
    # Disable CDN-dependent Swagger/ReDoc pages. The local JSON schema remains.
    application = FastAPI(title="Blu VisualTeacher", version="0.1.0",
                          lifespan=lifespan, docs_url=None, redoc_url=None)

    @application.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, headers=exc.headers,
                            content={"error": {"code": str(exc.status_code), "message": str(exc.detail)}})

    @application.get("/api/health", response_model=HealthResponse)
    def health(request: Request) -> HealthResponse:
        models: ModelHealth = request.app.state.models
        return HealthResponse(
            ok=models.planner.ready and models.translator.ready and models.tts_kokoro.ready,
            device_profile=request.app.state.profile,
            offline=settings.offline,
            models=models,
            renderer=RendererHealth(bundle_ready=(settings.render_bundle / "index.html").is_file()),
            queue_length=request.app.state.runner.queue_length,
        )

    @application.get("/api/config", response_model=ConfigResponse)
    def configuration() -> ConfigResponse:
        # Engines/listening-test approvals are deliberately not invented here.
        return ConfigResponse(languages=list(LANGUAGES),
                              target_seconds=LengthOptions(default=settings.default_target_seconds),
                              defaults=Defaults(language=settings.default_language))

    application.mount("/media", StaticFiles(directory=cache.lessons, check_dir=False), name="media")
    # The foundation starts without Varun's build. Hash routes need only index.html.
    if (settings.web_dist / "index.html").is_file():
        application.mount("/", StaticFiles(directory=settings.web_dist, html=True), name="web")
    return application


app = create_app()
