"""System API endpoint tests."""

from fastapi.testclient import TestClient

from pharmasense.api.dependencies import get_database_readiness_service
from pharmasense.api.main import app
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
