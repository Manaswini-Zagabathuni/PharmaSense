"""Settings tests."""

import pytest
from pydantic import SecretStr, ValidationError
from sqlalchemy import URL

from pharmasense import __version__
from pharmasense.config.settings import Settings


def test_database_url_is_built_from_components_without_string_interpolation() -> None:
    settings = Settings(
        _env_file=None,
        mysql_host="database",
        mysql_database="pharmasense",
        mysql_user="researcher",
        mysql_password=SecretStr("p@ss/word"),
    )

    url = settings.sqlalchemy_url()

    assert isinstance(url, URL)
    assert url.password == "p@ss/word"
    assert "p%40ss%2Fword" in url.render_as_string(hide_password=False)


def test_database_url_is_none_when_configuration_is_incomplete() -> None:
    settings = Settings(_env_file=None)

    assert settings.sqlalchemy_url() is None


def test_application_version_has_centralized_default_and_environment_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert Settings(_env_file=None).app_version == __version__

    monkeypatch.setenv("APP_VERSION", "2.4.0-build.7")

    assert Settings(_env_file=None).app_version == "2.4.0-build.7"


def test_trusted_hosts_are_normalized_and_deduplicated() -> None:
    settings = Settings(
        _env_file=None,
        app_trusted_hosts=" localhost,api.example.test,localhost ",
    )

    assert settings.app_trusted_hosts == "localhost,api.example.test"
    assert settings.trusted_hosts == ("localhost", "api.example.test")


@pytest.mark.parametrize(
    "trusted_hosts",
    ["", "localhost,", "https://api.example.test", "api.example.test:8000", "bad host"],
)
def test_invalid_trusted_host_configuration_is_rejected(trusted_hosts: str) -> None:
    with pytest.raises(ValidationError, match="APP_TRUSTED_HOSTS"):
        Settings(_env_file=None, app_trusted_hosts=trusted_hosts)


def test_production_requires_explicit_non_wildcard_trusted_hosts() -> None:
    with pytest.raises(ValidationError, match="explicitly configured"):
        Settings(_env_file=None, app_environment="production")

    with pytest.raises(ValidationError, match=r"cannot contain '\*'"):
        Settings(
            _env_file=None,
            app_environment="production",
            app_trusted_hosts="*",
        )


def test_production_rejects_debug_logging_and_accepts_explicit_safe_configuration() -> None:
    with pytest.raises(ValidationError, match="cannot be DEBUG"):
        Settings(
            _env_file=None,
            app_environment="production",
            app_log_level="DEBUG",
            app_trusted_hosts="api.example.test",
        )

    settings = Settings(
        _env_file=None,
        app_environment="production",
        app_log_level="INFO",
        app_trusted_hosts="api.example.test,health.internal.example.test",
    )
    assert settings.trusted_hosts == (
        "api.example.test",
        "health.internal.example.test",
    )


def test_production_configuration_can_be_supplied_by_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENVIRONMENT", "production")
    monkeypatch.setenv("APP_LOG_LEVEL", "WARNING")
    monkeypatch.setenv("APP_TRUSTED_HOSTS", "api.example.test,*.internal.example.test")

    settings = Settings(_env_file=None)

    assert settings.app_environment == "production"
    assert settings.app_log_level == "WARNING"
    assert settings.trusted_hosts == (
        "api.example.test",
        "*.internal.example.test",
    )
