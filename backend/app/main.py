"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.app.api.analytics import router as analytics_router
from backend.app.api.health import router as health_router
from backend.app.core.config import get_settings
from backend.app.core.logging import configure_logging


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Validate required configuration before accepting requests."""
    configure_logging()
    get_settings()
    yield


app = FastAPI(
    title="E-commerce Real-time A/B & Attribution Dashboard API",
    version="0.1.0",
    lifespan=lifespan,
)
app.include_router(health_router)
app.include_router(analytics_router)
