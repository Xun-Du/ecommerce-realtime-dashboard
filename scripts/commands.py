"""Console commands declared in pyproject.toml."""

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _run(command: list[str]) -> None:
    """Run a child command from the repository root."""
    subprocess.run(command, cwd=PROJECT_ROOT, check=True)


def lint() -> None:
    """Run static checks."""
    _run([sys.executable, "-m", "ruff", "check", "."])


def test() -> None:
    """Run the automated test suite."""
    _run([sys.executable, "-m", "pytest"])


def run_api() -> None:
    """Start the FastAPI development server."""
    _run([sys.executable, "-m", "uvicorn", "backend.app.main:app", "--reload"])


def run_dashboard() -> None:
    """Start the Streamlit development server."""
    _run([sys.executable, "-m", "streamlit", "run", "frontend/app.py"])


def run_simulator() -> None:
    """Run the M1 event simulator placeholder."""
    _run([sys.executable, "scripts/simulate_events.py"])
