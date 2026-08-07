"""Attribution-specific Streamlit visual components."""

import plotly.graph_objects as go
import streamlit as st

from backend.app.schemas.analytics import AttributionResponse
from frontend.components.dashboard import format_currency, format_percentage
from frontend.theme import plotly_layout


def render(response: AttributionResponse, comparison: dict[str, AttributionResponse]) -> None:
    if response.total_orders == 0:
        st.info("当前筛选范围暂无归因数据。")
        return
    top = next((item for item in response.channels if item.channel != "unknown"), None)
    cards = st.columns(4)
    cards[0].metric("归因 GMV", format_currency(response.attributed_gmv))
    cards[1].metric("归因订单", f"{float(response.attributed_orders):,.2f}")
    cards[2].metric("Unknown 占比", format_percentage(response.data_quality.unknown_channel_share))
    cards[3].metric("Top Channel", top.channel if top else "—")

    if response.data_quality.warnings:
        for warning in response.data_quality.warnings:
            st.warning(warning)

    st.caption("归因代表规则下的贡献分配，不等同于因果增量。")
    labels = [item.channel for item in response.channels]
    figure = go.Figure(
        go.Bar(
            x=labels,
            y=[float(item.gmv_credit) for item in response.channels],
            name="GMV 贡献",
        )
    )
    figure.update_layout(**plotly_layout(title="渠道 GMV 贡献", yaxis_title="GMV（¥）"))
    st.plotly_chart(figure, use_container_width=True)

    st.subheader("渠道贡献排行")
    st.dataframe(
        [
            {
                "排名": item.rank,
                "渠道": item.channel,
                "订单贡献": float(item.order_credit),
                "GMV贡献": float(item.gmv_credit),
                "GMV占比": format_percentage(item.gmv_share),
            }
            for item in response.channels
        ],
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("模型对比")
    comparison_rows = []
    for model, item in comparison.items():
        by_channel = {channel.channel: channel for channel in item.channels}
        comparison_rows.extend(
            {
                "模型": model,
                "渠道": channel,
                "GMV贡献": float(value.gmv_credit),
                "GMV占比": format_percentage(value.gmv_share),
            }
            for channel, value in by_channel.items()
        )
    st.dataframe(comparison_rows, use_container_width=True, hide_index=True)

    st.subheader("活动与触点路径")
    for campaign in response.campaigns:
        st.caption(
            f"{campaign.campaign_name or campaign.campaign_id} · "
            f"GMV {format_currency(campaign.gmv_credit)} · "
            f"订单 {float(campaign.order_credit):,.2f}"
        )
    if response.touchpoint_paths:
        st.dataframe(
            [
                {
                    "订单": path.order_id,
                    "订单时间": path.order_time,
                    "订单金额": format_currency(path.order_value),
                    "触点路径": " → ".join(point.channel for point in path.touchpoints)
                    or "unknown",
                }
                for path in response.touchpoint_paths
            ],
            use_container_width=True,
            hide_index=True,
        )
