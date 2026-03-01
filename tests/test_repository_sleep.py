"""Tests for SleepRepository — CRUD + incremental sync helpers."""

import sqlite3

from garsync.db.repository import SleepRepository


class TestSleepRepository:
    def test_upsert_inserts_new(
        self, in_memory_db: sqlite3.Connection, sample_sleep_row: dict
    ) -> None:
        repo = SleepRepository(in_memory_db)
        repo.upsert(sample_sleep_row)

        row = in_memory_db.execute(
            "SELECT * FROM sleep WHERE date = ?",
            (sample_sleep_row["date"],),
        ).fetchone()
        assert row is not None
        assert row["sleep_score"] == 82

    def test_upsert_updates_existing(
        self, in_memory_db: sqlite3.Connection, sample_sleep_row: dict
    ) -> None:
        repo = SleepRepository(in_memory_db)
        repo.upsert(sample_sleep_row)

        updated = {**sample_sleep_row, "sleep_score": 90}
        repo.upsert(updated)

        row = repo.get_by_date(sample_sleep_row["date"])
        assert row is not None
        assert row["sleep_score"] == 90

    def test_upsert_does_not_duplicate(
        self, in_memory_db: sqlite3.Connection, sample_sleep_row: dict
    ) -> None:
        repo = SleepRepository(in_memory_db)
        repo.upsert(sample_sleep_row)
        repo.upsert(sample_sleep_row)
        assert repo.count() == 1

    def test_get_by_date(self, in_memory_db: sqlite3.Connection, sample_sleep_row: dict) -> None:
        repo = SleepRepository(in_memory_db)
        repo.upsert(sample_sleep_row)

        row = repo.get_by_date("2026-02-28")
        assert row is not None
        assert row["total_sleep_seconds"] == 27000

    def test_get_by_date_missing_returns_none(self, in_memory_db: sqlite3.Connection) -> None:
        repo = SleepRepository(in_memory_db)
        assert repo.get_by_date("2099-01-01") is None

    def test_get_latest_date(
        self, in_memory_db: sqlite3.Connection, sample_sleep_row: dict
    ) -> None:
        repo = SleepRepository(in_memory_db)
        repo.upsert(sample_sleep_row)
        repo.upsert({**sample_sleep_row, "date": "2026-02-27"})
        repo.upsert({**sample_sleep_row, "date": "2026-03-01"})

        assert repo.get_latest_date() == "2026-03-01"

    def test_get_latest_date_empty(self, in_memory_db: sqlite3.Connection) -> None:
        repo = SleepRepository(in_memory_db)
        assert repo.get_latest_date() is None

    def test_count(self, in_memory_db: sqlite3.Connection, sample_sleep_row: dict) -> None:
        repo = SleepRepository(in_memory_db)
        assert repo.count() == 0
        repo.upsert(sample_sleep_row)
        assert repo.count() == 1

    def test_handles_null_optionals(self, in_memory_db: sqlite3.Connection) -> None:
        repo = SleepRepository(in_memory_db)
        row = {
            "date": "2026-02-25",
            "sleep_start": None,
            "sleep_end": None,
            "total_sleep_seconds": None,
            "deep_sleep_seconds": None,
            "light_sleep_seconds": None,
            "rem_sleep_seconds": None,
            "awake_sleep_seconds": None,
            "sleep_score": None,
            "raw_data": "{}",
        }
        repo.upsert(row)
        result = repo.get_by_date("2026-02-25")
        assert result is not None
        assert result["sleep_score"] is None


def _seed_sleep(repo: SleepRepository, base_row: dict) -> None:
    """Seed 5 days of sleep data."""
    for i in range(5):
        repo.upsert(
            {
                **base_row,
                "date": f"2026-02-{20 + i:02d}",
                "total_sleep_seconds": 25000 + i * 1000,
                "deep_sleep_seconds": 6000 + i * 200,
                "sleep_score": 75 + i * 2,
            }
        )


class TestSleepRepositoryDateRange:
    def test_get_by_date_range(
        self, in_memory_db: sqlite3.Connection, sample_sleep_row: dict
    ) -> None:
        repo = SleepRepository(in_memory_db)
        _seed_sleep(repo, sample_sleep_row)

        rows = repo.get_by_date_range("2026-02-21", "2026-02-23")
        assert len(rows) == 3

    def test_get_by_date_range_empty(self, in_memory_db: sqlite3.Connection) -> None:
        repo = SleepRepository(in_memory_db)
        rows = repo.get_by_date_range("2099-01-01", "2099-01-31")
        assert rows == []


class TestSleepRepositoryAvgStats:
    def test_get_avg_stats(self, in_memory_db: sqlite3.Connection, sample_sleep_row: dict) -> None:
        repo = SleepRepository(in_memory_db)
        _seed_sleep(repo, sample_sleep_row)

        stats = repo.get_avg_stats("2026-02-20", "2026-02-24")
        assert stats is not None
        assert stats["avg_sleep_seconds"] is not None
        assert stats["avg_sleep_score"] is not None
        assert stats["record_count"] == 5

    def test_get_avg_stats_empty_range(self, in_memory_db: sqlite3.Connection) -> None:
        repo = SleepRepository(in_memory_db)
        stats = repo.get_avg_stats("2099-01-01", "2099-01-31")
        assert stats is not None
        assert stats["record_count"] == 0
