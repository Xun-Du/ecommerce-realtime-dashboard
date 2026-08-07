"""Tests for M1 deterministic event generation."""

from collections import Counter
from datetime import UTC, datetime, timedelta

import pytest

from scripts.data_generator import CHANNELS, DEFAULT_EXPERIMENT_ID, generate_batch


@pytest.fixture
def generated_batch():
    return generate_batch(
        start_at=datetime(2026, 7, 1, tzinfo=UTC),
        end_at=datetime(2026, 7, 15, tzinfo=UTC),
        user_count=10_000,
        seed=42,
        b_uplift=0.20,
    )


def test_generator_is_reproducible() -> None:
    arguments = {
        "start_at": datetime(2026, 7, 1, tzinfo=UTC),
        "end_at": datetime(2026, 7, 2, tzinfo=UTC),
        "user_count": 20,
        "seed": 42,
        "b_uplift": 0.20,
    }
    assert generate_batch(**arguments) == generate_batch(**arguments)


def test_events_obey_value_and_funnel_rules(generated_batch) -> None:
    events_by_session = {}
    for event in generated_batch.events:
        events_by_session.setdefault(event.session_id, []).append(event)
        assert event.experiment_id == DEFAULT_EXPERIMENT_ID
        assert event.source
        assert event.medium
        assert event.event_properties["synthetic"] is True
        if event.event_type == "buy":
            assert event.order_value is not None and event.order_value > 0
            assert event.order_id is not None
        else:
            assert event.order_value is None
            assert event.order_id is None

    for session_events in events_by_session.values():
        assert [event.event_type for event in session_events] in (
            ["click"],
            ["click", "add_to_cart"],
            ["click", "add_to_cart", "buy"],
        )
        assert [event.created_at for event in session_events] == sorted(
            event.created_at for event in session_events
        )


def test_generator_has_all_channels_and_b_group_lift(generated_batch) -> None:
    assert {event.channel for event in generated_batch.events} == set(CHANNELS)
    clicks = {group: set() for group in ("A", "B")}
    buyers = {group: set() for group in ("A", "B")}
    for event in generated_batch.events:
        if event.event_type == "click":
            clicks[event.experiment_group].add(event.user_id)
        if event.event_type == "buy":
            buyers[event.experiment_group].add(event.user_id)
    assert len(clicks["A"]) > 0 and len(clicks["B"]) > 0
    assert len(buyers["B"]) / len(clicks["B"]) > len(buyers["A"]) / len(clicks["A"])


def test_generator_emits_stable_experiment_assignments(generated_batch) -> None:
    assert len(generated_batch.assignments) == len(generated_batch.users)
    assignments_by_user = {
        assignment.user_id: assignment for assignment in generated_batch.assignments
    }
    events_by_user = {}
    for event in generated_batch.events:
        events_by_user.setdefault(event.user_id, []).append(event)

    for user in generated_batch.users:
        assignment = assignments_by_user[user.user_id]
        assert assignment.experiment_id == DEFAULT_EXPERIMENT_ID
        assert assignment.variant_id in (
            f"{DEFAULT_EXPERIMENT_ID}:A",
            f"{DEFAULT_EXPERIMENT_ID}:B",
        )
        user_events = events_by_user[user.user_id]
        assert user_events
        assert {event.experiment_group for event in user_events} == {
            assignment.variant_id.rsplit(":", maxsplit=1)[1]
        }
        assert user.customer_type in {"new", "returning"}
        assert user.external_user_id.startswith("demo_customer_")


def test_generator_includes_multi_touch_marketing_context(generated_batch) -> None:
    assert {event.source for event in generated_batch.events}
    assert {event.medium for event in generated_batch.events}
    assert any(event.campaign_id for event in generated_batch.events)
    channels_by_user = {}
    for event in generated_batch.events:
        channels_by_user.setdefault(event.user_id, set()).add(event.channel)
    assert any(len(channels) > 1 for channels in channels_by_user.values())


def test_daily_event_counts_follow_the_funnel(generated_batch) -> None:
    counts_by_day: dict[object, Counter[str]] = {}
    for event in generated_batch.events:
        counts_by_day.setdefault(event.created_at.date(), Counter())[event.event_type] += 1
    assert all(
        counts["click"] >= counts["add_to_cart"] >= counts["buy"]
        for counts in counts_by_day.values()
    )


def test_generator_rejects_invalid_windows() -> None:
    now = datetime.now(UTC)
    with pytest.raises(ValueError, match="earlier"):
        generate_batch(
            start_at=now,
            end_at=now - timedelta(seconds=1),
            user_count=1,
            seed=1,
            b_uplift=0,
        )
