"""HTTP client boundary for the future dashboard API integration."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ApiClient:
    """Stores the API base URL without accessing the database from the frontend."""

    base_url: str
