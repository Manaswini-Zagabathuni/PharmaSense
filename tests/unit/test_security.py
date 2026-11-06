"""HTTP hardening and trusted-host behavior tests."""

from collections.abc import Mapping

from fastapi import FastAPI
from fastapi.testclient import TestClient

from pharmasense.api.main import create_app
from pharmasense.api.observability import REQUEST_ID_HEADER
from pharmasense.api.security import SECURITY_HEADERS
from pharmasense.config.settings import Settings


def _assert_security_headers(response_headers: Mapping[str, str]) -> None:
    for name, value in SECURITY_HEADERS.items():
        assert response_headers[name] == value


def test_successful_api_response_keeps_schema_and_adds_security_headers() -> None:
    request_id = "security-test-request"
    response = TestClient(create_app(Settings(_env_file=None))).get(
        "/api/v1/health", headers={REQUEST_ID_HEADER: request_id}
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "pharmasense-api",
        "version": "0.1.0",
    }
    assert response.headers[REQUEST_ID_HEADER] == request_id
    _assert_security_headers(response.headers)


def test_disallowed_host_is_rejected_with_request_id_and_security_headers() -> None:
    application = create_app(Settings(_env_file=None, app_trusted_hosts="api.example.test"))

    response = TestClient(application).get(
        "/api/v1/health", headers={"Host": "untrusted.example.test"}
    )

    assert response.status_code == 400
    assert response.text == "Invalid host header"
    assert REQUEST_ID_HEADER in response.headers
    _assert_security_headers(response.headers)


def test_configured_host_is_allowed() -> None:
    application = create_app(Settings(_env_file=None, app_trusted_hosts="api.example.test"))

    response = TestClient(application, base_url="http://api.example.test").get("/api/v1/info")

    assert response.status_code == 200
    assert response.json()["application_name"] == "PharmaSense"


def test_unexpected_error_remains_sanitized_and_hardened() -> None:
    application: FastAPI = create_app(Settings(_env_file=None))

    @application.get("/test/security-failure")
    def failure() -> None:
        raise RuntimeError("database_url=mysql://user:secret@internal/private")

    response = TestClient(application, raise_server_exceptions=False).get("/test/security-failure")

    assert response.status_code == 500
    assert response.text == "Internal Server Error"
    assert "secret" not in response.text
    assert "mysql" not in response.text
    assert REQUEST_ID_HEADER in response.headers
    _assert_security_headers(response.headers)
