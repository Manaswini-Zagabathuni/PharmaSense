"""Settings tests."""

import pytest
from pydantic import SecretStr
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
