"""Health-check route for the API service."""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["system"])


class HealthResponse(BaseModel):
    """Response returned while database monitoring is deferred to M1."""

    status: str
    database: str


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    """Report that the HTTP service is live."""
    return HealthResponse(status="ok", database="not_checked")
