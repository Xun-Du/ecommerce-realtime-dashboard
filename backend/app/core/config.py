"""Environment-backed application settings."""

from functools import lru_cache
from urllib.parse import urlparse

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings required by the API and the future event simulator.

    Values are read from environment variables first, then from a local `.env` file.
    The file is deliberately ignored by Git; use `.env.example` as its template.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = Field(validation_alias="DATABASE_URL")
    supabase_url: str = Field(validation_alias="SUPABASE_URL")
    supabase_service_role_key: str = Field(validation_alias="SUPABASE_SERVICE_ROLE_KEY")
    api_base_url: str = Field(validation_alias="API_BASE_URL")
    streamlit_server_port: int = Field(validation_alias="STREAMLIT_SERVER_PORT")
    simulator_interval_seconds: int = Field(validation_alias="SIMULATOR_INTERVAL_SECONDS")

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        if not value.startswith(("postgresql://", "postgresql+psycopg://")):
            raise ValueError("DATABASE_URL must use a PostgreSQL URL.")
        return value

    @field_validator("supabase_url", "api_base_url")
    @classmethod
    def validate_http_url(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("must be a complete http(s) URL.")
        return value.rstrip("/")

    @field_validator("supabase_service_role_key")
    @classmethod
    def validate_service_key(cls, value: str) -> str:
        if not value or value == "replace_me":
            raise ValueError("SUPABASE_SERVICE_ROLE_KEY must be set to a non-placeholder value.")
        return value

    @field_validator("streamlit_server_port")
    @classmethod
    def validate_streamlit_port(cls, value: int) -> int:
        if not 1 <= value <= 65535:
            raise ValueError("STREAMLIT_SERVER_PORT must be between 1 and 65535.")
        return value

    @field_validator("simulator_interval_seconds")
    @classmethod
    def validate_simulator_interval(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("SIMULATOR_INTERVAL_SECONDS must be greater than zero.")
        return value


@lru_cache
def get_settings() -> Settings:
    """Create and cache validated process settings."""
    return Settings()
