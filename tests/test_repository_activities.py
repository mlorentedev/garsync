"""Tests for ActivityRepository — CRUD + upsert deduplication + pagination/aggregation."""

import json
import sqlite3

from garsync.db.repository import ActivityRepository


class TestActivityRepository:
    def test_upsert_inserts_new(
        self, in_memory_db: sqlite3.Connection, sample_activity_row: dict
    ) -> None:
        repo = ActivityRepository(in_memory_db)
        repo.upsert(sample_activity_row)

        row = in_memory_db.execute(
            "SELECT * FROM activities WHERE activity_id = ?",
            (sample_activity_row["activity_id"],),
        ).fetchone()
        assert row is not None
        assert row["activity_name"] == "Morning Run"
        assert row["activity_type"] == "running"

    def test_upsert_updates_existing(
        self, in_memory_db: sqlite3.Connection, sample_activity_row: dict
    ) -> None:
        repo = ActivityRepository(in_memory_db)
        repo.upsert(sample_activity_row)

        updated = {
            **sample_activity_row,
            "activity_name": "Evening Run",
            "calories": 500.0,
        }
        repo.upsert(updated)

        row = in_memory_db.execute(
            "SELECT * FROM activities WHERE activity_id = ?",
            (sample_activity_row["activity_id"],),
        ).fetchone()
        assert row["activity_name"] == "Evening Run"
        assert row["calories"] == 500.0

    def test_upsert_does_not_duplicate(
        self, in_memory_db: sqlite3.Connection, sample_activity_row: dict
    ) -> None:
        repo = ActivityRepository(in_memory_db)
        repo.upsert(sample_activity_row)
        repo.upsert(sample_activity_row)

        count = in_memory_db.execute("SELECT COUNT(*) as cnt FROM activities").fetchone()["cnt"]
        assert count == 1

    def test_get_by_id(self, in_memory_db: sqlite3.Connection, sample_activity_row: dict) -> None:
        repo = ActivityRepository(in_memory_db)
        repo.upsert(sample_activity_row)

        row = repo.get_by_id(sample_activity_row["activity_id"])
        assert row is not None
        assert row["activity_id"] == sample_activity_row["activity_id"]

    def test_get_by_id_missing_returns_none(self, in_memory_db: sqlite3.Connection) -> None:
        repo = ActivityRepository(in_memory_db)
        assert repo.get_by_id(999999) is None

    def test_get_all(self, in_memory_db: sqlite3.Connection, sample_activity_row: dict) -> None:
        repo = ActivityRepository(in_memory_db)
        row2 = {
            **sample_activity_row,
            "activity_id": 987654321,
            "activity_name": "Swim",
        }
        repo.upsert(sample_activity_row)
        repo.upsert(row2)

        rows = repo.get_all()
        assert len(rows) == 2

    def test_get_all_empty(self, in_memory_db: sqlite3.Connection) -> None:
        repo = ActivityRepository(in_memory_db)
        assert repo.get_all() == []

    def test_upsert_batch(
        self, in_memory_db: sqlite3.Connection, sample_activity_row: dict
    ) -> None:
        repo = ActivityRepository(in_memory_db)
        rows = [
            sample_activity_row,
            {**sample_activity_row, "activity_id": 111, "activity_name": "Bike"},
            {**sample_activity_row, "activity_id": 222, "activity_name": "Hike"},
        ]
        repo.upsert_batch(rows)

        count = in_memory_db.execute("SELECT COUNT(*) as cnt FROM activities").fetchone()["cnt"]
        assert count == 3

    def test_count(self, in_memory_db: sqlite3.Connection, sample_activity_row: dict) -> None:
        repo = ActivityRepository(in_memory_db)
        assert repo.count() == 0
        repo.upsert(sample_activity_row)
        assert repo.count() == 1


def _seed_activities(repo: ActivityRepository, base_row: dict, count: int = 5) -> None:
    """Seed multiple activities with varying dates and types."""
    types = ["running", "cycling", "swimming", "running", "hiking"]
    for i in range(count):
        repo.upsert(
            {
                **base_row,
                "activity_id": 1000 + i,
                "activity_name": f"Activity {i}",
                "activity_type": types[i % len(types)],
                "start_time": f"2026-02-{20 + i:02d}T08:00:00",
                "duration_seconds": 1800.0 + i * 600,
                "distance_meters": 5000.0 + i * 1000,
                "calories": 300.0 + i * 50,
                "raw_data": json.dumps({"activityId": 1000 + i}),
            }
        )


class TestActivityRepositoryPaginated:
    def test_get_paginated_returns_page_and_total(
        self, in_memory_db: sqlite3.Connection, sample_activity_row: dict
    ) -> None:
        repo = ActivityRepository(in_memory_db)
        _seed_activities(repo, sample_activity_row, 5)

        rows, total = repo.get_paginated(page=1, limit=2)
        assert total == 5
        assert len(rows) == 2

    def test_get_paginated_second_page(
        self, in_memory_db: sqlite3.Connection, sample_activity_row: dict
    ) -> None:
        repo = ActivityRepository(in_memory_db)
        _seed_activities(repo, sample_activity_row, 5)

        rows, total = repo.get_paginated(page=2, limit=2)
        assert total == 5
        assert len(rows) == 2

    def test_get_paginated_filters_by_date_range(
        self, in_memory_db: sqlite3.Connection, sample_activity_row: dict
    ) -> None:
        repo = ActivityRepository(in_memory_db)
        _seed_activities(repo, sample_activity_row, 5)

        rows, total = repo.get_paginated(
            page=1, limit=10, start_date="2026-02-21", end_date="2026-02-23"
        )
        assert total == 3  # Feb 21, 22, 23

    def test_get_paginated_filters_by_activity_type(
        self, in_memory_db: sqlite3.Connection, sample_activity_row: dict
    ) -> None:
        repo = ActivityRepository(in_memory_db)
        _seed_activities(repo, sample_activity_row, 5)

        rows, total = repo.get_paginated(page=1, limit=10, activity_type="running")
        assert total == 2  # indices 0 and 3

    def test_get_paginated_empty(self, in_memory_db: sqlite3.Connection) -> None:
        repo = ActivityRepository(in_memory_db)
        rows, total = repo.get_paginated(page=1, limit=10)
        assert total == 0
        assert rows == []


class TestActivityRepositoryHeatmap:
    def test_get_heatmap_data_returns_daily_aggregates(
        self, in_memory_db: sqlite3.Connection, sample_activity_row: dict
    ) -> None:
        repo = ActivityRepository(in_memory_db)
        _seed_activities(repo, sample_activity_row, 5)

        rows = repo.get_heatmap_data(year=2026)
        assert len(rows) == 5
        assert rows[0]["activity_count"] >= 1

    def test_get_heatmap_data_filters_by_type(
        self, in_memory_db: sqlite3.Connection, sample_activity_row: dict
    ) -> None:
        repo = ActivityRepository(in_memory_db)
        _seed_activities(repo, sample_activity_row, 5)

        rows = repo.get_heatmap_data(year=2026, activity_type="running")
        assert len(rows) == 2

    def test_get_heatmap_data_empty_year(self, in_memory_db: sqlite3.Connection) -> None:
        repo = ActivityRepository(in_memory_db)
        rows = repo.get_heatmap_data(year=2099)
        assert rows == []


class TestActivityRepositorySummaryStats:
    def test_get_summary_stats_returns_aggregates(
        self, in_memory_db: sqlite3.Connection, sample_activity_row: dict
    ) -> None:
        repo = ActivityRepository(in_memory_db)
        _seed_activities(repo, sample_activity_row, 5)

        stats = repo.get_summary_stats("2026-02-20", "2026-02-24")
        assert stats is not None
        assert stats["total_activities"] == 5
        assert stats["total_duration_seconds"] > 0
        assert stats["total_distance_meters"] > 0
        assert stats["total_calories"] > 0

    def test_get_summary_stats_empty_range(self, in_memory_db: sqlite3.Connection) -> None:
        repo = ActivityRepository(in_memory_db)
        stats = repo.get_summary_stats("2099-01-01", "2099-01-31")
        assert stats is not None
        assert stats["total_activities"] == 0
