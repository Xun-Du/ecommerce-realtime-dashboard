"""Explicit empty states for modules whose APIs are scheduled for later milestones."""

import streamlit as st


def render_placeholder(page_key: str) -> None:
    st.info("该模块已纳入产品壳层，业务数据能力规划中。")
    st.markdown("**当前边界**：本阶段不请求不存在的 API，也不展示伪造的业务结果。")
    dependencies = {
        "attribution": "M5：多触点事件、活动字段和规则型归因服务",
        "customers": "M7：新老客、复购和客户分群指标",
        "creatives": "M8：campaign/素材数据接入",
        "integrations": "M8：Shopify、广告平台和埋点 SDK 连接器",
    }
    st.caption(f"预计依赖：{dependencies[page_key]}")
