"""Tests for the M4 dashboard frontend boundary and display logic."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock

import httpx
import pytest

import frontend.app as dashboard
from frontend.api_client import ApiClient, ApiRequestError, ApiResponseError
from frontend.components.dashboard import _format_p_value, format_currency, format_percentage
from frontend.navigation import NAVIGATION_ITEMS, navigation_item


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


def _attribution_payload(model: str = "last_touch") -> dict:
    start_time, end_time = _window()
    return {
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "lookback_start": (start_time - timedelta(days=30)).isoformat(),
        "model": model,
        "total_orders": 2,
        "total_gmv": 100,
        "attributed_orders": 2,
        "attributed_gmv": 100,
        "unknown_orders": 0,
        "unknown_gmv": 0,
        "coverage_rate": 1,
        "channels": [
            {"channel": "search", "order_credit": 2, "gmv_credit": 100, "gmv_share": 1, "rank": 1}
        ],
        "campaigns": [],
        "touchpoint_paths": [],
        "data_quality": {
            "unknown_channel_share": 0,
            "missing_campaign_count": 0,
            "missing_campaign_share": 0,
            "no_valid_touchpoint_orders": 0,
            "warnings": [],
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


def test_api_client_serializes_attribution_filters(monkeypatch) -> None:
    monkeypatch.setattr("frontend.api_client.httpx.Client", _FakeHttpClient)
    _FakeHttpClient.response = httpx.Response(
        200,
        json=_attribution_payload("linear"),
        request=httpx.Request("GET", "http://localhost:8000/api/attribution"),
    )
    start_time, end_time = _window()

    result = ApiClient("http://localhost:8000").get_attribution(
        start_time, end_time, "linear", "search", "campaign-1"
    )

    assert result.model == "linear"
    assert _FakeHttpClient.last_params == {
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "model": "linear",
        "channel": "search",
        "campaign_id": "campaign-1",
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


def test_navigation_exposes_available_and_planned_modules() -> None:
    assert [item.key for item in NAVIGATION_ITEMS] == [
        "home",
        "monitor",
        "attribution",
        "funnel",
        "customers",
        "experiments",
        "creatives",
        "integrations",
    ]
    assert navigation_item("home").status == "available"
    assert navigation_item("attribution").status == "available"


@pytest.mark.parametrize("page_key", ["customers", "creatives", "integrations"])
def test_planned_pages_do_not_request_api(monkeypatch, page_key: str) -> None:
    filters = dashboard.DashboardFilters(*_window(), "hour", None, False)
    load_metrics = Mock(side_effect=AssertionError("planned page requested metrics"))
    load_funnel = Mock(side_effect=AssertionError("planned page requested funnel"))
    load_experiment = Mock(side_effect=AssertionError("planned page requested experiment"))
    rendered: list[str] = []

    monkeypatch.setattr(dashboard, "load_metrics", load_metrics)
    monkeypatch.setattr(dashboard, "load_funnel", load_funnel)
    monkeypatch.setattr(dashboard, "load_experiment", load_experiment)
    monkeypatch.setattr(dashboard, "render_placeholder", rendered.append)
    monkeypatch.setattr(dashboard.st, "title", Mock())
    monkeypatch.setattr(dashboard.st, "caption", Mock())

    dashboard._render_page(page_key, filters, "http://localhost:8000", 0)

    assert rendered == [page_key]
    load_metrics.assert_not_called()
    load_funnel.assert_not_called()
    load_experiment.assert_not_called()


def test_monitor_page_only_requests_metrics(monkeypatch) -> None:
    filters = dashboard.DashboardFilters(*_window(), "day", "A", False)
    load_metrics = Mock(return_value="metrics")
    rendered: list[str] = []

    monkeypatch.setattr(dashboard, "load_metrics", load_metrics)
    monkeypatch.setattr(dashboard, "load_funnel", Mock())
    monkeypatch.setattr(dashboard, "load_experiment", Mock())
    monkeypatch.setattr(dashboard.monitor_page, "render", rendered.append)
    monkeypatch.setattr(dashboard.st, "title", Mock())
    monkeypatch.setattr(dashboard.st, "caption", Mock())

    dashboard._render_page("monitor", filters, "http://localhost:8000", 7)

    assert rendered == ["metrics"]
    load_metrics.assert_called_once_with(filters, "http://localhost:8000", 7)


def test_attribution_page_requests_all_models(monkeypatch) -> None:
    filters = dashboard.DashboardFilters(*_window(), "day", None, False)
    rendered: list[dict] = []
    loader = Mock(side_effect=lambda *_args: _attribution_payload())
    monkeypatch.setattr(dashboard, "load_attribution", loader)
    monkeypatch.setattr(dashboard.attribution_page, "render", rendered.append)

    dashboard._render_page("attribution", filters, "http://localhost:8000", 0)

    assert loader.call_args_list[0].args[-1] == "first_touch"
    assert loader.call_args_list[1].args[-1] == "last_touch"
    assert loader.call_args_list[2].args[-1] == "linear"
    assert set(rendered[0]) == {"first_touch", "last_touch", "linear"}
