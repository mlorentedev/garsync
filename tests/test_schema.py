"""Tests for db/schema.py — the Alembic chain, its version SSOT, and the v2 shape.

The `init_db` cases here are the v2 schema; the v1→v2 transformation itself is exercised in
`tests/test_migrations.py`, which builds its *from* state from a frozen DDL.
"""

import sqlite3

import pytest

from garsync.db.repository import IngestRunRepository
from garsync.db.schema import init_db

pytestmark = pytest.mark.unit

V2_TABLES = {"activities", "daily_metrics", "sleep_sessions", "ingest_run", "goals"}


class TestInitDb:
    """Verify init_db produces the v2 schema and records its revision."""

    def test_creates_all_tables(self, in_memory_db: sqlite3.Connection) -> None:
        cursor = in_memory_db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = {row["name"] for row in cursor.fetchall()}
        assert V2_TABLES.issubset(tables)
        assert "alembic_version" in tables

    def test_the_v1_names_are_gone(self, in_memory_db: sqlite3.Connection) -> None:
        """`schema_version` was the pre-Alembic version SSOT, and two table names were renames.

        `sync_log` is the deliberate exception: it is kept, in place and inert, until SUB-002 retires
        it — the rows were *copied* into `ingest_run`, so a bug in the copy would still be recoverable
        from the original. A fresh database carries it for the same reason the chain has no branch on
        "new": one schema, produced one way.
        """
        cursor = in_memory_db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = {row["name"] for row in cursor.fetchall()}
        assert tables.isdisjoint({"schema_version", "biometrics", "sleep"})
        assert "sync_log" in tables
        assert in_memory_db.execute("SELECT COUNT(*) AS c FROM sync_log").fetchone()["c"] == 0

    def test_nothing_is_written_to_the_legacy_table(self, in_memory_db: sqlite3.Connection) -> None:
        """Inert means inert: the ledger and the audit both moved, and no code path logs to v1's
        table any more."""
        IngestRunRepository(in_memory_db).log("activities", rows_upserted=1)
        assert in_memory_db.execute("SELECT COUNT(*) AS c FROM sync_log").fetchone()["c"] == 0
        assert in_memory_db.execute("SELECT COUNT(*) AS c FROM ingest_run").fetchone()["c"] == 1

    def test_activities_columns(self, in_memory_db: sqlite3.Connection) -> None:
        cursor = in_memory_db.execute("PRAGMA table_info(activities)")
        columns = {row["name"] for row in cursor.fetchall()}
        expected = {
            "activity_id",
            "source",
            "source_id",
            "activity_name",
            "activity_type",
            "start_time",
            "tz_offset_minutes",
            "duration_seconds",
            "distance_meters",
            "average_heart_rate",
            "max_heart_rate",
            "calories",
            "training_load",
            "aerobic_te",
            "anaerobic_te",
            "normalized_power",
            "avg_power",
            "raw_data",
            "created_at",
            "updated_at",
        }
        assert expected.issubset(columns)

    def test_daily_metrics_columns(self, in_memory_db: sqlite3.Connection) -> None:
        cursor = in_memory_db.execute("PRAGMA table_info(daily_metrics)")
        columns = {row["name"] for row in cursor.fetchall()}
        expected = {
            "date",
            "resting_heart_rate",
            "hrv_baseline_status",
            "hrv_last_night_avg",
            "hrv_weekly_avg",
            "hrv_baseline_low",
            "hrv_baseline_high",
            "body_battery_highest",
            "body_battery_lowest",
            "stress_average",
            "raw_data",
            "created_at",
            "updated_at",
        }
        assert expected.issubset(columns)

    def test_sleep_sessions_columns(self, in_memory_db: sqlite3.Connection) -> None:
        cursor = in_memory_db.execute("PRAGMA table_info(sleep_sessions)")
        columns = {row["name"] for row in cursor.fetchall()}
        expected = {
            "date",
            "sleep_start",
            "sleep_end",
            "sleep_need_seconds",
            "total_sleep_seconds",
            "deep_sleep_seconds",
            "light_sleep_seconds",
            "rem_sleep_seconds",
            "awake_sleep_seconds",
            "sleep_score",
            "raw_data",
            "created_at",
            "updated_at",
        }
        assert expected.issubset(columns)

    def test_ingest_run_columns(self, in_memory_db: sqlite3.Connection) -> None:
        cursor = in_memory_db.execute("PRAGMA table_info(ingest_run)")
        columns = {row["name"] for row in cursor.fetchall()}
        expected = {
            "id",
            "source",
            "sync_type",
            "rows_upserted",
            "status",
            "error_message",
            "cursor_before",
            "cursor_after",
            "created_at",
        }
        assert expected.issubset(columns)

    def test_idempotent_init(self, in_memory_db: sqlite3.Connection) -> None:
        """Calling init_db twice should not raise or duplicate data."""
        init_db(in_memory_db)
        cursor = in_memory_db.execute("SELECT COUNT(*) as cnt FROM alembic_version")
        assert cursor.fetchone()["cnt"] == 1

    def test_activities_pk_is_activity_id(self, in_memory_db: sqlite3.Connection) -> None:
        cursor = in_memory_db.execute("PRAGMA table_info(activities)")
        pk_cols = [row["name"] for row in cursor.fetchall() if row["pk"] > 0]
        assert pk_cols == ["activity_id"]

    def test_daily_metrics_pk_is_date(self, in_memory_db: sqlite3.Connection) -> None:
        cursor = in_memory_db.execute("PRAGMA table_info(daily_metrics)")
        pk_cols = [row["name"] for row in cursor.fetchall() if row["pk"] > 0]
        assert pk_cols == ["date"]

    def test_sleep_sessions_pk_is_date(self, in_memory_db: sqlite3.Connection) -> None:
        cursor = in_memory_db.execute("PRAGMA table_info(sleep_sessions)")
        pk_cols = [row["name"] for row in cursor.fetchall() if row["pk"] > 0]
        assert pk_cols == ["date"]
