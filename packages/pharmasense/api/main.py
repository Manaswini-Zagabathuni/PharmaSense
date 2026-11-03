"""FastAPI application factory and executable entry point."""

from fastapi import FastAPI

from pharmasense import __version__
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
