"""Tests for startup configuration validation."""

import pytest
from pydantic import ValidationError

from backend.app.core.config import Settings


def test_settings_loads_valid_environment() -> None:
    settings = Settings()

    assert settings.streamlit_server_port == 8501
    assert settings.api_base_url == "http://localhost:8000"


def test_settings_rejects_missing_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL")

    with pytest.raises(ValidationError, match="DATABASE_URL"):
        Settings(_env_file=None)


def test_settings_rejects_invalid_simulator_interval(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SIMULATOR_INTERVAL_SECONDS", "0")

    with pytest.raises(ValidationError, match="greater than zero"):
        Settings(_env_file=None)
