"""Streamlit entry point for the P0 operations dashboard."""

import os
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta

import streamlit as st

from frontend.api_client import ApiClient, ApiClientError
from frontend.components.dashboard import (
    render_experiment,
    render_funnel,
    render_metric_cards,
    render_trends,
)

AUTO_REFRESH_SECONDS = 30
DEFAULT_API_BASE_URL = "http://localhost:8000"


@dataclass(frozen=True)
class DashboardFilters:
    """The common time and group filters shared by all P0 sections."""

    start_time: datetime
    end_time: datetime
    granularity: str
    experiment_group: str | None
    auto_refresh: bool


@st.cache_data(ttl=20, show_spinner=False)
def load_metrics(filters: DashboardFilters, api_base_url: str, refresh_nonce: int):
    """Load the overview data; nonce makes explicit refreshes bypass the cache."""
    del refresh_nonce
    return ApiClient(api_base_url).get_metrics(
        filters.start_time, filters.end_time, filters.granularity, filters.experiment_group
    )


@st.cache_data(ttl=20, show_spinner=False)
def load_funnel(filters: DashboardFilters, api_base_url: str, refresh_nonce: int):
    """Load the funnel for the same dashboard filters."""
    del refresh_nonce
    return ApiClient(api_base_url).get_funnel(
        filters.start_time, filters.end_time, filters.experiment_group
    )


@st.cache_data(ttl=20, show_spinner=False)
def load_experiment(filters: DashboardFilters, api_base_url: str, refresh_nonce: int):
    """Load full A/B evaluation without applying the single-group page filter."""
    del refresh_nonce
    return ApiClient(api_base_url).get_experiment(filters.start_time, filters.end_time)


def render_filters() -> DashboardFilters:
    """Render and normalize all top-level controls to UTC-aware API parameters."""
    now = datetime.now(UTC)
    window_mode = st.selectbox("时间范围", ("最近 24 小时", "最近 7 天", "自定义日期"))
    if window_mode == "最近 24 小时":
        start_time, end_time = now - timedelta(hours=24), now
    elif window_mode == "最近 7 天":
        start_time, end_time = now - timedelta(days=7), now
    else:
        start_date, end_date = st.date_input(
            "自定义日期范围",
            value=(now.date() - timedelta(days=1), now.date()),
            max_value=now.date(),
        )
        start_time = datetime.combine(start_date, time.min, tzinfo=UTC)
        end_time = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=UTC)

    group_label = st.radio("实验组", ("全部", "A", "B"), horizontal=True)
    granularity = st.segmented_control("趋势粒度", ("hour", "day"), default="hour")
    auto_refresh = st.toggle(f"自动刷新（每 {AUTO_REFRESH_SECONDS} 秒）", value=False)
    filters = DashboardFilters(
        start_time=start_time,
        end_time=end_time,
        granularity=granularity,
        experiment_group=None if group_label == "全部" else group_label,
        auto_refresh=auto_refresh,
    )
    st.session_state["dashboard_filters"] = filters
    return filters


def _render_section_error(title: str, error: ApiClientError) -> None:
    st.subheader(title)
    st.error(str(error))


def render_dashboard_sections(
    filters: DashboardFilters, api_base_url: str, refresh_nonce: int
) -> None:
    """Render sections independently so one failed endpoint does not break the page."""
    try:
        metrics = load_metrics(filters, api_base_url, refresh_nonce)
        render_metric_cards(metrics)
        render_trends(metrics)
    except ApiClientError as error:
        _render_section_error("经营概览", error)

    try:
        render_funnel(load_funnel(filters, api_base_url, refresh_nonce))
    except ApiClientError as error:
        _render_section_error("漏斗诊断", error)

    try:
        render_experiment(load_experiment(filters, api_base_url, refresh_nonce))
    except ApiClientError as error:
        _render_section_error("实验决策", error)


def render_dashboard() -> None:
    """Render the M4 P0 dashboard and refresh only data sections when requested."""
    st.set_page_config(page_title="实时电商 A/B 与归因分析看板", layout="wide")
    st.title("实时电商 A/B 测试与归因分析看板")
    st.caption("准实时模拟 Demo · 数据按 UTC 时间窗口统计")

    filters = render_filters()
    if "refresh_nonce" not in st.session_state:
        st.session_state.refresh_nonce = 0
    if st.button("立即刷新"):
        st.session_state.refresh_nonce += 1
    api_base_url = os.getenv("API_BASE_URL", DEFAULT_API_BASE_URL).rstrip("/")
    refresh_status = "自动刷新已开启" if filters.auto_refresh else "手动刷新"
    st.caption(f"数据源：{api_base_url} · {refresh_status}")

    @st.fragment(run_every=f"{AUTO_REFRESH_SECONDS}s" if filters.auto_refresh else None)
    def live_sections() -> None:
        if filters.auto_refresh:
            load_metrics.clear()
            load_funnel.clear()
            load_experiment.clear()
        render_dashboard_sections(filters, api_base_url, st.session_state.refresh_nonce)

    live_sections()


if __name__ == "__main__":
    render_dashboard()
