"""Streamlit dashboard entry point."""

import streamlit as st


def render_dashboard() -> None:
    """Render the M0 placeholder while API integrations are pending."""
    st.set_page_config(page_title="实时电商 A/B 与归因分析看板", layout="wide")
    st.title("实时电商 A/B 测试与归因分析看板")
    st.info("后端未连接／待接入：指标、漏斗与实验分析将在后续里程碑提供。")


if __name__ == "__main__":
    render_dashboard()
