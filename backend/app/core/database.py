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
from backend.app.models.domain import Event, User

if TYPE_CHECKING:
    from scripts.data_generator import GeneratedBatch


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SCHEMA_FILE = PROJECT_ROOT / "sql" / "001_initial_schema.sql"
INSERT_BATCH_SIZE = 1_000


@lru_cache
def get_engine() -> Engine:
    """Return the shared SQLAlchemy engine for the configured Supabase database."""
    return create_engine(
        get_settings().database_url,
        connect_args={"connect_timeout": 5},
        pool_pre_ping=True,
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
    """Create the M1 schema and default experiment configuration idempotently."""
    statements = [part.strip() for part in SCHEMA_FILE.read_text(encoding="utf-8").split(";")]
    with get_engine().begin() as connection:
        for statement in statements:
            if statement:
                connection.exec_driver_sql(statement)


def reset_demo_data() -> None:
    """Remove only the three M1 Demo tables, in dependency order."""
    with get_engine().begin() as connection:
        connection.execute(text("DELETE FROM events"))
        connection.execute(text("DELETE FROM users"))
        connection.execute(text("DELETE FROM experiment_config"))


def write_batch(batch: "GeneratedBatch") -> None:
    """Insert one generated batch atomically, in PostgreSQL-safe statement sizes."""
    users = [record.as_database_row() for record in batch.users]
    events = [record.as_database_row() for record in batch.events]
    with get_engine().begin() as connection:
        for user_rows in _batches(users):
            connection.execute(
                insert(User).values(user_rows).on_conflict_do_nothing(index_elements=["user_id"])
            )
        for event_rows in _batches(events):
            connection.execute(
                insert(Event).values(event_rows).on_conflict_do_nothing(index_elements=["event_id"])
            )


def _batches[Row](rows: Sequence[Row], size: int = INSERT_BATCH_SIZE) -> Iterator[Sequence[Row]]:
    """Yield rows in chunks that stay below PostgreSQL's bind-parameter limit."""
    for start in range(0, len(rows), size):
        yield rows[start : start + size]


def default_experiment_exists() -> bool:
    """Return whether initialization has created the default experiment."""
    with get_engine().connect() as connection:
        return connection.execute(
            text("SELECT EXISTS (SELECT 1 FROM experiment_config WHERE experiment_id = :id)"),
            {"id": "homepage_checkout_v1"},
        ).scalar_one()
