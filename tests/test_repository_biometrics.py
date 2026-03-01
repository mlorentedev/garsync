"""Tests for BiometricsRepository — CRUD + incremental sync helpers."""

import sqlite3

from garsync.db.repository import BiometricsRepository


class TestBiometricsRepository:
    def test_upsert_inserts_new(
        self, in_memory_db: sqlite3.Connection, sample_biometrics_row: dict
    ) -> None:
        repo = BiometricsRepository(in_memory_db)
        repo.upsert(sample_biometrics_row)

        row = in_memory_db.execute(
            "SELECT * FROM biometrics WHERE date = ?",
            (sample_biometrics_row["date"],),
        ).fetchone()
        assert row is not None
        assert row["resting_heart_rate"] == 52

    def test_upsert_updates_existing(
        self, in_memory_db: sqlite3.Connection, sample_biometrics_row: dict
    ) -> None:
        repo = BiometricsRepository(in_memory_db)
        repo.upsert(sample_biometrics_row)

        updated = {**sample_biometrics_row, "resting_heart_rate": 48}
        repo.upsert(updated)

        row = repo.get_by_date(sample_biometrics_row["date"])
        assert row is not None
        assert row["resting_heart_rate"] == 48

    def test_upsert_does_not_duplicate(
        self, in_memory_db: sqlite3.Connection, sample_biometrics_row: dict
    ) -> None:
        repo = BiometricsRepository(in_memory_db)
        repo.upsert(sample_biometrics_row)
        repo.upsert(sample_biometrics_row)
        assert repo.count() == 1

    def test_get_by_date(
        self, in_memory_db: sqlite3.Connection, sample_biometrics_row: dict
    ) -> None:
        repo = BiometricsRepository(in_memory_db)
        repo.upsert(sample_biometrics_row)

        row = repo.get_by_date("2026-02-28")
        assert row is not None
        assert row["stress_average"] == 28

    def test_get_by_date_missing_returns_none(self, in_memory_db: sqlite3.Connection) -> None:
        repo = BiometricsRepository(in_memory_db)
        assert repo.get_by_date("2099-01-01") is None

    def test_get_latest_date(
        self, in_memory_db: sqlite3.Connection, sample_biometrics_row: dict
    ) -> None:
        repo = BiometricsRepository(in_memory_db)
        repo.upsert(sample_biometrics_row)
        repo.upsert({**sample_biometrics_row, "date": "2026-02-27"})
        repo.upsert({**sample_biometrics_row, "date": "2026-03-01"})

        assert repo.get_latest_date() == "2026-03-01"

    def test_get_latest_date_empty(self, in_memory_db: sqlite3.Connection) -> None:
        repo = BiometricsRepository(in_memory_db)
        assert repo.get_latest_date() is None

    def test_count(self, in_memory_db: sqlite3.Connection, sample_biometrics_row: dict) -> None:
        repo = BiometricsRepository(in_memory_db)
        assert repo.count() == 0
        repo.upsert(sample_biometrics_row)
        assert repo.count() == 1


def _seed_biometrics(repo: BiometricsRepository, base_row: dict) -> None:
    """Seed 5 days of biometrics data."""
    for i in range(5):
        repo.upsert(
            {
                **base_row,
                "date": f"2026-02-{20 + i:02d}",
                "resting_heart_rate": 50 + i,
                "stress_average": 25 + i * 2,
                "body_battery_highest": 90 - i,
            }
        )


class TestBiometricsRepositoryDateRange:
    def test_get_by_date_range(
        self, in_memory_db: sqlite3.Connection, sample_biometrics_row: dict
    ) -> None:
        repo = BiometricsRepository(in_memory_db)
        _seed_biometrics(repo, sample_biometrics_row)

        rows = repo.get_by_date_range("2026-02-21", "2026-02-23")
        assert len(rows) == 3

    def test_get_by_date_range_empty(self, in_memory_db: sqlite3.Connection) -> None:
        repo = BiometricsRepository(in_memory_db)
        rows = repo.get_by_date_range("2099-01-01", "2099-01-31")
        assert rows == []


class TestBiometricsRepositoryAvgStats:
    def test_get_avg_stats(
        self, in_memory_db: sqlite3.Connection, sample_biometrics_row: dict
    ) -> None:
        repo = BiometricsRepository(in_memory_db)
        _seed_biometrics(repo, sample_biometrics_row)

        stats = repo.get_avg_stats("2026-02-20", "2026-02-24")
        assert stats is not None
        assert stats["avg_resting_heart_rate"] is not None
        assert stats["avg_stress"] is not None
        assert stats["record_count"] == 5

    def test_get_avg_stats_empty_range(self, in_memory_db: sqlite3.Connection) -> None:
        repo = BiometricsRepository(in_memory_db)
        stats = repo.get_avg_stats("2099-01-01", "2099-01-31")
        assert stats is not None
        assert stats["record_count"] == 0
