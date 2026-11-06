"""System API endpoint tests."""

from fastapi.testclient import TestClient

from pharmasense.api.dependencies import get_database_readiness_service
from pharmasense.api.main import app
from pharmasense.config.settings import Settings, get_settings
from pharmasense.db.readiness import DatabaseCheck


class StubReadinessService:
    def __init__(self, result: DatabaseCheck) -> None:
        self.result = result
        self.calls = 0

    def check(self) -> DatabaseCheck:
        self.calls += 1
        return self.result


def test_health_endpoint_reports_liveness() -> None:
    response = TestClient(app).get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "pharmasense-api",
        "version": "0.1.0",
    }


def test_info_endpoint_returns_only_safe_typed_metadata() -> None:
    settings = Settings(
        _env_file=None,
        app_name="PharmaSense Test",
        app_environment="test",
        app_version="9.8.7-test",
    )
    app.dependency_overrides[get_settings] = lambda: settings

    response = TestClient(app).get("/api/v1/info")

    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json() == {
        "application_name": "PharmaSense Test",
        "environment": "test",
        "version": "9.8.7-test",
    }
    serialized = response.text.lower()
    assert "database" not in serialized
    assert "password" not in serialized
    assert "path" not in serialized


def test_readiness_returns_success_after_database_check() -> None:
    service = StubReadinessService(DatabaseCheck(True, "Database connection succeeded."))
    app.dependency_overrides[get_database_readiness_service] = lambda: service

    response = TestClient(app).get("/api/v1/ready")

    app.dependency_overrides.clear()
    assert service.calls == 1
    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_readiness_returns_503_after_database_failure() -> None:
    service = StubReadinessService(DatabaseCheck(False, "Database connection failed."))
    app.dependency_overrides[get_database_readiness_service] = lambda: service

    response = TestClient(app).get("/api/v1/ready")

    app.dependency_overrides.clear()
    assert service.calls == 1
    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "checks": {
            "database": {
                "status": "unavailable",
                "detail": "Database connection failed.",
            }
        },
    }
