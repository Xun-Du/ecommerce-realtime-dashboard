"""Presentation components for the P0 operations dashboard."""

from decimal import Decimal

import plotly.graph_objects as go
import streamlit as st

from backend.app.schemas.analytics import ExperimentResponse, FunnelResponse, MetricsResponse


def format_currency(value: Decimal | float | None) -> str:
    """Render monetary values consistently, including empty API values."""
    return "—" if value is None else f"¥{float(value):,.2f}"


def format_percentage(value: Decimal | float | None, digits: int = 2) -> str:
    """Render API ratios (0-1) as percentages."""
    return "—" if value is None else f"{float(value) * 100:.{digits}f}%"


def render_metric_cards(metrics: MetricsResponse) -> None:
    cards = st.columns(4)
    cards[0].metric("DAU", f"{metrics.dau:,}")
    cards[1].metric("GMV", format_currency(metrics.gmv))
    cards[2].metric("购买转化率", format_percentage(metrics.purchase_conversion_rate))
    cards[3].metric("客单价（AOV）", format_currency(metrics.aov))


def render_trends(metrics: MetricsResponse) -> None:
    st.subheader("经营趋势")
    if not metrics.trends:
        st.info("当前筛选范围暂无趋势数据。")
        return

    timestamps = [point.start_time for point in metrics.trends]
    gmv_figure = go.Figure(
        go.Scatter(
            x=timestamps, y=[float(point.gmv) for point in metrics.trends], mode="lines+markers"
        )
    )
    gmv_figure.update_layout(
        title="GMV 趋势", yaxis_title="GMV（¥）", margin=dict(l=20, r=20, t=50, b=20)
    )
    conversion_figure = go.Figure(
        go.Scatter(
            x=timestamps,
            y=[float(p.purchase_conversion_rate or 0) * 100 for p in metrics.trends],
            mode="lines+markers",
        )
    )
    conversion_figure.update_layout(
        title="购买转化率趋势", yaxis_title="购买转化率（%）", margin=dict(l=20, r=20, t=50, b=20)
    )
    left, right = st.columns(2)
    left.plotly_chart(gmv_figure, use_container_width=True)
    right.plotly_chart(conversion_figure, use_container_width=True)


def render_funnel(funnel: FunnelResponse) -> None:
    st.subheader("漏斗诊断")
    if funnel.has_data_quality_issue:
        st.warning("检测到下游人数高于上游人数，请检查事件采集或时间窗口。")
    if not any(step.users for step in funnel.steps):
        st.info("当前筛选范围暂无漏斗数据。")
        return

    labels = {"click": "点击", "add_to_cart": "加购", "buy": "购买"}
    figure = go.Figure(
        go.Funnel(
            y=[labels[step.event_type] for step in funnel.steps],
            x=[step.users for step in funnel.steps],
            textinfo="value+percent initial",
        )
    )
    figure.update_layout(margin=dict(l=20, r=20, t=20, b=20))
    chart, details = st.columns((3, 2))
    chart.plotly_chart(figure, use_container_width=True)
    with details:
        for step in funnel.steps:
            st.metric(labels[step.event_type], f"{step.users:,}")
            if step.conversion_rate_from_previous is not None:
                st.caption(
                    f"环节转化 {format_percentage(step.conversion_rate_from_previous)} · "
                    f"流失 {format_percentage(step.drop_off_rate_from_previous)}"
                )


def render_experiment(experiment: ExperimentResponse) -> None:
    st.subheader("实验决策")
    left, right = st.columns(2)
    for column, group_name in ((left, "A"), (right, "B")):
        group = experiment.groups[group_name]
        with column:
            st.markdown(f"#### {group_name} 组{'（实验）' if group_name == 'B' else '（对照）'}")
            st.metric("购买转化率", format_percentage(group.conversion_rate))
            st.metric("GMV", format_currency(group.gmv))
            st.caption(
                f"点击用户 {group.click_users:,} · "
                f"加购率 {format_percentage(group.add_to_cart_rate)} · "
                f"订单 {group.order_count:,} · AOV {format_currency(group.aov)}"
            )

    st.caption(
        f"主指标：购买转化率｜最低样本量：每组 {experiment.minimum_sample_size:,} 名点击用户"
    )
    summary = (
        f"Uplift：{format_percentage(experiment.uplift)}　|　"
        f"p-value：{_format_p_value(experiment.p_value)}"
    )
    _decision_message(experiment.decision.level, f"{experiment.decision.message}\n\n{summary}")


def _format_p_value(value: Decimal | float | None) -> str:
    if value is None:
        return "—"
    if Decimal(str(value)) < Decimal("0.0001"):
        return "< 0.0001"
    return f"{float(value):.4f}"


def _decision_message(level: str, message: str) -> None:
    renderers = {"success": st.success, "error": st.error, "warning": st.warning, "info": st.info}
    renderer = renderers[level]
    renderer(message)
