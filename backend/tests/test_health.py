"""Tests for the initial API contract."""

from fastapi.testclient import TestClient

from backend.app.main import app


def test_health_check_returns_service_status(monkeypatch) -> None:
    monkeypatch.setattr("backend.app.api.health.database_is_available", lambda: True)
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "connected"}


def test_health_check_returns_503_when_database_is_unavailable(monkeypatch) -> None:
    monkeypatch.setattr("backend.app.api.health.database_is_available", lambda: False)
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "database_unavailable"
