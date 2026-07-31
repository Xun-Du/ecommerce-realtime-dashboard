"""Request and response contracts for the M2 analytics endpoints."""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_serializer, model_validator


class TimeWindowQuery(BaseModel):
    """A UTC-aware, left-closed/right-open analytics time window."""

    start_time: datetime
    end_time: datetime
    experiment_group: Literal["A", "B"] | None = None

    @model_validator(mode="after")
    def validate_time_window(self) -> "TimeWindowQuery":
        if self.start_time.tzinfo is None or self.end_time.tzinfo is None:
            raise ValueError("start_time and end_time must include a timezone.")
        if self.start_time >= self.end_time:
            raise ValueError("start_time must be earlier than end_time.")
        return self


class MetricsQuery(TimeWindowQuery):
    granularity: Literal["hour", "day"]


class MetricValues(BaseModel):
    dau: int = Field(ge=0)
    gmv: Decimal = Field(ge=0)
    order_count: int = Field(ge=0)
    purchase_conversion_rate: Decimal | None = Field(default=None, ge=0, le=1)
    aov: Decimal | None = Field(default=None, ge=0)

    @field_serializer("gmv", "purchase_conversion_rate", "aov", when_used="json")
    def serialize_decimal(self, value: Decimal | None) -> float | None:
        """Expose monetary and ratio fields as JSON numbers, not Decimal strings."""
        return float(value) if value is not None else None


class TrendPoint(MetricValues):
    start_time: datetime
    end_time: datetime


class MetricsResponse(MetricValues):
    start_time: datetime
    end_time: datetime
    granularity: Literal["hour", "day"]
    experiment_group: Literal["A", "B"] | None
    trends: list[TrendPoint]


class FunnelStep(BaseModel):
    event_type: Literal["click", "add_to_cart", "buy"]
    users: int = Field(ge=0)
    conversion_rate_from_previous: Decimal | None = Field(default=None, ge=0)
    cumulative_conversion_rate: Decimal | None = Field(default=None, ge=0)
    drop_off_users_from_previous: int | None = Field(default=None, ge=0)
    drop_off_rate_from_previous: Decimal | None = Field(default=None, ge=0)

    @field_serializer(
        "conversion_rate_from_previous",
        "cumulative_conversion_rate",
        "drop_off_rate_from_previous",
        when_used="json",
    )
    def serialize_decimal(self, value: Decimal | None) -> float | None:
        """Expose funnel rates as JSON numbers while retaining Decimal calculations."""
        return float(value) if value is not None else None


class FunnelResponse(BaseModel):
    start_time: datetime
    end_time: datetime
    experiment_group: Literal["A", "B"] | None
    steps: list[FunnelStep]
    has_data_quality_issue: bool
