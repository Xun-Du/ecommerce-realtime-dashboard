"""Tests for database helper behavior that does not require Supabase access."""

from backend.app.core.database import INSERT_BATCH_SIZE, _batches


def test_batches_split_large_inserts_below_the_postgres_parameter_limit() -> None:
    rows = list(range(INSERT_BATCH_SIZE * 2 + 17))

    batches = list(_batches(rows))

    assert [len(batch) for batch in batches] == [INSERT_BATCH_SIZE, INSERT_BATCH_SIZE, 17]
    assert [item for batch in batches for item in batch] == rows
