"""PostgreSQL connection and M1 data-writing helpers."""

from collections.abc import Iterator, Sequence
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

from sqlalchemy import create_engine, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from backend.app.core.config import get_settings
from backend.app.models.domain import Event, ExperimentAssignment, User

if TYPE_CHECKING:
    from scripts.data_generator import GeneratedBatch


PROJECT_ROOT = Path(__file__).resolve().parents[3]
MIGRATIONS_DIRECTORY = PROJECT_ROOT / "sql"
INSERT_BATCH_SIZE = 1_000


@lru_cache
def get_engine() -> Engine:
    """Return the shared SQLAlchemy engine for the configured Supabase database."""
    return create_engine(
        get_settings().database_url,
        connect_args={"connect_timeout": 5},
        # Supabase Session Pooler plans have a low per-client connection cap.
        # Keep the web process well below it and queue short-lived requests locally.
        pool_size=3,
        max_overflow=0,
        pool_pre_ping=True,
        pool_recycle=300,
        pool_timeout=10,
        pool_use_lifo=True,
    )


def database_is_available() -> bool:
    """Check connectivity without returning database implementation details."""
    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return False
    return True


def initialize_database() -> None:
    """Apply pending SQL migrations atomically in filename order."""
    with get_engine().begin() as connection:
        connection.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                migration_name VARCHAR(255) PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        applied = {
            row[0]
            for row in connection.execute(
                text("SELECT migration_name FROM schema_migrations")
            ).all()
        }
        for migration in migration_files():
            if migration.name in applied:
                continue
            for statement in _statements(migration):
                connection.exec_driver_sql(statement)
            connection.execute(
                text(
                    "INSERT INTO schema_migrations (migration_name) "
                    "VALUES (:migration_name)"
                ),
                {"migration_name": migration.name},
            )


def reset_demo_data() -> None:
    """Remove generated facts while preserving migrated experiment configuration."""
    with get_engine().begin() as connection:
        connection.execute(text("DELETE FROM experiment_results"))
        connection.execute(text("DELETE FROM experiment_assignments"))
        connection.execute(text("DELETE FROM events"))
        connection.execute(text("DELETE FROM users"))


def write_batch(batch: "GeneratedBatch") -> None:
    """Insert one generated batch atomically, in PostgreSQL-safe statement sizes."""
    users = [record.as_database_row() for record in batch.users]
    events = [record.as_database_row() for record in batch.events]
    assignments = [record.as_database_row() for record in batch.assignments]
    with get_engine().begin() as connection:
        for user_rows in _batches(users):
            connection.execute(
                insert(User).values(user_rows).on_conflict_do_nothing(index_elements=["user_id"])
            )
        for assignment_rows in _batches(assignments):
            connection.execute(
                insert(ExperimentAssignment)
                .values(assignment_rows)
                .on_conflict_do_nothing(index_elements=["experiment_id", "user_id"])
            )
        for event_rows in _batches(events):
            connection.execute(
                insert(Event).values(event_rows).on_conflict_do_nothing(index_elements=["event_id"])
            )


def _batches[Row](rows: Sequence[Row], size: int = INSERT_BATCH_SIZE) -> Iterator[Sequence[Row]]:
    """Yield rows in chunks that stay below PostgreSQL's bind-parameter limit."""
    for start in range(0, len(rows), size):
        yield rows[start : start + size]


def migration_files() -> list[Path]:
    """Return versioned SQL migrations in deterministic filename order."""
    return sorted(MIGRATIONS_DIRECTORY.glob("[0-9][0-9][0-9]_*.sql"))


def _statements(migration: Path) -> list[str]:
    """Split the project's simple SQL migration files into executable statements."""
    return [
        statement.strip()
        for statement in migration.read_text(encoding="utf-8").split(";")
        if statement.strip()
    ]


def default_experiment_exists() -> bool:
    """Return whether initialization has created the default experiment."""
    with get_engine().connect() as connection:
        return connection.execute(
            text("SELECT EXISTS (SELECT 1 FROM experiments WHERE experiment_id = :id)"),
            {"id": "homepage_checkout_v1"},
        ).scalar_one()
