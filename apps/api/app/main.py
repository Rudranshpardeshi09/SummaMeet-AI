"""FastAPI application factory — the main entry point.

Creates the FastAPI app with all middleware, routes, and error handlers.
Run with: uvicorn app.main:app --reload
"""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.auth import router as auth_router
from app.api.health import router as health_router
from app.api.bot import router as bot_router
from app.api.meetings import router as meetings_router
from app.api.transcript import router as transcript_router
from app.api.organizations import router as organizations_router
from app.api.users import router as users_router
from app.api.projects import router as projects_router
from app.api.ws import router as ws_router
from app.api.reports import router as reports_router
from app.api.action_items import router as action_items_router
from app.api.dashboard import router as dashboard_router
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.middleware import RequestIdMiddleware
from common import setup_logging

settings = get_settings()

# Initialize structured logging
setup_logging(
    log_level=settings.log_level,
    json_output=settings.is_production,
)


def create_app() -> FastAPI:
    """Application factory — creates and configures the FastAPI instance."""

    application = FastAPI(
        title="AI Video Note Taker API",
        description=(
            "Backend API for the AI-powered meeting note taker platform. "
            "Handles authentication, meeting orchestration, transcription, "
            "and report generation."
        ),
        version="0.2.0",
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
    )

    # ---- Middleware ----
    # Order matters: outermost middleware runs first

    application.add_middleware(RequestIdMiddleware)

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.api_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-Id"],
    )

    # ---- Error Handlers ----

    @application.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Convert Pydantic validation errors to RFC 7807 Problem Details."""
        invalid_params = []
        for error in exc.errors():
            loc = ".".join(str(l) for l in error["loc"] if l != "body")
            invalid_params.append({
                "name": loc,
                "reason": error["msg"],
            })

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={
                "type": "https://api.notes.local/errors/validation-error",
                "title": "Unprocessable Entity",
                "status": 422,
                "detail": "Request validation failed",
                "instance": str(request.url.path),
                "invalid_params": invalid_params,
            },
        )

    @application.exception_handler(AppError)
    async def app_error_exception_handler(
        request: Request, exc: AppError
    ) -> JSONResponse:
        """Handle custom AppErrors returning RFC 7807 format."""
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "type": exc.type,
                "title": exc.title,
                "status": exc.status_code,
                "detail": exc.detail,
                "instance": exc.instance or str(request.url.path),
            },
        )

    @application.exception_handler(Exception)
    async def global_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        """Catch-all error handler returning RFC 7807 format."""
        import structlog

        logger = structlog.get_logger("error_handler")
        logger.error(
            "Unhandled exception",
            path=str(request.url.path),
            method=request.method,
            error=str(exc),
            exc_info=True,
        )

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "type": "https://api.notes.local/errors/internal-server-error",
                "title": "Internal Server Error",
                "status": 500,
                "detail": "An unexpected error occurred"
                if settings.is_production
                else str(exc),
                "instance": str(request.url.path),
            },
        )

    # ---- Routes ----
    application.include_router(health_router, prefix="")
    application.include_router(auth_router, prefix="/api/v1")
    application.include_router(organizations_router, prefix="/api/v1")
    application.include_router(users_router, prefix="/api/v1")
    application.include_router(projects_router, prefix="/api/v1")
    application.include_router(ws_router, prefix="/api/v1")
    application.include_router(bot_router, prefix="/api/v1")
    application.include_router(meetings_router, prefix="/api/v1")
    application.include_router(reports_router, prefix="/api/v1")
    application.include_router(action_items_router, prefix="/api/v1")
    application.include_router(dashboard_router, prefix="/api/v1")
    application.include_router(transcript_router, prefix="")

    return application


app = create_app()
