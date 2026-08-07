"""Legacy single-experiment view used until M6 resource APIs land."""

from frontend.components.dashboard import render_experiment


def render(experiment) -> None:
    render_experiment(experiment)
