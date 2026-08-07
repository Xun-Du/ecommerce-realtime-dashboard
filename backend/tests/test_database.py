"""Tests for database helper behavior that does not require Supabase access."""

from pathlib import Path

import pytest

from backend.app.core import database
from backend.app.core.database import INSERT_BATCH_SIZE, _batches, _statements, migration_files


def test_batches_split_large_inserts_below_the_postgres_parameter_limit() -> None:
    rows = list(range(INSERT_BATCH_SIZE * 2 + 17))

    batches = list(_batches(rows))

    assert [len(batch) for batch in batches] == [INSERT_BATCH_SIZE, INSERT_BATCH_SIZE, 17]
    assert [item for batch in batches for item in batch] == rows


def test_migration_files_are_discovered_in_version_order() -> None:
    names = [path.name for path in migration_files()]

    assert names == sorted(names)
    assert names[:2] == ["001_initial_schema.sql", "002_data_model_evolution.sql"]


def test_data_model_migration_backfills_legacy_facts_and_creates_new_tables() -> None:
    migration = Path("sql/002_data_model_evolution.sql")
    statements = "\n".join(_statements(migration))

    assert "CREATE TABLE IF NOT EXISTS experiments" in statements
    assert "CREATE TABLE IF NOT EXISTS experiment_assignments" in statements
    assert "ALTER TABLE events" in statements
    assert "ADD COLUMN IF NOT EXISTS order_id" in statements
    assert "event_id::TEXT" in statements
    assert "INSERT INTO experiment_assignments" in statements
    assert "idx_events_order_id_unique" in statements


def test_initialize_database_records_and_skips_applied_migrations(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / "001_initial_schema.sql").write_text("SELECT 1;", encoding="utf-8")
    (tmp_path / "002_data_model_evolution.sql").write_text("SELECT 2;", encoding="utf-8")
    fake_engine = FakeEngine(applied={"001_initial_schema.sql"})

    monkeypatch.setattr(database, "MIGRATIONS_DIRECTORY", tmp_path)
    monkeypatch.setattr(database, "get_engine", lambda: fake_engine)

    database.initialize_database()
    database.initialize_database()

    assert fake_engine.driver_sql_statements.count("SELECT 1") == 0
    assert fake_engine.driver_sql_statements.count("SELECT 2") == 1
    assert fake_engine.applied == {"001_initial_schema.sql", "002_data_model_evolution.sql"}


class FakeEngine:
    def __init__(self, applied: set[str]) -> None:
        self.applied = applied
        self.driver_sql_statements: list[str] = []

    def begin(self) -> "FakeConnection":
        return FakeConnection(self)


class FakeConnection:
    def __init__(self, engine: FakeEngine) -> None:
        self.engine = engine

    def __enter__(self) -> "FakeConnection":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def exec_driver_sql(self, statement: str) -> None:
        self.engine.driver_sql_statements.append(statement.strip())

    def execute(self, statement: object, params: dict[str, str] | None = None) -> "FakeResult":
        text = str(statement)
        if "SELECT migration_name" in text:
            return FakeResult([(name,) for name in self.engine.applied])
        if "INSERT INTO schema_migrations" in text and params is not None:
            self.engine.applied.add(params["migration_name"])
            return FakeResult([])
        return FakeResult([])


class FakeResult:
    def __init__(self, rows: list[tuple[str]]) -> None:
        self.rows = rows

    def all(self) -> list[tuple[str]]:
        return self.rows
