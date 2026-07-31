"""Deterministic, business-shaped event generation for the M1 Demo."""

from __future__ import annotations

import random
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID, uuid5

CHANNELS = ("organic", "search", "social", "affiliate", "email")
CHANNEL_WEIGHTS = (0.30, 0.25, 0.20, 0.10, 0.15)
CHANNEL_PURCHASE_RATES = {
    "organic": 0.20,
    "search": 0.24,
    "social": 0.15,
    "affiliate": 0.18,
    "email": 0.28,
}
NAMESPACE = UUID("6b6d2cb3-4d2c-4f65-bf38-cf68924bb991")


@dataclass(frozen=True)
class UserRecord:
    user_id: UUID
    first_seen_at: datetime
    acquisition_channel: str
    country: str
    device_type: str

    def as_database_row(self) -> dict[str, object]:
        return self.__dict__


@dataclass(frozen=True)
class EventRecord:
    event_id: UUID
    user_id: UUID
    session_id: UUID
    event_type: str
    experiment_group: str
    channel: str
    product_id: str
    order_value: Decimal | None
    created_at: datetime

    def as_database_row(self) -> dict[str, object]:
        return self.__dict__


@dataclass(frozen=True)
class GeneratedBatch:
    users: list[UserRecord]
    events: list[EventRecord]

    def event_counts(self) -> Counter[str]:
        return Counter(event.event_type for event in self.events)

    def experiment_counts(self) -> Counter[str]:
        return Counter(
            event.experiment_group for event in self.events if event.event_type == "click"
        )


def generate_batch(
    *,
    start_at: datetime,
    end_at: datetime,
    user_count: int,
    seed: int,
    b_uplift: float,
    traffic_split_a: float = 0.5,
) -> GeneratedBatch:
    """Generate valid funnel sessions in a time range using a stable random seed."""
    if start_at.tzinfo is None or end_at.tzinfo is None:
        raise ValueError("start_at and end_at must be timezone-aware.")
    if start_at >= end_at:
        raise ValueError("start_at must be earlier than end_at.")
    if user_count <= 0:
        raise ValueError("user_count must be greater than zero.")
    if not 0 < traffic_split_a < 1:
        raise ValueError("traffic_split_a must be between zero and one.")
    if b_uplift < 0:
        raise ValueError("b_uplift must not be negative.")

    randomizer = random.Random(seed)
    window_seconds = max(1, int((end_at - start_at).total_seconds()) - 300)
    users: list[UserRecord] = []
    events: list[EventRecord] = []

    for user_index in range(user_count):
        user_id = _stable_id(seed, "user", user_index)
        channel = randomizer.choices(CHANNELS, weights=CHANNEL_WEIGHTS, k=1)[0]
        group = "A" if randomizer.random() < traffic_split_a else "B"
        session_count = 1 if randomizer.random() < 0.68 else randomizer.randint(2, 3)
        first_seen: datetime | None = None

        for session_index in range(session_count):
            offset = randomizer.randint(0, window_seconds)
            session_start = start_at + timedelta(seconds=offset)
            if first_seen is None or session_start < first_seen:
                first_seen = session_start
            session_id = _stable_id(seed, "session", user_index, session_index)
            product_id = f"product_{randomizer.randint(1, 50):03d}"
            click = _event(
                seed,
                user_id,
                session_id,
                user_index,
                session_index,
                "click",
                group,
                channel,
                product_id,
                None,
                session_start,
            )
            events.append(click)

            if randomizer.random() >= 0.48:
                continue
            cart_time = session_start + timedelta(seconds=randomizer.randint(5, 90))
            events.append(
                _event(
                    seed,
                    user_id,
                    session_id,
                    user_index,
                    session_index,
                    "add_to_cart",
                    group,
                    channel,
                    product_id,
                    None,
                    cart_time,
                )
            )
            purchase_probability = CHANNEL_PURCHASE_RATES[channel] * (
                1 + (b_uplift if group == "B" else 0)
            )
            if randomizer.random() < min(purchase_probability, 0.95):
                buy_time = cart_time + timedelta(seconds=randomizer.randint(10, 180))
                value = Decimal(str(randomizer.lognormvariate(4.25, 0.45))).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
                events.append(
                    _event(
                        seed,
                        user_id,
                        session_id,
                        user_index,
                        session_index,
                        "buy",
                        group,
                        channel,
                        product_id,
                        value,
                        buy_time,
                    )
                )

        users.append(
            UserRecord(
                user_id=user_id,
                first_seen_at=first_seen or start_at,
                acquisition_channel=channel,
                country=randomizer.choice(("CN", "US", "GB", "SG")),
                device_type=randomizer.choices(
                    ("mobile", "desktop", "tablet"), weights=(0.72, 0.24, 0.04), k=1
                )[0],
            )
        )

    return GeneratedBatch(users=users, events=sorted(events, key=lambda event: event.created_at))


def _stable_id(seed: int, *parts: object) -> UUID:
    return uuid5(NAMESPACE, ":".join(str(part) for part in (seed, *parts)))


def _event(
    seed: int,
    user_id: UUID,
    session_id: UUID,
    user_index: int,
    session_index: int,
    event_type: str,
    experiment_group: str,
    channel: str,
    product_id: str,
    order_value: Decimal | None,
    created_at: datetime,
) -> EventRecord:
    return EventRecord(
        event_id=_stable_id(seed, "event", user_index, session_index, event_type),
        user_id=user_id,
        session_id=session_id,
        event_type=event_type,
        experiment_group=experiment_group,
        channel=channel,
        product_id=product_id,
        order_value=order_value,
        created_at=created_at.astimezone(UTC),
    )
