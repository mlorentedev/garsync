"""Tests for IngestRunRepository — append-only ingest ledger."""

import sqlite3

import pytest

from garsync.db.repository import IngestRunRepository

pytestmark = pytest.mark.unit


class TestIngestRunRepository:
    def test_log_success(self, in_memory_db: sqlite3.Connection) -> None:
        repo = IngestRunRepository(in_memory_db)
        repo.log("activities", rows_upserted=10)

        row = repo.get_latest()
        assert row is not None
        assert row["sync_type"] == "activities"
        assert row["rows_upserted"] == 10
        assert row["status"] == "success"
        assert row["error_message"] is None

    def test_log_error(self, in_memory_db: sqlite3.Connection) -> None:
        repo = IngestRunRepository(in_memory_db)
        repo.log("biometrics", rows_upserted=0, status="error", error_message="API timeout")

        row = repo.get_latest()
        assert row is not None
        assert row["status"] == "error"
        assert row["error_message"] == "API timeout"

    def test_get_latest_by_type(self, in_memory_db: sqlite3.Connection) -> None:
        repo = IngestRunRepository(in_memory_db)
        repo.log("activities", rows_upserted=5)
        repo.log("biometrics", rows_upserted=3)
        repo.log("activities", rows_upserted=10)

        latest_activities = repo.get_latest(sync_type="activities")
        assert latest_activities is not None
        assert latest_activities["rows_upserted"] == 10

        latest_bio = repo.get_latest(sync_type="biometrics")
        assert latest_bio is not None
        assert latest_bio["rows_upserted"] == 3

    def test_get_latest_empty(self, in_memory_db: sqlite3.Connection) -> None:
        repo = IngestRunRepository(in_memory_db)
        assert repo.get_latest() is None

    def test_get_all(self, in_memory_db: sqlite3.Connection) -> None:
        repo = IngestRunRepository(in_memory_db)
        repo.log("activities", rows_upserted=5)
        repo.log("biometrics", rows_upserted=3)

        entries = repo.get_all()
        assert len(entries) == 2

    def test_count(self, in_memory_db: sqlite3.Connection) -> None:
        repo = IngestRunRepository(in_memory_db)
        assert repo.count() == 0
        repo.log("activities", rows_upserted=5)
        repo.log("sleep", rows_upserted=1)
        assert repo.count() == 2

    def test_append_only(self, in_memory_db: sqlite3.Connection) -> None:
        """Entries are never overwritten — each log() creates a new row."""
        repo = IngestRunRepository(in_memory_db)
        repo.log("activities", rows_upserted=5)
        repo.log("activities", rows_upserted=10)
        repo.log("activities", rows_upserted=15)

        entries = repo.get_all()
        assert len(entries) == 3
        counts = [e["rows_upserted"] for e in entries]
        assert counts == [15, 10, 5]  # DESC order
