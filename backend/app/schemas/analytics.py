"""Request and response contracts for the analytics endpoints."""

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


class ExperimentTimeWindowQuery(BaseModel):
    """A/B experiment time window; groups are always evaluated together."""

    start_time: datetime
    end_time: datetime

    @model_validator(mode="after")
    def validate_time_window(self) -> "ExperimentTimeWindowQuery":
        if self.start_time.tzinfo is None or self.end_time.tzinfo is None:
            raise ValueError("start_time and end_time must include a timezone.")
        if self.start_time >= self.end_time:
            raise ValueError("start_time must be earlier than end_time.")
        return self


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


class ExperimentGroupMetrics(BaseModel):
    """Metrics for one experiment group, using deduplicated user counts."""

    click_users: int = Field(ge=0)
    add_to_cart_users: int = Field(ge=0)
    purchase_users: int = Field(ge=0)
    conversion_rate: Decimal | None = Field(default=None, ge=0, le=1)
    add_to_cart_rate: Decimal | None = Field(default=None, ge=0)
    gmv: Decimal = Field(ge=0)
    aov: Decimal | None = Field(default=None, ge=0)
    order_count: int = Field(ge=0)

    @field_serializer(
        "conversion_rate", "add_to_cart_rate", "gmv", "aov", when_used="json"
    )
    def serialize_decimal(self, value: Decimal | None) -> float | None:
        return float(value) if value is not None else None


class ExperimentDecision(BaseModel):
    """Machine-readable and display-ready experiment recommendation."""

    code: Literal[
        "insufficient_sample",
        "significantly_better",
        "significantly_worse",
        "no_significant_difference",
    ]
    message: str
    level: Literal["info", "success", "error", "warning"]


class ExperimentResponse(BaseModel):
    """A/B experiment evaluation for the selected time window."""

    experiment_id: str
    primary_metric: Literal["purchase_conversion_rate"]
    minimum_sample_size: int = Field(ge=1)
    start_time: datetime
    end_time: datetime
    groups: dict[Literal["A", "B"], ExperimentGroupMetrics]
    uplift: Decimal | None = None
    p_value: Decimal | None = Field(default=None, ge=0, le=1)
    decision: ExperimentDecision

    @field_serializer("uplift", "p_value", when_used="json")
    def serialize_decimal(self, value: Decimal | None) -> float | None:
        return float(value) if value is not None else None


AttributionModel = Literal["first_touch", "last_touch", "linear"]


class AttributionQuery(BaseModel):
    start_time: datetime
    end_time: datetime
    model: AttributionModel = "last_touch"
    channel: str | None = Field(default=None, min_length=1, max_length=32)
    campaign_id: str | None = Field(default=None, min_length=1, max_length=128)

    @model_validator(mode="after")
    def validate_time_window(self) -> "AttributionQuery":
        if self.start_time.tzinfo is None or self.end_time.tzinfo is None:
            raise ValueError("start_time and end_time must include a timezone.")
        if self.start_time >= self.end_time:
            raise ValueError("start_time must be earlier than end_time.")
        return self


class AttributionTouchpoint(BaseModel):
    created_at: datetime
    channel: str
    source: str | None = None
    medium: str | None = None
    campaign_id: str | None = None
    campaign_name: str | None = None


class AttributionChannel(BaseModel):
    channel: str
    order_credit: Decimal = Field(ge=0)
    gmv_credit: Decimal = Field(ge=0)
    gmv_share: Decimal = Field(ge=0, le=1)
    rank: int = Field(ge=1)

    @field_serializer("order_credit", "gmv_credit", "gmv_share", when_used="json")
    def serialize_decimal(self, value: Decimal) -> float:
        return float(value)


class AttributionCampaign(AttributionChannel):
    campaign_id: str | None = None
    campaign_name: str | None = None


class AttributionPath(BaseModel):
    order_id: str
    order_time: datetime
    order_value: Decimal = Field(ge=0)
    touchpoints: list[AttributionTouchpoint]

    @field_serializer("order_value", when_used="json")
    def serialize_decimal(self, value: Decimal) -> float:
        return float(value)


class AttributionDataQuality(BaseModel):
    unknown_channel_share: Decimal = Field(ge=0, le=1)
    missing_campaign_count: int = Field(ge=0)
    missing_campaign_share: Decimal = Field(ge=0, le=1)
    no_valid_touchpoint_orders: int = Field(ge=0)
    warnings: list[str] = []

    @field_serializer("unknown_channel_share", "missing_campaign_share", when_used="json")
    def serialize_decimal(self, value: Decimal) -> float:
        return float(value)


class AttributionResponse(BaseModel):
    start_time: datetime
    end_time: datetime
    lookback_start: datetime
    model: AttributionModel
    total_orders: int = Field(ge=0)
    total_gmv: Decimal = Field(ge=0)
    attributed_orders: Decimal = Field(ge=0)
    attributed_gmv: Decimal = Field(ge=0)
    unknown_orders: Decimal = Field(ge=0)
    unknown_gmv: Decimal = Field(ge=0)
    coverage_rate: Decimal = Field(ge=0, le=1)
    channels: list[AttributionChannel]
    campaigns: list[AttributionCampaign]
    touchpoint_paths: list[AttributionPath]
    data_quality: AttributionDataQuality

    @field_serializer(
        "total_gmv", "attributed_orders", "attributed_gmv", "unknown_orders",
        "unknown_gmv", "coverage_rate", when_used="json"
    )
    def serialize_decimal(self, value: Decimal) -> float:
        return float(value)
