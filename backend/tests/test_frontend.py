"""Tests for the M4 dashboard frontend boundary and display logic."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock

import httpx
import pytest

import frontend.app as dashboard
from frontend.api_client import ApiClient, ApiRequestError, ApiResponseError
from frontend.components.dashboard import _format_p_value, format_currency, format_percentage


class _FakeHttpClient:
    response: httpx.Response | None = None
    error: Exception | None = None
    last_url: str | None = None
    last_params: dict[str, str] | None = None

    def __init__(self, timeout: float) -> None:
        self.timeout = timeout

    def __enter__(self) -> "_FakeHttpClient":
        return self

    def __exit__(self, *_args) -> None:
        return None

    def get(self, url: str, params: dict[str, str]) -> httpx.Response:
        type(self).last_url = url
        type(self).last_params = params
        if type(self).error:
            raise type(self).error
        assert type(self).response is not None
        return type(self).response


@pytest.fixture(autouse=True)
def reset_fake_http_client() -> None:
    _FakeHttpClient.response = None
    _FakeHttpClient.error = None
    _FakeHttpClient.last_url = None
    _FakeHttpClient.last_params = None


def _window() -> tuple[datetime, datetime]:
    end_time = datetime(2026, 8, 2, 12, tzinfo=UTC)
    return end_time - timedelta(hours=24), end_time


def _metrics_payload() -> dict:
    start_time, end_time = _window()
    return {
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "granularity": "hour",
        "experiment_group": "B",
        "dau": 1200,
        "gmv": 34567.89,
        "order_count": 320,
        "purchase_conversion_rate": 0.182,
        "aov": 108.02,
        "trends": [
            {
                "start_time": start_time.isoformat(),
                "end_time": (start_time + timedelta(hours=1)).isoformat(),
                "dau": 80,
                "gmv": 1234.5,
                "order_count": 12,
                "purchase_conversion_rate": 0.15,
                "aov": 102.88,
            }
        ],
    }


def _experiment_payload() -> dict:
    start_time, end_time = _window()
    return {
        "experiment_id": "homepage_checkout_v1",
        "primary_metric": "purchase_conversion_rate",
        "minimum_sample_size": 100,
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "groups": {
            "A": {
                "click_users": 1000,
                "add_to_cart_users": 300,
                "purchase_users": 120,
                "conversion_rate": 0.12,
                "add_to_cart_rate": 0.3,
                "gmv": 12000,
                "aov": 100,
                "order_count": 120,
            },
            "B": {
                "click_users": 1000,
                "add_to_cart_users": 380,
                "purchase_users": 160,
                "conversion_rate": 0.16,
                "add_to_cart_rate": 0.38,
                "gmv": 17600,
                "aov": 110,
                "order_count": 160,
            },
        },
        "uplift": 0.333333,
        "p_value": 0.0123,
        "decision": {
            "code": "significantly_better",
            "message": "B 组显著优于 A 组。",
            "level": "success",
        },
    }


def test_api_client_serializes_metrics_filters(monkeypatch) -> None:
    monkeypatch.setattr("frontend.api_client.httpx.Client", _FakeHttpClient)
    _FakeHttpClient.response = httpx.Response(
        200,
        json=_metrics_payload(),
        request=httpx.Request("GET", "http://localhost:8000/api/metrics"),
    )
    start_time, end_time = _window()

    response = ApiClient("http://localhost:8000/").get_metrics(start_time, end_time, "hour", "B")

    assert response.dau == 1200
    assert _FakeHttpClient.last_url == "http://localhost:8000/api/metrics"
    assert _FakeHttpClient.last_params == {
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "experiment_group": "B",
        "granularity": "hour",
    }


def test_api_client_experiment_ignores_single_group_filter(monkeypatch) -> None:
    monkeypatch.setattr("frontend.api_client.httpx.Client", _FakeHttpClient)
    _FakeHttpClient.response = httpx.Response(
        200,
        json=_experiment_payload(),
        request=httpx.Request("GET", "http://localhost:8000/api/experiment"),
    )
    start_time, end_time = _window()

    response = ApiClient("http://localhost:8000").get_experiment(start_time, end_time)

    assert response.decision.code == "significantly_better"
    assert _FakeHttpClient.last_params == {
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
    }


@pytest.mark.parametrize(
    ("status_code", "expected_message"),
    [(422, "筛选条件无效"), (503, "分析数据暂不可用"), (500, "HTTP 500")],
)
def test_api_client_maps_http_errors(monkeypatch, status_code: int, expected_message: str) -> None:
    monkeypatch.setattr("frontend.api_client.httpx.Client", _FakeHttpClient)
    request = httpx.Request("GET", "http://localhost:8000/api/metrics")
    _FakeHttpClient.response = httpx.Response(status_code, request=request)
    start_time, end_time = _window()

    with pytest.raises(ApiRequestError, match=expected_message):
        ApiClient("http://localhost:8000").get_metrics(start_time, end_time, "hour", None)


def test_api_client_maps_timeout(monkeypatch) -> None:
    monkeypatch.setattr("frontend.api_client.httpx.Client", _FakeHttpClient)
    _FakeHttpClient.error = httpx.ReadTimeout("slow API")
    start_time, end_time = _window()

    with pytest.raises(ApiRequestError, match="请求超时"):
        ApiClient("http://localhost:8000").get_funnel(start_time, end_time, None)


def test_api_client_rejects_invalid_payload(monkeypatch) -> None:
    monkeypatch.setattr("frontend.api_client.httpx.Client", _FakeHttpClient)
    _FakeHttpClient.response = httpx.Response(
        200,
        json={"unexpected": "payload"},
        request=httpx.Request("GET", "http://localhost:8000/api/metrics"),
    )
    start_time, end_time = _window()

    with pytest.raises(ApiResponseError, match="数据格式异常"):
        ApiClient("http://localhost:8000").get_metrics(start_time, end_time, "hour", None)


def test_formatters_handle_null_money_and_ratios() -> None:
    assert format_currency(None) == "—"
    assert format_currency(Decimal("1234.5")) == "¥1,234.50"
    assert format_percentage(None) == "—"
    assert format_percentage(Decimal("0.1234")) == "12.34%"


def test_p_value_formatter_avoids_displaying_tiny_values_as_zero() -> None:
    assert _format_p_value(None) == "—"
    assert _format_p_value(Decimal("0.00001")) == "< 0.0001"
    assert _format_p_value(Decimal("0.0123")) == "0.0123"


def test_dashboard_sections_isolate_module_failures(monkeypatch) -> None:
    filters = dashboard.DashboardFilters(*_window(), "hour", "B", False)
    rendered: list[str] = []
    errors: list[str] = []

    monkeypatch.setattr(
        dashboard, "load_metrics", Mock(side_effect=ApiRequestError("metrics down"))
    )
    monkeypatch.setattr(dashboard, "load_funnel", Mock(return_value="funnel"))
    monkeypatch.setattr(dashboard, "load_experiment", Mock(return_value="experiment"))
    monkeypatch.setattr(dashboard, "render_funnel", lambda _payload: rendered.append("funnel"))
    monkeypatch.setattr(
        dashboard, "render_experiment", lambda _payload: rendered.append("experiment")
    )
    monkeypatch.setattr(dashboard.st, "subheader", Mock())
    monkeypatch.setattr(dashboard.st, "error", lambda message: errors.append(message))

    dashboard.render_dashboard_sections(filters, "http://localhost:8000", 0)

    assert rendered == ["funnel", "experiment"]
    assert errors == ["metrics down"]
