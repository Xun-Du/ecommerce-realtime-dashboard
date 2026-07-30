"""Tests for the initial API contract."""

from fastapi.testclient import TestClient

from backend.app.main import app


def test_health_check_returns_service_status() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "not_checked"}
