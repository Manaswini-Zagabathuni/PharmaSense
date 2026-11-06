"""Request observability and privacy-safety tests."""

import json
import logging
from typing import cast
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from pharmasense.api.main import create_app
from pharmasense.api.observability import REQUEST_ID_HEADER


def _app_with_test_routes() -> FastAPI:
    application = create_app()

    @application.get("/test/ok")
    def ok() -> dict[str, str]:
        return {"status": "ok"}

    @application.get("/test/failure")
    def failure() -> None:
        raise RuntimeError("private exception detail")

    @application.get("/test/items/{item_name}")
    def item(item_name: str) -> dict[str, str]:
        return {"item": item_name}

    return application


def _request_event(caplog: pytest.LogCaptureFixture) -> dict[str, object]:
    records = [
        record for record in caplog.records if record.name == "pharmasense.api.observability"
    ]
    assert len(records) == 1
    return cast(dict[str, object], json.loads(records[0].message))


def test_request_id_is_generated_returned_and_timed(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="pharmasense.api.observability")

    response = TestClient(_app_with_test_routes()).get("/test/ok?ignored=value")

    request_id = response.headers[REQUEST_ID_HEADER]
    assert UUID(request_id).hex == request_id
    event = _request_event(caplog)
    assert event["event"] == "http_request_completed"
    assert event["request_id"] == request_id
    assert event["method"] == "GET"
    assert event["path"] == "/test/ok"
    assert event["status_code"] == 200
    duration_ms = event["duration_ms"]
    assert isinstance(duration_ms, int | float)
    assert duration_ms >= 0
    assert "ignored" not in json.dumps(event)


def test_valid_client_request_id_is_preserved(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="pharmasense.api.observability")
    request_id = "client-request_123.example"

    response = TestClient(_app_with_test_routes()).get(
        "/test/ok", headers={REQUEST_ID_HEADER: request_id}
    )

    assert response.headers[REQUEST_ID_HEADER] == request_id
    assert _request_event(caplog)["request_id"] == request_id


def test_generated_request_ids_are_unique_per_request() -> None:
    client = TestClient(_app_with_test_routes())

    first = client.get("/test/ok").headers[REQUEST_ID_HEADER]
    second = client.get("/test/ok").headers[REQUEST_ID_HEADER]

    assert first != second


def test_request_log_uses_route_template_not_path_parameter(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="pharmasense.api.observability")

    response = TestClient(_app_with_test_routes()).get("/test/items/private-source-value")

    assert response.status_code == 200
    event = _request_event(caplog)
    assert event["path"] == "/test/items/{item_name}"
    assert "private-source-value" not in json.dumps(event)


def test_invalid_client_request_id_is_replaced() -> None:
    response = TestClient(_app_with_test_routes()).get(
        "/test/ok", headers={REQUEST_ID_HEADER: "invalid request id"}
    )

    replacement = response.headers[REQUEST_ID_HEADER]
    assert replacement != "invalid request id"
    assert UUID(replacement).hex == replacement


def test_unexpected_exception_is_sanitized_and_correlated(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO)

    response = TestClient(_app_with_test_routes(), raise_server_exceptions=False).get(
        "/test/failure"
    )

    assert response.status_code == 500
    assert response.text == "Internal Server Error"
    assert REQUEST_ID_HEADER in response.headers
    assert _request_event(caplog)["status_code"] == 500
    assert "private exception detail" not in caplog.text
