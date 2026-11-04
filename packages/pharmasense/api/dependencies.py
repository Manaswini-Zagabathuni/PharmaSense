"""FastAPI dependency providers."""

from functools import lru_cache

from pharmasense.api.services.analytics import AnalyticsService
from pharmasense.config.settings import get_settings
from pharmasense.db.readiness import DatabaseReadinessService


@lru_cache
def get_analytics_service() -> AnalyticsService:
    """Build the lazy read-only analytics service from environment configuration."""

    return AnalyticsService(get_settings())


@lru_cache
def get_database_readiness_service() -> DatabaseReadinessService:
    """Build the database readiness service from environment configuration."""
    return DatabaseReadinessService(get_settings())


def reset_dependencies() -> None:
    """Clear cached dependencies, primarily for tests and process reloads."""
    get_analytics_service.cache_clear()
    get_database_readiness_service.cache_clear()
    get_settings.cache_clear()
