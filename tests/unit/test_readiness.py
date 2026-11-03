"""Database readiness service tests."""

from typing import Any

import pytest
from pydantic import SecretStr
from sqlalchemy import Engine, create_engine
from sqlalchemy.exc import OperationalError

from pharmasense.config.settings import Settings
from pharmasense.db.readiness import DatabaseReadinessService


def test_readiness_reports_missing_configuration() -> None:
    result = DatabaseReadinessService(Settings(_env_file=None)).check()

    assert result.ready is False
    assert result.detail == "Database configuration is incomplete."


def test_readiness_executes_database_query() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    settings = Settings(_env_file=None, database_url=SecretStr("sqlite+pysqlite:///:memory:"))

    result = DatabaseReadinessService(settings, engine).check()

    assert result.ready is True


def test_readiness_reuses_the_connection_pool(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    settings = Settings(_env_file=None, database_url=SecretStr("sqlite+pysqlite:///:memory:"))
    build_calls = 0

    def build_test_engine(_database_url: object) -> Engine:
        nonlocal build_calls
        build_calls += 1
        return engine

    monkeypatch.setattr("pharmasense.db.readiness.build_engine", build_test_engine)
    service = DatabaseReadinessService(settings)

    assert service.check().ready is True
    assert service.check().ready is True
    assert build_calls == 1


class FailingConnection:
    def __enter__(self) -> "FailingConnection":
        raise OperationalError("SELECT 1", {}, Exception("unavailable"))

    def __exit__(self, *_args: Any) -> None:
        return None


class FailingEngine:
    def connect(self) -> FailingConnection:
        return FailingConnection()


def test_readiness_sanitizes_database_failure() -> None:
    settings = Settings(_env_file=None, database_url=SecretStr("sqlite+pysqlite:///:memory:"))

    result = DatabaseReadinessService(settings, FailingEngine()).check()  # type: ignore[arg-type]

    assert result.ready is False
    assert result.detail == "Database connection failed."
