"""Liveness and readiness endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from pharmasense import __version__
from pharmasense.api.dependencies import get_database_readiness_service
from pharmasense.api.schemas.system import (
    HealthResponse,
    InfoResponse,
    ReadinessResponse,
    ServiceCheck,
)
from pharmasense.config.settings import Settings, get_settings
from pharmasense.db.readiness import DatabaseReadinessService

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Report process liveness without requiring downstream services."""
    return HealthResponse(status="ok", service="pharmasense-api", version=__version__)


@router.get("/info", response_model=InfoResponse)
def info(settings: Annotated[Settings, Depends(get_settings)]) -> InfoResponse:
    """Return safe application metadata without infrastructure configuration."""

    return InfoResponse(
        application_name=settings.app_name,
        environment=settings.app_environment,
        version=settings.app_version,
    )


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ReadinessResponse}},
)
def readiness(
    response: Response,
    service: Annotated[DatabaseReadinessService, Depends(get_database_readiness_service)],
) -> ReadinessResponse:
    """Verify connectivity to every service required to accept traffic."""
    database = service.check()
    if not database.ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return ReadinessResponse(
            status="not_ready",
            checks={"database": ServiceCheck(status="unavailable", detail=database.detail)},
        )

    return ReadinessResponse(
        status="ready",
        checks={"database": ServiceCheck(status="ok", detail=database.detail)},
    )
