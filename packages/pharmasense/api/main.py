"""FastAPI application factory and executable entry point."""

import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse, PlainTextResponse

from pharmasense.api.errors import AnalyticsExecutionError, AnalyticsUnavailableError
from pharmasense.api.observability import REQUEST_ID_HEADER, observe_request, safe_request_path
from pharmasense.api.routes.analytics import router as analytics_router
from pharmasense.api.routes.system import router as system_router
from pharmasense.config.settings import get_settings
from pharmasense.telemetry import configure_application_logging, structured_log

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """Create the PharmaSense API without connecting to external services."""
    settings = get_settings()
    configure_application_logging(settings.app_log_level)
    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Research API for potential drug safety reporting signals.",
        docs_url="/docs" if settings.app_environment != "production" else None,
        redoc_url=None,
    )
    application.middleware("http")(observe_request)
    application.include_router(system_router, prefix="/api/v1", tags=["system"])
    application.include_router(analytics_router, prefix="/api/v1", tags=["analytics"])

    @application.exception_handler(AnalyticsUnavailableError)
    async def analytics_unavailable(
        _request: Request, _error: AnalyticsUnavailableError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": "Analytics database is unavailable."},
        )

    @application.exception_handler(AnalyticsExecutionError)
    async def analytics_failure(_request: Request, _error: AnalyticsExecutionError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Analytics request could not be completed."},
        )

    @application.exception_handler(Exception)
    async def unexpected_failure(request: Request, _error: Exception) -> PlainTextResponse:
        request_id = getattr(request.state, "request_id", None)
        structured_log(
            logger,
            "unhandled_request_exception",
            level=logging.ERROR,
            request_id=request_id,
            method=request.method,
            path=safe_request_path(request),
        )
        headers = {REQUEST_ID_HEADER: request_id} if isinstance(request_id, str) else None
        return PlainTextResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content="Internal Server Error",
            headers=headers,
        )

    return application


app = create_app()


def run() -> None:
    """Run the development API server through the installed console script."""
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "pharmasense.api.main:app",
        host=settings.app_host,
        port=settings.app_port,
        log_level=settings.app_log_level.lower(),
    )
