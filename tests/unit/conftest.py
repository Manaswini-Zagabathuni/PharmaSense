"""Isolation fixtures shared by unit tests only."""

from collections.abc import Iterator

import pytest

from pharmasense.config.settings import get_settings

_DATABASE_ENVIRONMENT_VARIABLES = (
    "DATABASE_URL",
    "TEST_DATABASE_URL",
    "MYSQL_HOST",
    "MYSQL_PORT",
    "MYSQL_DATABASE",
    "MYSQL_USER",
    "MYSQL_PASSWORD",
)

_APPLICATION_ENVIRONMENT_VARIABLES = (
    "APP_ENVIRONMENT",
    "APP_LOG_LEVEL",
    "APP_TRUSTED_HOSTS",
    "APP_VERSION",
)


@pytest.fixture(autouse=True)
def isolate_database_environment(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Prevent external database configuration from leaking into unit tests."""

    for variable in (*_DATABASE_ENVIRONMENT_VARIABLES, *_APPLICATION_ENVIRONMENT_VARIABLES):
        monkeypatch.delenv(variable, raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
