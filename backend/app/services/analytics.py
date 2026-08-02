"""Database-backed business calculations for metrics, funnels, and experiments."""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Literal

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from backend.app.core.database import get_engine
from backend.app.schemas.analytics import (
    ExperimentGroupMetrics,
    ExperimentResponse,
    FunnelResponse,
    FunnelStep,
    MetricsResponse,
    TrendPoint,
)
from backend.app.services.experiment import decision_for, evaluate_proportions

ZERO = Decimal("0")
DEFAULT_EXPERIMENT_ID = "homepage_checkout_v1"
MINIMUM_EXPERIMENT_SAMPLE_SIZE = 100
EventGroup = Literal["A", "B"] | None
logger = logging.getLogger("dashboard.analytics")


class AnalyticsDatabaseUnavailable(Exception):
    """Raised when an analytics query cannot reach the database."""


def get_metrics(
    start_time: datetime,
    end_time: datetime,
    granularity: Literal["hour", "day"],
    experiment_group: EventGroup,
) -> MetricsResponse:
    """Return overview metrics and UTC-aligned time buckets for a window."""
    summary = _fetch_one(_summary_statement(), start_time, end_time, experiment_group)
    bucket_expression = (
        "date_trunc('hour', created_at)"
        if granularity == "hour"
        else "date_trunc('day', created_at)"
    )
    trends = _fetch_all(
        _trend_statement(bucket_expression), start_time, end_time, experiment_group
    )
    bucket_size = timedelta(hours=1) if granularity == "hour" else timedelta(days=1)
    return MetricsResponse(
        start_time=start_time,
        end_time=end_time,
        granularity=granularity,
        experiment_group=experiment_group,
        **_metric_values(summary),
        trends=[
            TrendPoint(
                start_time=row["bucket_start"],
                end_time=row["bucket_start"] + bucket_size,
                **_metric_values(row),
            )
            for row in trends
        ],
    )


def get_funnel(
    start_time: datetime, end_time: datetime, experiment_group: EventGroup
) -> FunnelResponse:
    """Return the fixed three-step, user-deduplicated conversion funnel."""
    row = _fetch_one(_funnel_statement(), start_time, end_time, experiment_group)
    counts = [int(row[name] or 0) for name in ("click_users", "cart_users", "buy_users")]
    names: list[Literal["click", "add_to_cart", "buy"]] = ["click", "add_to_cart", "buy"]
    steps: list[FunnelStep] = []
    for index, (name, users) in enumerate(zip(names, counts, strict=True)):
        previous = counts[index - 1] if index else None
        steps.append(
            FunnelStep(
                event_type=name,
                users=users,
                conversion_rate_from_previous=_ratio(users, previous),
                cumulative_conversion_rate=(
                    _ratio(users, counts[0]) if index else _ratio(users, users)
                ),
                drop_off_users_from_previous=(
                    max(previous - users, 0) if previous is not None else None
                ),
                drop_off_rate_from_previous=(
                    _ratio(max(previous - users, 0), previous) if previous is not None else None
                ),
            )
        )
    return FunnelResponse(
        start_time=start_time,
        end_time=end_time,
        experiment_group=experiment_group,
        steps=steps,
        has_data_quality_issue=any(
            current > previous for previous, current in zip(counts, counts[1:], strict=True)
        ),
    )


def get_experiment(start_time: datetime, end_time: datetime) -> ExperimentResponse:
    """Evaluate the default A/B experiment over a selected time window."""
    rows = _fetch_all(_experiment_statement(), start_time, end_time, None)
    by_group = {row["experiment_group"]: row for row in rows}
    groups = {
        group: _experiment_group_metrics(by_group.get(group, {})) for group in ("A", "B")
    }
    rate_a = groups["A"].conversion_rate
    rate_b = groups["B"].conversion_rate
    test = evaluate_proportions(
        groups["A"].click_users,
        groups["A"].purchase_users,
        groups["B"].click_users,
        groups["B"].purchase_users,
    )
    p_value = (
        test.p_value
        if groups["A"].click_users >= MINIMUM_EXPERIMENT_SAMPLE_SIZE
        and groups["B"].click_users >= MINIMUM_EXPERIMENT_SAMPLE_SIZE
        else None
    )
    return ExperimentResponse(
        experiment_id=DEFAULT_EXPERIMENT_ID,
        primary_metric="purchase_conversion_rate",
        minimum_sample_size=MINIMUM_EXPERIMENT_SAMPLE_SIZE,
        start_time=start_time,
        end_time=end_time,
        groups=groups,
        uplift=test.uplift,
        p_value=p_value,
        decision=decision_for(
            clicks_a=groups["A"].click_users,
            clicks_b=groups["B"].click_users,
            minimum_sample_size=MINIMUM_EXPERIMENT_SAMPLE_SIZE,
            rate_a=rate_a,
            rate_b=rate_b,
            p_value=p_value,
        ),
    )


def _metric_values(row: dict) -> dict:
    order_count = int(row["order_count"] or 0)
    click_users = int(row["click_users"] or 0)
    purchase_users = int(row["purchase_users"] or 0)
    gmv = Decimal(row["gmv"] or 0)
    return {
        "dau": int(row["dau"] or 0),
        "gmv": gmv,
        "order_count": order_count,
        "purchase_conversion_rate": _ratio(purchase_users, click_users),
        "aov": _ratio(gmv, order_count),
    }


def _ratio(numerator: int | Decimal, denominator: int | Decimal | None) -> Decimal | None:
    if denominator is None or denominator == 0:
        return None
    return Decimal(numerator) / Decimal(denominator)


def _experiment_group_metrics(row: dict) -> ExperimentGroupMetrics:
    click_users = int(row.get("click_users") or 0)
    cart_users = int(row.get("cart_users") or 0)
    purchase_users = int(row.get("purchase_users") or 0)
    order_count = int(row.get("order_count") or 0)
    gmv = Decimal(row.get("gmv") or 0)
    return ExperimentGroupMetrics(
        click_users=click_users,
        add_to_cart_users=cart_users,
        purchase_users=purchase_users,
        conversion_rate=_ratio(purchase_users, click_users),
        add_to_cart_rate=_ratio(cart_users, click_users),
        gmv=gmv,
        aov=_ratio(gmv, order_count),
        order_count=order_count,
    )


def _fetch_one(statement: str, start_time: datetime, end_time: datetime, group: EventGroup) -> dict:
    rows = _fetch_all(statement, start_time, end_time, group)
    return rows[0]


def _fetch_all(
    statement: str, start_time: datetime, end_time: datetime, group: EventGroup
) -> list[dict]:
    params = {"start_time": start_time, "end_time": end_time, "experiment_group": group}
    try:
        with get_engine().connect() as connection:
            return [dict(row) for row in connection.execute(text(statement), params).mappings()]
    except SQLAlchemyError as exc:
        logger.error(
            "analytics_database_unavailable",
            extra={"event": "analytics_database_unavailable", **params},
            exc_info=True,
        )
        raise AnalyticsDatabaseUnavailable from exc


def _where_clause() -> str:
    return (
        "created_at >= :start_time AND created_at < :end_time "
        "AND (:experiment_group IS NULL OR experiment_group = :experiment_group)"
    )


def _summary_statement() -> str:
    return f"""
        SELECT COUNT(DISTINCT user_id) AS dau,
               COUNT(DISTINCT user_id) FILTER (WHERE event_type = 'click') AS click_users,
               COUNT(DISTINCT user_id) FILTER (WHERE event_type = 'buy') AS purchase_users,
               COUNT(*) FILTER (WHERE event_type = 'buy') AS order_count,
               COALESCE(SUM(order_value) FILTER (WHERE event_type = 'buy'), 0) AS gmv
        FROM events WHERE {_where_clause()}
    """


def _trend_statement(bucket_expression: str) -> str:
    return f"""
        SELECT {bucket_expression} AS bucket_start,
               COUNT(DISTINCT user_id) AS dau,
               COUNT(DISTINCT user_id) FILTER (WHERE event_type = 'click') AS click_users,
               COUNT(DISTINCT user_id) FILTER (WHERE event_type = 'buy') AS purchase_users,
               COUNT(*) FILTER (WHERE event_type = 'buy') AS order_count,
               COALESCE(SUM(order_value) FILTER (WHERE event_type = 'buy'), 0) AS gmv
        FROM events WHERE {_where_clause()}
        GROUP BY bucket_start ORDER BY bucket_start
    """


def _funnel_statement() -> str:
    return f"""
        SELECT COUNT(DISTINCT user_id) FILTER (WHERE event_type = 'click') AS click_users,
               COUNT(DISTINCT user_id) FILTER (WHERE event_type = 'add_to_cart') AS cart_users,
               COUNT(DISTINCT user_id) FILTER (WHERE event_type = 'buy') AS buy_users
        FROM events WHERE {_where_clause()}
    """


def _experiment_statement() -> str:
    return """
        SELECT experiment_group,
               COUNT(DISTINCT user_id) FILTER (WHERE event_type = 'click') AS click_users,
               COUNT(DISTINCT user_id) FILTER (WHERE event_type = 'add_to_cart') AS cart_users,
               COUNT(DISTINCT user_id) FILTER (WHERE event_type = 'buy') AS purchase_users,
               COUNT(*) FILTER (WHERE event_type = 'buy') AS order_count,
               COALESCE(SUM(order_value) FILTER (WHERE event_type = 'buy'), 0) AS gmv
        FROM events
        WHERE created_at >= :start_time AND created_at < :end_time
          AND experiment_group IN ('A', 'B')
        GROUP BY experiment_group
    """
