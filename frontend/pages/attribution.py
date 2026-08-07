"""Attribution analysis page."""

import streamlit as st

from backend.app.schemas.analytics import AttributionResponse
from frontend.components.attribution import render as render_attribution


def render(responses: dict[str, AttributionResponse]) -> None:
    available = sorted(responses)
    if not available:
        st.info("归因数据暂不可用，请稍后重试。")
        return
    selected = st.selectbox(
        "归因模型",
        available,
        index=available.index("last_touch") if "last_touch" in available else 0,
        format_func=lambda value: {
            "first_touch": "首次触达",
            "last_touch": "末次触达",
            "linear": "线性归因",
        }.get(value, value),
    )
    render_attribution(responses[selected], responses)
