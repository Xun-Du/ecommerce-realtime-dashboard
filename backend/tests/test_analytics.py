"""Analytics service and HTTP contract tests without a live PostgreSQL dependency."""

import logging
from datetime import UTC, datetime
from decimal import Decimal

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.analytics import (
    AnalyticsDatabaseUnavailable,
    _where_clause,
    get_experiment,
    get_funnel,
    get_metrics,
)
from backend.app.services.analytics import (
    logger as analytics_logger,
)
from backend.app.services.experiment import decision_for, evaluate_proportions

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


def test_group_filter_clause_types_the_optional_null_parameter() -> None:
    """PostgreSQL must know the parameter type when the dashboard selects all groups."""
    clause = _where_clause()

    assert "CAST(:experiment_group AS VARCHAR) IS NULL" in clause
    assert "experiment_group = CAST(:experiment_group AS VARCHAR)" in clause


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


def test_funnel_accepts_a_monotonic_three_step_funnel(monkeypatch) -> None:
    monkeypatch.setattr(
        "backend.app.services.analytics._fetch_all",
        lambda *_: [{"click_users": 100, "cart_users": 40, "buy_users": 15}],
    )

    result = get_funnel(START, END, None)

    assert result.has_data_quality_issue is False
    assert [step.users for step in result.steps] == [100, 40, 15]


def test_experiment_returns_significant_positive_result(monkeypatch) -> None:
    monkeypatch.setattr(
        "backend.app.services.analytics._fetch_all",
        lambda *_: [
            {
                "experiment_group": "A",
                "click_users": 1000,
                "cart_users": 200,
                "purchase_users": 100,
                "order_count": 110,
                "gmv": Decimal("2200"),
            },
            {
                "experiment_group": "B",
                "click_users": 1000,
                "cart_users": 300,
                "purchase_users": 180,
                "order_count": 190,
                "gmv": Decimal("4180"),
            },
        ],
    )

    result = get_experiment(START, END)

    assert result.groups["A"].conversion_rate == Decimal("0.1")
    assert result.groups["B"].add_to_cart_rate == Decimal("0.3")
    assert result.uplift == Decimal("0.8")
    assert result.p_value is not None and result.p_value < Decimal("0.05")
    assert result.decision.code == "significantly_better"
    assert result.decision.level == "success"


def test_experiment_handles_missing_groups_and_zero_denominators(monkeypatch) -> None:
    monkeypatch.setattr("backend.app.services.analytics._fetch_all", lambda *_: [])

    result = get_experiment(START, END)

    assert result.groups["A"].conversion_rate is None
    assert result.groups["B"].aov is None
    assert result.uplift is None
    assert result.p_value is None
    assert result.decision.code == "insufficient_sample"


def test_experiment_does_not_publish_p_value_before_minimum_sample(monkeypatch) -> None:
    monkeypatch.setattr(
        "backend.app.services.analytics._fetch_all",
        lambda *_: [
            {
                "experiment_group": "A",
                "click_users": 99,
                "cart_users": 20,
                "purchase_users": 10,
                "order_count": 10,
                "gmv": Decimal("100"),
            },
            {
                "experiment_group": "B",
                "click_users": 100,
                "cart_users": 40,
                "purchase_users": 30,
                "order_count": 30,
                "gmv": Decimal("300"),
            },
        ],
    )

    result = get_experiment(START, END)

    assert result.uplift is not None
    assert result.p_value is None
    assert result.decision.code == "insufficient_sample"


def test_experiment_decision_priority_and_statistical_edge_cases() -> None:
    positive = evaluate_proportions(1000, 100, 1000, 180)
    negative = evaluate_proportions(1000, 180, 1000, 100)
    equal_zero = evaluate_proportions(1000, 0, 1000, 0)

    assert positive.p_value is not None and positive.p_value < Decimal("0.05")
    assert negative.uplift is not None and negative.uplift < 0
    assert equal_zero.uplift is None
    assert equal_zero.p_value == Decimal("1")
    assert decision_for(
        clicks_a=1000,
        clicks_b=1000,
        minimum_sample_size=100,
        rate_a=Decimal("0.18"),
        rate_b=Decimal("0.1"),
        p_value=negative.p_value,
    ).code == "significantly_worse"
    assert decision_for(
        clicks_a=1000,
        clicks_b=1000,
        minimum_sample_size=100,
        rate_a=Decimal("0.1"),
        rate_b=Decimal("0.105"),
        p_value=Decimal("0.8"),
    ).code == "no_significant_difference"


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


def test_experiment_api_serializes_and_maps_database_failure(monkeypatch) -> None:
    monkeypatch.setattr(
        "backend.app.api.analytics.get_experiment",
        lambda *_: get_experiment_from_rows(),
    )
    with TestClient(app) as client:
        response = client.get(
            "/api/experiment", params={"start_time": START.isoformat(), "end_time": END.isoformat()}
        )

    body = response.json()
    assert response.status_code == 200
    assert body["groups"]["A"]["gmv"] == 12.34
    assert isinstance(body["uplift"], float)
    assert body["decision"]["code"] == "significantly_better"

    def unavailable(*_: object) -> None:
        raise AnalyticsDatabaseUnavailable

    monkeypatch.setattr("backend.app.api.analytics.get_experiment", unavailable)
    with TestClient(app) as client:
        unavailable_response = client.get(
            "/api/experiment", params={"start_time": START.isoformat(), "end_time": END.isoformat()}
        )
    assert unavailable_response.status_code == 503


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


def get_experiment_from_rows():
    """Construct a fixed M3 response without a database for serialization tests."""
    from backend.app.schemas.analytics import (
        ExperimentDecision,
        ExperimentGroupMetrics,
        ExperimentResponse,
    )

    group = ExperimentGroupMetrics(
        click_users=100,
        add_to_cart_users=20,
        purchase_users=10,
        conversion_rate=Decimal("0.1"),
        add_to_cart_rate=Decimal("0.2"),
        gmv=Decimal("12.34"),
        aov=Decimal("12.34"),
        order_count=1,
    )
    return ExperimentResponse(
        experiment_id="homepage_checkout_v1",
        primary_metric="purchase_conversion_rate",
        minimum_sample_size=100,
        start_time=START,
        end_time=END,
        groups={"A": group, "B": group},
        uplift=Decimal("0.1"),
        p_value=Decimal("0.01"),
        decision=ExperimentDecision(
            code="significantly_better", message="test", level="success"
        ),
    )


def test_openapi_includes_analytics_contracts() -> None:
    with TestClient(app) as client:
        schema = client.get("/openapi.json").json()

    assert "/api/metrics" in schema["paths"]
    assert "/api/funnel" in schema["paths"]
    assert "/api/experiment" in schema["paths"]
    experiment_parameters = schema["paths"]["/api/experiment"]["get"]["parameters"]
    assert {parameter["name"] for parameter in experiment_parameters} == {
        "start_time",
        "end_time",
    }
