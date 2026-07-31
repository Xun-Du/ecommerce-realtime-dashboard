"""Database models shared by the data pipeline and later API milestones."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, String
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
    event_type: Mapped[str] = mapped_column(String(16), nullable=False)
    experiment_group: Mapped[str | None] = mapped_column(String(1), nullable=True)
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    product_id: Mapped[str] = mapped_column(String(32), nullable=False)
    order_value: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
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
