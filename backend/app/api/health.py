"""Health-check route for the API service."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.app.core.database import database_is_available

router = APIRouter(tags=["system"])


class HealthResponse(BaseModel):
    """Response returned when the API and Supabase database are available."""

    status: str
    database: str


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    """Report API and database readiness without leaking connection details."""
    if not database_is_available():
        raise HTTPException(
            status_code=503,
            detail={
                "code": "database_unavailable",
                "message": "Database connection is unavailable.",
            },
        )
    return HealthResponse(status="ok", database="connected")
