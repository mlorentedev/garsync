"""Tests for db/schema.py — DDL creation, migrations, version tracking."""

import sqlite3

from garsync.db.schema import CURRENT_VERSION, init_db


class TestInitDb:
    """Verify init_db creates all expected tables and indexes."""

    def test_creates_all_tables(self, in_memory_db: sqlite3.Connection) -> None:
        cursor = in_memory_db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = {row["name"] for row in cursor.fetchall()}
        expected = {"activities", "biometrics", "sleep", "sync_log", "schema_version"}
        assert expected.issubset(tables)

    def test_activities_columns(self, in_memory_db: sqlite3.Connection) -> None:
        cursor = in_memory_db.execute("PRAGMA table_info(activities)")
        columns = {row["name"] for row in cursor.fetchall()}
        expected = {
            "activity_id",
            "activity_name",
            "activity_type",
            "start_time",
            "duration_seconds",
            "distance_meters",
            "average_heart_rate",
            "max_heart_rate",
            "calories",
            "raw_data",
            "created_at",
            "updated_at",
        }
        assert expected.issubset(columns)

    def test_biometrics_columns(self, in_memory_db: sqlite3.Connection) -> None:
        cursor = in_memory_db.execute("PRAGMA table_info(biometrics)")
        columns = {row["name"] for row in cursor.fetchall()}
        expected = {
            "date",
            "resting_heart_rate",
            "hrv_balance",
            "body_battery_highest",
            "body_battery_lowest",
            "stress_average",
            "raw_data",
            "created_at",
            "updated_at",
        }
        assert expected.issubset(columns)

    def test_sleep_columns(self, in_memory_db: sqlite3.Connection) -> None:
        cursor = in_memory_db.execute("PRAGMA table_info(sleep)")
        columns = {row["name"] for row in cursor.fetchall()}
        expected = {
            "date",
            "sleep_start",
            "sleep_end",
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

    def test_sync_log_columns(self, in_memory_db: sqlite3.Connection) -> None:
        cursor = in_memory_db.execute("PRAGMA table_info(sync_log)")
        columns = {row["name"] for row in cursor.fetchall()}
        expected = {
            "id",
            "sync_type",
            "records_synced",
            "status",
            "error_message",
            "created_at",
        }
        assert expected.issubset(columns)

    def test_schema_version_set(self, in_memory_db: sqlite3.Connection) -> None:
        cursor = in_memory_db.execute("SELECT version FROM schema_version")
        row = cursor.fetchone()
        assert row is not None
        assert row["version"] == CURRENT_VERSION

    def test_idempotent_init(self, in_memory_db: sqlite3.Connection) -> None:
        """Calling init_db twice should not raise or duplicate data."""
        init_db(in_memory_db)
        cursor = in_memory_db.execute("SELECT COUNT(*) as cnt FROM schema_version")
        assert cursor.fetchone()["cnt"] == 1

    def test_activities_pk_is_activity_id(self, in_memory_db: sqlite3.Connection) -> None:
        cursor = in_memory_db.execute("PRAGMA table_info(activities)")
        pk_cols = [row["name"] for row in cursor.fetchall() if row["pk"] > 0]
        assert pk_cols == ["activity_id"]

    def test_biometrics_pk_is_date(self, in_memory_db: sqlite3.Connection) -> None:
        cursor = in_memory_db.execute("PRAGMA table_info(biometrics)")
        pk_cols = [row["name"] for row in cursor.fetchall() if row["pk"] > 0]
        assert pk_cols == ["date"]

    def test_sleep_pk_is_date(self, in_memory_db: sqlite3.Connection) -> None:
        cursor = in_memory_db.execute("PRAGMA table_info(sleep)")
        pk_cols = [row["name"] for row in cursor.fetchall() if row["pk"] > 0]
        assert pk_cols == ["date"]
