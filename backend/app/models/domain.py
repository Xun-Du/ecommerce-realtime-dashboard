"""Database models shared by the data pipeline and later API milestones."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for ORM mappings."""


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    acquisition_channel: Mapped[str] = mapped_column(String(32), nullable=False)
    country: Mapped[str] = mapped_column(String(2), nullable=False)
    device_type: Mapped[str] = mapped_column(String(16), nullable=False)
    customer_type: Mapped[str] = mapped_column(String(16), nullable=False, default="new")
    external_user_id: Mapped[str | None] = mapped_column(String(128), nullable=True)


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        CheckConstraint("event_type IN ('click', 'add_to_cart', 'buy')"),
        CheckConstraint("experiment_group IN ('A', 'B') OR experiment_group IS NULL"),
        CheckConstraint(
            "(event_type = 'buy' AND order_value > 0) "
            "OR (event_type <> 'buy' AND order_value IS NULL)"
        ),
    )

    event_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False
    )
    session_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    experiment_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    event_type: Mapped[str] = mapped_column(String(16), nullable=False)
    experiment_group: Mapped[str | None] = mapped_column(String(1), nullable=True)
    source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    medium: Mapped[str | None] = mapped_column(String(64), nullable=True)
    campaign_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    campaign_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    product_id: Mapped[str] = mapped_column(String(32), nullable=False)
    order_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    order_value: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    event_properties: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ExperimentConfig(Base):
    __tablename__ = "experiment_config"
    __table_args__ = (
        CheckConstraint("traffic_split_a >= 0 AND traffic_split_b >= 0"),
        CheckConstraint("traffic_split_a + traffic_split_b = 1"),
        CheckConstraint("conversion_alert_threshold >= 0 AND gmv_alert_threshold >= 0"),
    )

    experiment_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    traffic_split_a: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    traffic_split_b: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    conversion_alert_threshold: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)
    gmv_alert_threshold: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Experiment(Base):
    __tablename__ = "experiments"
    __table_args__ = (
        CheckConstraint("status IN ('draft', 'running', 'paused', 'completed', 'cancelled')"),
        CheckConstraint("traffic_split_a >= 0 AND traffic_split_b >= 0"),
        CheckConstraint("traffic_split_a + traffic_split_b = 1"),
        CheckConstraint(
            "significance_level > 0 AND significance_level < 1 AND minimum_sample_size >= 1"
        ),
        CheckConstraint("end_time IS NULL OR start_time IS NULL OR end_time > start_time"),
    )

    experiment_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    hypothesis: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    primary_metric: Mapped[str] = mapped_column(String(64), nullable=False)
    start_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    traffic_split_a: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    traffic_split_b: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    minimum_sample_size: Mapped[int] = mapped_column(Integer, nullable=False)
    significance_level: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ExperimentVariant(Base):
    __tablename__ = "experiment_variants"
    __table_args__ = (CheckConstraint("traffic_proportion >= 0 AND traffic_proportion <= 1"),)

    variant_id: Mapped[str] = mapped_column(String(96), primary_key=True)
    experiment_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("experiments.experiment_id"), nullable=False
    )
    variant_key: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    is_control: Mapped[bool] = mapped_column(Boolean, nullable=False)
    traffic_proportion: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ExperimentAssignment(Base):
    __tablename__ = "experiment_assignments"

    experiment_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("experiments.experiment_id"), primary_key=True
    )
    user_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("users.user_id"), primary_key=True
    )
    variant_id: Mapped[str] = mapped_column(
        String(96), ForeignKey("experiment_variants.variant_id"), nullable=False
    )
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ExperimentResult(Base):
    __tablename__ = "experiment_results"
    __table_args__ = (CheckConstraint("window_end > window_start"),)

    result_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    experiment_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("experiments.experiment_id"), nullable=False
    )
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    metrics_snapshot: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    statistics_snapshot: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    decision_code: Mapped[str] = mapped_column(String(64), nullable=False)
    decision_level: Mapped[str] = mapped_column(String(16), nullable=False)
    decision_message: Mapped[str] = mapped_column(Text, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class MetricThreshold(Base):
    __tablename__ = "metric_thresholds"
    __table_args__ = (
        CheckConstraint("direction IN ('above', 'below', 'increase', 'decrease')"),
        CheckConstraint("threshold_value >= 0"),
    )

    threshold_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    metric_name: Mapped[str] = mapped_column(String(64), nullable=False)
    direction: Mapped[str] = mapped_column(String(16), nullable=False)
    threshold_value: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    scope: Mapped[str] = mapped_column(String(64), nullable=False, default="global")
    experiment_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("experiments.experiment_id"), nullable=True
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
