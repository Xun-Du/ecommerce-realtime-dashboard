"""HTTP routes for analytics metrics, funnels, and experiment evaluation."""

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from backend.app.schemas.analytics import (
    ExperimentResponse,
    ExperimentTimeWindowQuery,
    FunnelResponse,
    MetricsQuery,
    MetricsResponse,
    TimeWindowQuery,
)
from backend.app.services.analytics import (
    AnalyticsDatabaseUnavailable,
    get_experiment,
    get_funnel,
    get_metrics,
)

router = APIRouter(prefix="/api", tags=["analytics"])


def database_unavailable() -> HTTPException:
    """Return the stable public failure contract for analytics queries."""
    return HTTPException(
        status_code=503,
        detail={"code": "database_unavailable", "message": "Database connection is unavailable."},
    )


def time_window_query(
    start_time: Annotated[datetime, Query()],
    end_time: Annotated[datetime, Query()],
    experiment_group: Annotated[Literal["A", "B"] | None, Query()] = None,
) -> TimeWindowQuery:
    """Build and validate a shared query model as a normal FastAPI 422 error."""
    try:
        return TimeWindowQuery(
            start_time=start_time, end_time=end_time, experiment_group=experiment_group
        )
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from None


def metrics_query(
    start_time: Annotated[datetime, Query()],
    end_time: Annotated[datetime, Query()],
    granularity: Annotated[Literal["hour", "day"], Query()],
    experiment_group: Annotated[Literal["A", "B"] | None, Query()] = None,
) -> MetricsQuery:
    """Build the metrics-specific query model and preserve validation semantics."""
    try:
        return MetricsQuery(
            start_time=start_time,
            end_time=end_time,
            granularity=granularity,
            experiment_group=experiment_group,
        )
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from None


def experiment_time_window_query(
    start_time: Annotated[datetime, Query()], end_time: Annotated[datetime, Query()]
) -> ExperimentTimeWindowQuery:
    """Validate the experiment window without exposing an individual group filter."""
    try:
        return ExperimentTimeWindowQuery(start_time=start_time, end_time=end_time)
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from None


@router.get("/metrics", response_model=MetricsResponse)
def metrics(query: Annotated[MetricsQuery, Depends(metrics_query)]) -> MetricsResponse:
    try:
        return get_metrics(**query.model_dump())
    except AnalyticsDatabaseUnavailable:
        raise database_unavailable() from None


@router.get("/funnel", response_model=FunnelResponse)
def funnel(query: Annotated[TimeWindowQuery, Depends(time_window_query)]) -> FunnelResponse:
    try:
        return get_funnel(**query.model_dump())
    except AnalyticsDatabaseUnavailable:
        raise database_unavailable() from None


@router.get("/experiment", response_model=ExperimentResponse)
def experiment(
    query: Annotated[ExperimentTimeWindowQuery, Depends(experiment_time_window_query)]
) -> ExperimentResponse:
    try:
        return get_experiment(query.start_time, query.end_time)
    except AnalyticsDatabaseUnavailable:
        raise database_unavailable() from None
