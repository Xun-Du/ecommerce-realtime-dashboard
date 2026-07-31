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
    """Run the M1 event simulator."""
    _run([sys.executable, "scripts/simulate_events.py"])


def init_db() -> None:
    """Create the M1 database schema."""
    result = subprocess.run([sys.executable, "scripts/init_db.py"], cwd=PROJECT_ROOT, check=False)
    if result.returncode:
        raise SystemExit(result.returncode)


def seed_data() -> None:
    """Generate the default historical M1 data set."""
    _run([sys.executable, "scripts/seed_data.py"])
