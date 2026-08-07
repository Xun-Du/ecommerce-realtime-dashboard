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
CHANNEL_CONTEXT = {
    "organic": ("google", "organic"),
    "search": ("google", "cpc"),
    "social": ("meta", "paid_social"),
    "affiliate": ("partner_network", "affiliate"),
    "email": ("crm", "email"),
}
DEFAULT_EXPERIMENT_ID = "homepage_checkout_v1"
NAMESPACE = UUID("6b6d2cb3-4d2c-4f65-bf38-cf68924bb991")


@dataclass(frozen=True)
class UserRecord:
    user_id: UUID
    first_seen_at: datetime
    acquisition_channel: str
    country: str
    device_type: str
    customer_type: str
    external_user_id: str

    def as_database_row(self) -> dict[str, object]:
        return self.__dict__


@dataclass(frozen=True)
class EventRecord:
    event_id: UUID
    user_id: UUID
    session_id: UUID
    experiment_id: str
    event_type: str
    experiment_group: str
    source: str
    medium: str
    campaign_id: str | None
    campaign_name: str | None
    channel: str
    product_id: str
    order_id: str | None
    order_value: Decimal | None
    event_properties: dict[str, object]
    created_at: datetime

    def as_database_row(self) -> dict[str, object]:
        return self.__dict__


@dataclass(frozen=True)
class ExperimentAssignmentRecord:
    experiment_id: str
    user_id: UUID
    variant_id: str
    assigned_at: datetime

    def as_database_row(self) -> dict[str, object]:
        return self.__dict__


@dataclass(frozen=True)
class GeneratedBatch:
    users: list[UserRecord]
    events: list[EventRecord]
    assignments: list[ExperimentAssignmentRecord]

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
    assignments: list[ExperimentAssignmentRecord] = []

    for user_index in range(user_count):
        user_id = _stable_id(seed, "user", user_index)
        group = "A" if randomizer.random() < traffic_split_a else "B"
        session_count = 1 if randomizer.random() < 0.68 else randomizer.randint(2, 3)
        session_starts = sorted(
            start_at + timedelta(seconds=randomizer.randint(0, window_seconds))
            for _ in range(session_count)
        )
        acquisition_channel = randomizer.choices(CHANNELS, weights=CHANNEL_WEIGHTS, k=1)[0]
        customer_type = "returning" if randomizer.random() < 0.30 else "new"
        first_seen = session_starts[0]
        if customer_type == "returning":
            first_seen -= timedelta(days=randomizer.randint(1, 180))

        assignments.append(
            ExperimentAssignmentRecord(
                experiment_id=DEFAULT_EXPERIMENT_ID,
                user_id=user_id,
                variant_id=f"{DEFAULT_EXPERIMENT_ID}:{group}",
                assigned_at=session_starts[0].astimezone(UTC),
            )
        )

        for session_index, session_start in enumerate(session_starts):
            channel = (
                acquisition_channel
                if session_index == 0 or randomizer.random() < 0.55
                else randomizer.choice(
                    tuple(candidate for candidate in CHANNELS if candidate != acquisition_channel)
                )
            )
            source, medium, campaign_id, campaign_name = _marketing_context(
                channel, user_index, session_index
            )
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
                source,
                medium,
                campaign_id,
                campaign_name,
                channel,
                product_id,
                None,
                None,
                session_index,
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
                    source,
                    medium,
                    campaign_id,
                    campaign_name,
                    channel,
                    product_id,
                    None,
                    None,
                    session_index,
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
                        source,
                        medium,
                        campaign_id,
                        campaign_name,
                        channel,
                        product_id,
                        str(_stable_id(seed, "order", user_index, session_index)),
                        value,
                        session_index,
                        buy_time,
                    )
                )

        users.append(
            UserRecord(
                user_id=user_id,
                first_seen_at=first_seen.astimezone(UTC),
                acquisition_channel=acquisition_channel,
                country=randomizer.choice(("CN", "US", "GB", "SG")),
                device_type=randomizer.choices(
                    ("mobile", "desktop", "tablet"), weights=(0.72, 0.24, 0.04), k=1
                )[0],
                customer_type=customer_type,
                external_user_id=f"demo_customer_{user_id.hex}",
            )
        )

    return GeneratedBatch(
        users=users,
        events=sorted(events, key=lambda event: event.created_at),
        assignments=assignments,
    )


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
    source: str,
    medium: str,
    campaign_id: str | None,
    campaign_name: str | None,
    channel: str,
    product_id: str,
    order_id: str | None,
    order_value: Decimal | None,
    touchpoint_sequence: int,
    created_at: datetime,
) -> EventRecord:
    return EventRecord(
        event_id=_stable_id(seed, "event", user_index, session_index, event_type),
        user_id=user_id,
        session_id=session_id,
        experiment_id=DEFAULT_EXPERIMENT_ID,
        event_type=event_type,
        experiment_group=experiment_group,
        source=source,
        medium=medium,
        campaign_id=campaign_id,
        campaign_name=campaign_name,
        channel=channel,
        product_id=product_id,
        order_id=order_id,
        order_value=order_value,
        event_properties={
            "synthetic": True,
            "touchpoint_sequence": touchpoint_sequence,
        },
        created_at=created_at.astimezone(UTC),
    )


def _marketing_context(
    channel: str, user_index: int, session_index: int
) -> tuple[str, str, str | None, str | None]:
    source, medium = CHANNEL_CONTEXT[channel]
    if channel == "organic":
        return source, medium, None, None
    campaign_number = (user_index + session_index) % 6 + 1
    campaign_id = f"{channel}_campaign_{campaign_number:02d}"
    campaign_name = f"{channel.replace('_', ' ').title()} Campaign {campaign_number:02d}"
    return source, medium, campaign_id, campaign_name
