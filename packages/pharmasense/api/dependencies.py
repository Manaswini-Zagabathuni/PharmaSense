"""FastAPI dependency providers."""

from functools import lru_cache

from pharmasense.config.settings import get_settings
from pharmasense.db.readiness import DatabaseReadinessService


@lru_cache
def get_database_readiness_service() -> DatabaseReadinessService:
    """Build the database readiness service from environment configuration."""
    return DatabaseReadinessService(get_settings())


def reset_dependencies() -> None:
    """Clear cached dependencies, primarily for tests and process reloads."""
    get_database_readiness_service.cache_clear()
    get_settings.cache_clear()
