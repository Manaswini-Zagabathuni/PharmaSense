"""System endpoint response models."""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    """Liveness response."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["ok"]
    service: str
    version: str


class ServiceCheck(BaseModel):
    """Status of one required dependency."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["ok", "unavailable"]
    detail: str


class ReadinessResponse(BaseModel):
    """Aggregate readiness response."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["ready", "not_ready"]
    checks: dict[str, ServiceCheck]
