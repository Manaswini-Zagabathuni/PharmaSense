"""Typed, environment-based settings."""

import re
from functools import lru_cache
from typing import Literal

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL

from pharmasense import __version__

_HOST_PATTERN = re.compile(r"(?:\*|(?:\*\.)?[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?)")


class Settings(BaseSettings):
    """Configuration loaded from environment variables and an ignored .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "PharmaSense"
    app_version: str = __version__
    app_environment: Literal["development", "test", "production"] = "development"
    app_log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    app_trusted_hosts: str = "localhost,127.0.0.1,testserver,api"

    database_url: SecretStr | None = None
    mysql_host: str | None = None
    mysql_port: int = 3306
    mysql_database: str | None = None
    mysql_user: str | None = None
    mysql_password: SecretStr | None = None

    @field_validator("app_trusted_hosts")
    @classmethod
    def validate_trusted_hosts(cls, value: str) -> str:
        """Normalize and validate a comma-separated Starlette trusted-host allowlist."""

        hosts = [host.strip() for host in value.split(",")]
        if not hosts or any(not host for host in hosts):
            raise ValueError("APP_TRUSTED_HOSTS must contain one or more hosts")
        if len(hosts) > 32:
            raise ValueError("APP_TRUSTED_HOSTS cannot contain more than 32 hosts")
        if any(_HOST_PATTERN.fullmatch(host) is None for host in hosts):
            raise ValueError("APP_TRUSTED_HOSTS contains an invalid host pattern")
        return ",".join(dict.fromkeys(hosts))

    @model_validator(mode="after")
    def validate_production_settings(self) -> "Settings":
        """Require explicit, fail-closed host and logging configuration in production."""

        if self.app_environment != "production":
            return self
        if "app_trusted_hosts" not in self.model_fields_set:
            raise ValueError("APP_TRUSTED_HOSTS must be explicitly configured in production")
        if "*" in self.trusted_hosts:
            raise ValueError("APP_TRUSTED_HOSTS cannot contain '*' in production")
        if self.app_log_level == "DEBUG":
            raise ValueError("APP_LOG_LEVEL cannot be DEBUG in production")
        return self

    @property
    def trusted_hosts(self) -> tuple[str, ...]:
        """Return the validated host allowlist for Starlette middleware."""

        return tuple(self.app_trusted_hosts.split(","))

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
