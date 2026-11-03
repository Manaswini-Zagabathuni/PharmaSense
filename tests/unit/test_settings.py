"""Settings tests."""

from pydantic import SecretStr
from sqlalchemy import URL

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
