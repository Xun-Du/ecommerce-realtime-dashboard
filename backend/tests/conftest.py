"""Test environment configuration."""

import os

import pytest


@pytest.fixture(autouse=True)
def configured_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provide safe, non-secret settings to every test."""
    values = {
        "DATABASE_URL": "postgresql+psycopg://user:password@localhost:5432/dashboard",
        "SUPABASE_URL": "https://example.supabase.co",
        "SUPABASE_SERVICE_ROLE_KEY": "test-service-role-key",
        "API_BASE_URL": "http://localhost:8000",
        "STREAMLIT_SERVER_PORT": "8501",
        "SIMULATOR_INTERVAL_SECONDS": "5",
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)

    from backend.app.core.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
    for name in values:
        os.environ.pop(name, None)
