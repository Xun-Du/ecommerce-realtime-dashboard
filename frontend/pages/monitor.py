"""Metric monitoring page, reusing the M4 analytics sections."""

from frontend.components.dashboard import render_metric_cards, render_trends


def render(metrics) -> None:
    render_metric_cards(metrics)
    render_trends(metrics)
