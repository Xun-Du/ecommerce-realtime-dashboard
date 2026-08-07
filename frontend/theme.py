"""Central visual tokens shared by all Streamlit pages."""

ACCENT = "#f05a9d"
POSITIVE = "#45c98a"
RISK = "#ef6b73"
MUTED = "#8e96a8"


def apply_theme() -> None:
    """Apply the common desktop application-shell styling."""
    import streamlit as st

    st.markdown(
        """
        <style>
        [data-testid="stSidebar"] { background: #151722; }
        [data-testid="stMetric"] { background: #1b1e2b; border: 1px solid #303446;
          border-radius: 8px; padding: 12px; }
        .shell-caption { color: #8e96a8; font-size: 0.82rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def plotly_layout(**kwargs) -> dict:
    layout = dict(
        template="plotly_dark",
        paper_bgcolor="#1b1e2b",
        plot_bgcolor="#1b1e2b",
        font=dict(color="#e7e9ef"),
        margin=dict(l=20, r=20, t=50, b=20),
        colorway=[ACCENT, "#7b8cff", POSITIVE, "#f2b866"],
    )
    layout.update(kwargs)
    return layout
