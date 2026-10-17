"""One unit of work per run — SUB-002, AC2.

The repositories used to commit once per row, which is invisible while the driver owns the transaction
and fatal once the run owns it: `commit()` inside an explicit `BEGIN` *ends* that transaction, and the
run silently becomes a sequence of independent commits (lesson 028). These tests assert the mechanism
rather than the intent, because a test that only looks at the rows cannot tell the two worlds apart.
"""

import sqlite3

import pytest

from garsync.db.connection import transaction
from garsync.db.repository import ActivityRepository


class TestTransactionOwnership:
    """Whoever opens the transaction owns the commit — and only they may end it."""

    def test_a_repository_write_does_not_end_the_callers_transaction(
        self, in_memory_db: sqlite3.Connection, sample_activity_row: dict
    ) -> None:
        repo = ActivityRepository(in_memory_db)
        with transaction(in_memory_db):
            repo.upsert(sample_activity_row)
            assert in_memory_db.in_transaction is True, "the run's transaction was ended from below"
        assert in_memory_db.in_transaction is False
        assert repo.count() == 1

    def test_the_negative_control_a_bare_commit_inside_begin_ends_it(
        self, in_memory_db: sqlite3.Connection
    ) -> None:
        """Proof that the assertion above can see the failure it exists to catch."""
        in_memory_db.execute("BEGIN IMMEDIATE")
        assert in_memory_db.in_transaction is True
        in_memory_db.execute(
            "INSERT INTO activities (activity_id, source, source_id) VALUES (1, 'garmin', '1')"
        )
        in_memory_db.commit()
        assert in_memory_db.in_transaction is False

    def test_a_failure_rolls_back_every_row_of_the_run(
        self, in_memory_db: sqlite3.Connection, sample_activity_row: dict
    ) -> None:
        repo = ActivityRepository(in_memory_db)
        with pytest.raises(RuntimeError, match="boom"), transaction(in_memory_db):
            repo.upsert(sample_activity_row)
            repo.upsert({**sample_activity_row, "activity_id": 2, "source_id": "2"})
            raise RuntimeError("boom")
        assert repo.count() == 0, "a half-written run survived the rollback"


class TestBatchAtomicity:
    """`upsert_batch` is a unit of work on its own, and joins one when there already is one."""

    def test_upsert_batch_is_atomic_on_its_own(
        self, in_memory_db: sqlite3.Connection, sample_activity_row: dict
    ) -> None:
        repo = ActivityRepository(in_memory_db)
        invalid = {**sample_activity_row, "activity_id": 999, "source_id": None}
        with pytest.raises(sqlite3.IntegrityError):
            repo.upsert_batch([sample_activity_row, invalid])
        assert repo.count() == 0, "the row before the failure committed on its own"

    def test_a_nested_block_joins_the_outer_transaction(
        self, in_memory_db: sqlite3.Connection, sample_activity_row: dict
    ) -> None:
        repo = ActivityRepository(in_memory_db)
        with transaction(in_memory_db):
            repo.upsert(sample_activity_row)
            with transaction(in_memory_db):
                repo.upsert({**sample_activity_row, "activity_id": 2, "source_id": "2"})
                assert in_memory_db.in_transaction is True
            assert in_memory_db.in_transaction is True, "the inner block committed the outer one"
            assert repo.count() == 2
        assert repo.count() == 2

    def test_a_nested_failure_rolls_back_the_outer_transaction(
        self, in_memory_db: sqlite3.Connection, sample_activity_row: dict
    ) -> None:
        repo = ActivityRepository(in_memory_db)
        with pytest.raises(RuntimeError, match="boom"), transaction(in_memory_db):
            repo.upsert(sample_activity_row)
            with transaction(in_memory_db):
                repo.upsert({**sample_activity_row, "activity_id": 2, "source_id": "2"})
                raise RuntimeError("boom")
        assert repo.count() == 0
