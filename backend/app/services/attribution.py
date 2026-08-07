"""Explainable rule-based marketing attribution over purchase and click facts."""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from functools import lru_cache

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from backend.app.core.database import get_engine
from backend.app.schemas.analytics import (
    AttributionCampaign,
    AttributionChannel,
    AttributionDataQuality,
    AttributionModel,
    AttributionPath,
    AttributionResponse,
    AttributionTouchpoint,
)
from backend.app.services.analytics import AnalyticsDatabaseUnavailable

ZERO = Decimal("0")
ONE = Decimal("1")
LOOKBACK_DAYS = 30
MAX_PATHS_PER_CHANNEL = 5
logger = logging.getLogger("dashboard.attribution")


@dataclass(frozen=True)
class _Touchpoint:
    created_at: datetime
    channel: str
    source: str | None
    medium: str | None
    campaign_id: str | None
    campaign_name: str | None
    session_id: str


def get_attribution(
    start_time: datetime,
    end_time: datetime,
    model: AttributionModel,
    channel: str | None = None,
    campaign_id: str | None = None,
) -> AttributionResponse:
    lookback_start = start_time - timedelta(days=LOOKBACK_DAYS)
    rows = _fetch_attribution_rows(lookback_start, end_time)
    return attribute_rows(
        rows, start_time, end_time, model, channel=channel, campaign_id=campaign_id
    )


def attribute_rows(
    rows: list[dict],
    start_time: datetime,
    end_time: datetime,
    model: AttributionModel,
    *,
    channel: str | None = None,
    campaign_id: str | None = None,
) -> AttributionResponse:
    """Pure attribution calculation, kept separate so it is easy to test."""
    buys: dict[str, dict] = {}
    clicks: dict[str, list[_Touchpoint]] = defaultdict(list)
    for row in rows:
        created_at = row["created_at"]
        if row["event_type"] == "buy" and start_time <= created_at < end_time:
            order_id = str(row.get("order_id") or row["event_id"])
            buys.setdefault(order_id, row)
        elif row["event_type"] == "click":
            raw_channel = (row.get("channel") or "").strip()
            if not raw_channel:
                continue
            clicks[str(row["user_id"])].append(
                _Touchpoint(
                    created_at=created_at,
                    channel=raw_channel,
                    source=row.get("source"),
                    medium=row.get("medium"),
                    campaign_id=row.get("campaign_id"),
                    campaign_name=row.get("campaign_name"),
                    session_id=str(row["session_id"]),
                )
            )

    for user_id in clicks:
        clicks[user_id] = _fold_touchpoints(sorted(clicks[user_id], key=lambda p: p.created_at))

    total_orders = len(buys)
    total_gmv = sum((Decimal(row.get("order_value") or 0) for row in buys.values()), ZERO)
    channel_orders: defaultdict[str, Decimal] = defaultdict(lambda: ZERO)
    channel_gmv: defaultdict[str, Decimal] = defaultdict(lambda: ZERO)
    campaign_orders: defaultdict[tuple[str | None, str | None], Decimal] = defaultdict(
        lambda: ZERO
    )
    campaign_gmv: defaultdict[tuple[str | None, str | None], Decimal] = defaultdict(lambda: ZERO)
    paths: list[tuple[str, AttributionPath]] = []
    unknown_orders = ZERO
    unknown_gmv = ZERO
    missing_campaign_count = 0
    no_touchpoint_orders = 0

    for order_id, buy in sorted(buys.items(), key=lambda item: item[1]["created_at"]):
        order_value = Decimal(buy.get("order_value") or 0)
        candidates = [
            point
            for point in clicks.get(str(buy["user_id"]), [])
            if point.created_at < buy["created_at"]
            and (buy["created_at"] - timedelta(days=LOOKBACK_DAYS)) <= point.created_at
            and (channel is None or point.channel == channel)
            and (campaign_id is None or point.campaign_id == campaign_id)
        ]
        if not candidates:
            unknown_orders += Decimal("1")
            unknown_gmv += order_value
            no_touchpoint_orders += 1
            paths.append(("unknown", _path(order_id, buy, candidates)))
            continue
        selected = _select_touchpoints(candidates, model)
        weight = Decimal("1") / Decimal(len(selected))
        for point in selected:
            channel_orders[point.channel] += weight
            channel_gmv[point.channel] += order_value * weight
            key = (point.campaign_id, point.campaign_name)
            campaign_orders[key] += weight
            campaign_gmv[key] += order_value * weight
        paths.append((selected[0].channel, _path(order_id, buy, candidates)))
        missing_campaign_count += int(any(point.campaign_id is None for point in candidates))

    attributed_orders = sum(channel_orders.values(), ZERO)
    attributed_gmv = sum(channel_gmv.values(), ZERO)
    if unknown_orders:
        channel_orders["unknown"] += unknown_orders
        channel_gmv["unknown"] += unknown_gmv
    channels = _channel_rows(channel_orders, channel_gmv, total_gmv)
    campaigns = _campaign_rows(campaign_orders, campaign_gmv, total_gmv)
    unknown_share = _bounded_ratio(unknown_gmv, total_gmv)
    missing_share = (
        Decimal(missing_campaign_count) / Decimal(max(total_orders, 1)) if total_orders else ZERO
    )
    warnings: list[str] = []
    if unknown_share > Decimal("0.2"):
        warnings.append("未知渠道占比超过 20%，请检查触点采集或渠道映射。")
    if no_touchpoint_orders:
        warnings.append("部分订单没有购买前有效触点，已计入 unknown。")
    if missing_campaign_count:
        warnings.append("部分有效触点缺少 campaign 信息，活动下钻可能不完整。")

    per_channel_count: defaultdict[str, int] = defaultdict(int)
    touchpoint_paths = []
    for path_channel, path in paths:
        if per_channel_count[path_channel] < MAX_PATHS_PER_CHANNEL:
            touchpoint_paths.append(path)
            per_channel_count[path_channel] += 1
    return AttributionResponse(
        start_time=start_time,
        end_time=end_time,
        lookback_start=start_time - timedelta(days=LOOKBACK_DAYS),
        model=model,
        total_orders=total_orders,
        total_gmv=total_gmv,
        attributed_orders=attributed_orders,
        attributed_gmv=attributed_gmv,
        unknown_orders=unknown_orders,
        unknown_gmv=unknown_gmv,
            coverage_rate=_bounded_ratio(attributed_gmv, total_gmv),
        channels=channels,
        campaigns=campaigns,
        touchpoint_paths=touchpoint_paths,
        data_quality=AttributionDataQuality(
            unknown_channel_share=unknown_share,
            missing_campaign_count=missing_campaign_count,
            missing_campaign_share=missing_share,
            no_valid_touchpoint_orders=no_touchpoint_orders,
            warnings=warnings,
        ),
    )


def _fold_touchpoints(points: list[_Touchpoint]) -> list[_Touchpoint]:
    folded: list[_Touchpoint] = []
    for point in points:
        if folded and (
            folded[-1].session_id,
            folded[-1].channel,
            folded[-1].campaign_id,
        ) == (point.session_id, point.channel, point.campaign_id):
            continue
        folded.append(point)
    return folded


def _select_touchpoints(points: list[_Touchpoint], model: AttributionModel) -> list[_Touchpoint]:
    if model == "first_touch":
        return points[:1]
    if model == "last_touch":
        return points[-1:]
    return points


def _path(order_id: str, buy: dict, points: list[_Touchpoint]) -> AttributionPath:
    return AttributionPath(
        order_id=order_id,
        order_time=buy["created_at"],
        order_value=Decimal(buy.get("order_value") or 0),
        touchpoints=[
            AttributionTouchpoint(
                created_at=p.created_at,
                channel=p.channel,
                source=p.source,
                medium=p.medium,
                campaign_id=p.campaign_id,
                campaign_name=p.campaign_name,
            )
            for p in points
        ],
    )


def _channel_rows(
    orders: dict[str, Decimal], gmvs: dict[str, Decimal], total_gmv: Decimal
) -> list[AttributionChannel]:
    names = sorted(orders, key=lambda name: (-gmvs[name], name))
    return [
        AttributionChannel(
            channel=name,
            order_credit=orders[name],
            gmv_credit=gmvs[name],
            gmv_share=_bounded_ratio(gmvs[name], total_gmv),
            rank=index,
        )
        for index, name in enumerate(names, 1)
    ]


def _campaign_rows(
    orders: dict[tuple[str | None, str | None], Decimal],
    gmvs: dict[tuple[str | None, str | None], Decimal],
    total_gmv: Decimal,
) -> list[AttributionCampaign]:
    keys = [key for key in orders if key[0] is not None]
    keys.sort(key=lambda key: (-gmvs[key], str(key[0])))
    return [
        AttributionCampaign(
            channel="all",
            campaign_id=key[0],
            campaign_name=key[1],
            order_credit=orders[key],
            gmv_credit=gmvs[key],
            gmv_share=_bounded_ratio(gmvs[key], total_gmv),
            rank=index,
        )
        for index, key in enumerate(keys, 1)
    ]


@lru_cache(maxsize=32)
def _fetch_attribution_rows(start_time: datetime, end_time: datetime) -> list[dict]:
    """Fetch one raw window for all models; model calculations reuse this result."""
    statement = """
        SELECT event_id, user_id, session_id, event_type, channel, source, medium,
               campaign_id, campaign_name, order_id, order_value, created_at
        FROM events
        WHERE created_at >= :start_time AND created_at < :end_time
          AND event_type IN ('buy', 'click')
    """
    params = {"start_time": start_time, "end_time": end_time}
    for attempt in range(2):
        try:
            with get_engine().connect() as connection:
                return [
                    dict(row)
                    for row in connection.execute(text(statement), params).mappings()
                ]
        except SQLAlchemyError as exc:
            logger.warning(
                "attribution_database_query_failed",
                extra={
                    "event": "attribution_database_query_failed",
                    "attempt": attempt + 1,
                    "error_type": type(exc).__name__,
                    "error": _safe_database_error(exc),
                },
                exc_info=attempt == 1,
            )
            if attempt == 0 and _is_retryable_connection_error(exc):
                get_engine().dispose()
                continue
            raise AnalyticsDatabaseUnavailable from exc


def _bounded_ratio(numerator: Decimal, denominator: Decimal) -> Decimal:
    if not denominator:
        return ZERO
    return min(max(numerator / denominator, ZERO), ONE)


def _safe_database_error(error: SQLAlchemyError) -> str:
    """Keep useful database diagnostics while excluding connection credentials."""
    message = str(error)
    for secret_marker in ("postgresql+psycopg://", "postgresql://"):
        if secret_marker in message:
            message = message.split(secret_marker, 1)[0] + "<redacted>"
    return message[:500]


def _is_retryable_connection_error(error: SQLAlchemyError) -> bool:
    message = str(error).lower()
    return "ssl connection has been closed" in message or "connection reset" in message
