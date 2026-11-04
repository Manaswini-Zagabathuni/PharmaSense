"""FastAPI application factory and executable entry point."""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from pharmasense import __version__
from pharmasense.api.errors import AnalyticsExecutionError, AnalyticsUnavailableError
from pharmasense.api.routes.analytics import router as analytics_router
from pharmasense.api.routes.system import router as system_router
from pharmasense.config.settings import get_settings


def create_app() -> FastAPI:
    """Create the PharmaSense API without connecting to external services."""
    settings = get_settings()
    application = FastAPI(
        title=settings.app_name,
        version=__version__,
        description="Research API for potential drug safety reporting signals.",
        docs_url="/docs" if settings.app_environment != "production" else None,
        redoc_url=None,
    )
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
