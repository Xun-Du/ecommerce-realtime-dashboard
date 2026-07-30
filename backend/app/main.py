"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.app.api.health import router as health_router
from backend.app.core.config import get_settings


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Validate required configuration before accepting requests."""
    get_settings()
    yield


app = FastAPI(
    title="E-commerce Real-time A/B & Attribution Dashboard API",
    version="0.1.0",
    lifespan=lifespan,
)
app.include_router(health_router)
