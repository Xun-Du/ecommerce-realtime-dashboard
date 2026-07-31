"""M2 service and HTTP contract tests without a live PostgreSQL dependency."""

import logging
from datetime import UTC, datetime
from decimal import Decimal

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.analytics import (
    AnalyticsDatabaseUnavailable,
    get_funnel,
    get_metrics,
)
from backend.app.services.analytics import (
    logger as analytics_logger,
)

START = datetime(2026, 7, 30, tzinfo=UTC)
END = datetime(2026, 7, 31, tzinfo=UTC)


def test_metrics_calculates_summary_and_hourly_trends(monkeypatch) -> None:
    rows = iter(
        [
            [
                {
                    "dau": 3,
                    "click_users": 2,
                    "purchase_users": 1,
                    "order_count": 2,
                    "gmv": Decimal("50"),
                }
            ],
            [
                {
                    "bucket_start": START,
                    "dau": 2,
                    "click_users": 2,
                    "purchase_users": 1,
                    "order_count": 1,
                    "gmv": Decimal("20"),
                }
            ],
        ]
    )
    monkeypatch.setattr("backend.app.services.analytics._fetch_all", lambda *_: next(rows))

    result = get_metrics(START, END, "hour", "A")

    assert result.dau == 3
    assert result.gmv == Decimal("50")
    assert result.purchase_conversion_rate == Decimal("0.5")
    assert result.aov == Decimal("25")
    assert result.trends[0].start_time == START
    assert result.trends[0].end_time.hour == 1


def test_metrics_returns_null_rates_when_denominators_are_zero(monkeypatch) -> None:
    rows = iter(
        [
            [{"dau": 0, "click_users": 0, "purchase_users": 0, "order_count": 0, "gmv": 0}],
            [],
        ]
    )
    monkeypatch.setattr("backend.app.services.analytics._fetch_all", lambda *_: next(rows))

    result = get_metrics(START, END, "day", None)

    assert result.purchase_conversion_rate is None
    assert result.aov is None
    assert result.trends == []


def test_funnel_reports_drop_off_and_data_quality_issues(monkeypatch) -> None:
    monkeypatch.setattr(
        "backend.app.services.analytics._fetch_all",
        lambda *_: [{"click_users": 10, "cart_users": 12, "buy_users": 3}],
    )

    result = get_funnel(START, END, None)

    assert result.has_data_quality_issue is True
    assert result.steps[0].cumulative_conversion_rate == Decimal("1")
    assert result.steps[1].conversion_rate_from_previous == Decimal("1.2")
    assert result.steps[1].drop_off_users_from_previous == 0
    assert result.steps[2].drop_off_users_from_previous == 9
    assert result.steps[2].drop_off_rate_from_previous == Decimal("0.75")


def test_analytics_api_validates_queries_and_maps_database_failure(monkeypatch) -> None:
    with TestClient(app) as client:
        missing_parameters = client.get("/api/metrics")
        invalid_window = client.get(
            "/api/funnel",
            params={"start_time": END.isoformat(), "end_time": START.isoformat()},
        )
        missing_timezone = client.get(
            "/api/funnel", params={"start_time": "2026-07-30T00:00:00", "end_time": END.isoformat()}
        )

    assert missing_parameters.status_code == 422
    assert invalid_window.status_code == 422
    assert missing_timezone.status_code == 422

    def unavailable(**_: object) -> None:
        raise AnalyticsDatabaseUnavailable

    monkeypatch.setattr("backend.app.api.analytics.get_metrics", unavailable)
    with TestClient(app) as client:
        response = client.get(
            "/api/metrics",
            params={
                "start_time": START.isoformat(),
                "end_time": END.isoformat(),
                "granularity": "hour",
            },
        )

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "database_unavailable"


def test_metrics_api_serializes_decimals_as_json_numbers(monkeypatch) -> None:
    monkeypatch.setattr(
        "backend.app.api.analytics.get_metrics",
        lambda **_: get_metrics_from_rows(),
    )
    with TestClient(app) as client:
        response = client.get(
            "/api/metrics",
            params={
                "start_time": START.isoformat(),
                "end_time": END.isoformat(),
                "granularity": "day",
            },
        )

    body = response.json()
    assert response.status_code == 200
    assert body["gmv"] == 12.34
    assert isinstance(body["gmv"], float)
    assert body["purchase_conversion_rate"] == 0.5
    assert isinstance(body["aov"], float)


def test_database_failure_emits_structured_context(caplog, monkeypatch) -> None:
    def unavailable_engine():
        raise __import__("sqlalchemy.exc", fromlist=["SQLAlchemyError"]).SQLAlchemyError("offline")

    monkeypatch.setattr("backend.app.services.analytics.get_engine", unavailable_engine)
    monkeypatch.setattr(analytics_logger, "propagate", True)
    monkeypatch.setattr(logging.getLogger("dashboard"), "propagate", True)
    caplog.set_level("ERROR", logger="dashboard.analytics")

    try:
        get_funnel(START, END, "B")
    except AnalyticsDatabaseUnavailable:
        pass
    else:
        raise AssertionError("Expected an unavailable database error.")

    record = caplog.records[-1]
    assert record.message == "analytics_database_unavailable"
    assert record.event == "analytics_database_unavailable"
    assert record.experiment_group == "B"


def get_metrics_from_rows():
    """Construct a fixed response without a database for response serialization tests."""
    from backend.app.schemas.analytics import MetricsResponse

    return MetricsResponse(
        start_time=START,
        end_time=END,
        granularity="day",
        experiment_group=None,
        dau=2,
        gmv=Decimal("12.34"),
        order_count=1,
        purchase_conversion_rate=Decimal("0.5"),
        aov=Decimal("12.34"),
        trends=[],
    )


def test_openapi_includes_m2_contracts() -> None:
    with TestClient(app) as client:
        schema = client.get("/openapi.json").json()

    assert "/api/metrics" in schema["paths"]
    assert "/api/funnel" in schema["paths"]
