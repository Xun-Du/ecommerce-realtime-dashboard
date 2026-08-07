from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.attribution import attribute_rows

START = datetime(2026, 7, 30, tzinfo=UTC)
END = datetime(2026, 7, 31, tzinfo=UTC)


def _row(
    event_type: str,
    at: datetime,
    *,
    user: str = "u1",
    channel: str = "search",
    order: str | None = None,
    value: Decimal | None = None,
    session: str = "s1",
    campaign: str | None = "c1",
) -> dict:
    return {
        "event_id": str(uuid4()),
        "user_id": user,
        "session_id": session,
        "event_type": event_type,
        "channel": channel,
        "source": "google",
        "medium": "cpc",
        "campaign_id": campaign,
        "campaign_name": "Campaign",
        "order_id": order,
        "order_value": value,
        "created_at": at,
    }


def test_models_and_duplicate_touchpoints_preserve_gmv() -> None:
    rows = [
        _row("click", START - timedelta(days=1), channel="social", session="s1", campaign="s1"),
        _row(
            "click",
            START - timedelta(days=1, seconds=-1),
            channel="social",
            session="s1",
            campaign="s1",
        ),
        _row("click", START - timedelta(hours=1), channel="email", session="s2", campaign="e1"),
        _row("buy", START + timedelta(hours=1), order="o1", value=Decimal("100")),
    ]
    first = attribute_rows(rows, START, END, "first_touch")
    last = attribute_rows(rows, START, END, "last_touch")
    linear = attribute_rows(rows, START, END, "linear")
    assert first.channels[0].channel == "social"
    assert last.channels[0].channel == "email"
    assert linear.attributed_gmv == Decimal("100")
    assert sum(item.gmv_share for item in linear.channels) == Decimal("1")


def test_unknown_and_window_boundary_are_explicit() -> None:
    rows = [
        _row("buy", START, order="o1", value=Decimal("10"), channel=""),
        _row("buy", END, order="o2", value=Decimal("20"), channel=""),
    ]
    result = attribute_rows(rows, START, END, "last_touch")
    assert result.total_orders == 1
    assert result.unknown_orders == Decimal("1")
    assert result.unknown_gmv == Decimal("10")
    assert result.coverage_rate == Decimal("0")


def test_attribution_api_rejects_invalid_model() -> None:
    with TestClient(app) as client:
        response = client.get(
            "/api/attribution",
            params={"start_time": START.isoformat(), "end_time": END.isoformat(), "model": "bad"},
        )
    assert response.status_code == 422
