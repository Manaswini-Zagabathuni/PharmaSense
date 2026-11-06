"""Database connectivity checks used by API readiness."""

import logging
from dataclasses import dataclass

from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError

from pharmasense.config.settings import Settings
from pharmasense.db.engine import build_engine
from pharmasense.telemetry import structured_log

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DatabaseCheck:
    """Sanitized result of a database connectivity check."""

    ready: bool
    detail: str


class DatabaseReadinessService:
    """Lazily create an engine and verify MySQL connectivity."""

    def __init__(self, settings: Settings, engine: Engine | None = None) -> None:
        self._settings = settings
        self._engine = engine

    def check(self) -> DatabaseCheck:
        """Execute a minimal parameterized query against the configured database."""
        database_url = self._settings.sqlalchemy_url()
        if database_url is None:
            return DatabaseCheck(False, "Database configuration is incomplete.")

        try:
            if self._engine is None:
                self._engine = build_engine(database_url)
            with self._engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return DatabaseCheck(True, "Database connection succeeded.")
        except SQLAlchemyError:
            structured_log(logger, "database_readiness_failed", level=logging.ERROR)
            return DatabaseCheck(False, "Database connection failed.")
