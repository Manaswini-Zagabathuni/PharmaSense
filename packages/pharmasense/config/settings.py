"""Typed, environment-based settings."""

from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class Settings(BaseSettings):
    """Configuration loaded from environment variables and an ignored .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "PharmaSense"
    app_environment: Literal["development", "test", "production"] = "development"
    app_log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    app_host: str = "127.0.0.1"
    app_port: int = 8000

    database_url: SecretStr | None = None
    mysql_host: str | None = None
    mysql_port: int = 3306
    mysql_database: str | None = None
    mysql_user: str | None = None
    mysql_password: SecretStr | None = None

    def sqlalchemy_url(self) -> URL | str | None:
        """Return a SQLAlchemy URL without exposing credentials in logs."""
        if self.database_url is not None:
            return self.database_url.get_secret_value()
        mysql_password = self.mysql_password
        if (
            self.mysql_host is None
            or self.mysql_database is None
            or self.mysql_user is None
            or mysql_password is None
        ):
            return None
        return URL.create(
            drivername="mysql+pymysql",
            username=self.mysql_user,
            password=mysql_password.get_secret_value(),
            host=self.mysql_host,
            port=self.mysql_port,
            database=self.mysql_database,
            query={"charset": "utf8mb4"},
        )


@lru_cache
def get_settings() -> Settings:
    """Load and cache process settings."""
    return Settings()
