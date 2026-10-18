"""FastAPI application factory, middleware, and lifecycle management."""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from blazzid_api.config import get_api_settings
from blazzid_api.dependencies import get_engine
from blazzid_api.routes.health import router as health_router
from blazzid_api.routes.jobs import router as jobs_router
from blazzid_core.errors import BlazzidError
from blazzid_jobs.database import init_db
from blazzid_jobs.errors import (
    IdempotencyConflictError,
    InvalidStateTransitionError,
    JobNotFoundError,
)
from blazzid_storage.interfaces import (
    ArtifactNotFoundError,
    StoragePathTraversalError,
    StorageSizeLimitExceededError,
)

logger = logging.getLogger("blazzid.api")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup and shutdown lifecycle handler."""
    settings = get_api_settings()

    # Fail-safe production verification
    if settings.environment == "production":
        if not settings.auth_secret_token or len(settings.auth_secret_token.strip()) < 8:
            raise RuntimeError(
                "Production configuration error: BLAZZID_AUTH_SECRET must be configured "
                "with at least 8 characters in production."
            )
        if settings.allow_anonymous_dev:
            raise RuntimeError(
                "Production configuration error: BLAZZID_ALLOW_ANONYMOUS_DEV cannot be enabled in production."
            )

    engine = get_engine(settings)
    if engine.dialect.name == "sqlite":
        logger.info("Initializing BLAZZID API database schema (SQLite)...")
        init_db(engine)
    yield
    logger.info("BLAZZID API shutdown complete.")


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    settings = get_api_settings()

    app = FastAPI(
        title="BLAZZID AI Studio API",
        description="Production REST API for asynchronous gameplay video processing and highlight montage assembly",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Global Exception Handlers
    @app.exception_handler(JobNotFoundError)
    async def job_not_found_handler(request: Request, exc: JobNotFoundError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": "not_found", "message": str(exc)},
        )

    @app.exception_handler(ArtifactNotFoundError)
    async def artifact_not_found_handler(
        request: Request, exc: ArtifactNotFoundError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": "artifact_not_found", "message": str(exc)},
        )

    @app.exception_handler(InvalidStateTransitionError)
    async def invalid_transition_handler(
        request: Request, exc: InvalidStateTransitionError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"error": "conflict", "message": str(exc)},
        )

    @app.exception_handler(IdempotencyConflictError)
    async def idempotency_conflict_handler(
        request: Request, exc: IdempotencyConflictError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"error": "idempotency_conflict", "message": str(exc)},
        )

    @app.exception_handler(StorageSizeLimitExceededError)
    async def size_limit_handler(
        request: Request, exc: StorageSizeLimitExceededError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            content={"error": "payload_too_large", "message": str(exc)},
        )

    @app.exception_handler(StoragePathTraversalError)
    async def path_traversal_handler(
        request: Request, exc: StoragePathTraversalError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "invalid_path", "message": str(exc)},
        )

    @app.exception_handler(BlazzidError)
    async def domain_error_handler(request: Request, exc: BlazzidError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "domain_error", "message": str(exc)},
        )

    # Mount routers
    app.include_router(jobs_router, prefix="/api/v1")
    app.include_router(health_router)

    return app


app = create_app()
