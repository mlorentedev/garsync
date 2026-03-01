"""Repository classes for garsync SQLite tables.

Each repository wraps a single table with upsert, query, and count operations.
Connection is injected — the caller manages lifecycle and transactions.
"""

import sqlite3
from typing import Any, Optional


class ActivityRepository:
    """CRUD operations for the activities table."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def upsert(self, row: dict[str, Any]) -> None:
        """Insert or update an activity by activity_id."""
        self._conn.execute(
            """
            INSERT INTO activities (
                activity_id, activity_name, activity_type, start_time,
                duration_seconds, distance_meters, average_heart_rate,
                max_heart_rate, calories, raw_data
            ) VALUES (
                :activity_id, :activity_name, :activity_type, :start_time,
                :duration_seconds, :distance_meters, :average_heart_rate,
                :max_heart_rate, :calories, :raw_data
            )
            ON CONFLICT(activity_id) DO UPDATE SET
                activity_name      = excluded.activity_name,
                activity_type      = excluded.activity_type,
                start_time         = excluded.start_time,
                duration_seconds   = excluded.duration_seconds,
                distance_meters    = excluded.distance_meters,
                average_heart_rate = excluded.average_heart_rate,
                max_heart_rate     = excluded.max_heart_rate,
                calories           = excluded.calories,
                raw_data           = excluded.raw_data,
                updated_at         = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
            """,
            row,
        )
        self._conn.commit()

    def upsert_batch(self, rows: list[dict[str, Any]]) -> None:
        """Upsert multiple activities in a single transaction."""
        for row in rows:
            self._conn.execute(
                """
                INSERT INTO activities (
                    activity_id, activity_name, activity_type, start_time,
                    duration_seconds, distance_meters, average_heart_rate,
                    max_heart_rate, calories, raw_data
                ) VALUES (
                    :activity_id, :activity_name, :activity_type, :start_time,
                    :duration_seconds, :distance_meters, :average_heart_rate,
                    :max_heart_rate, :calories, :raw_data
                )
                ON CONFLICT(activity_id) DO UPDATE SET
                    activity_name      = excluded.activity_name,
                    activity_type      = excluded.activity_type,
                    start_time         = excluded.start_time,
                    duration_seconds   = excluded.duration_seconds,
                    distance_meters    = excluded.distance_meters,
                    average_heart_rate = excluded.average_heart_rate,
                    max_heart_rate     = excluded.max_heart_rate,
                    calories           = excluded.calories,
                    raw_data           = excluded.raw_data,
                    updated_at         = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                """,
                row,
            )
        self._conn.commit()

    def get_by_id(self, activity_id: int) -> Optional[sqlite3.Row]:
        """Get a single activity by ID, or None."""
        cursor = self._conn.execute(
            "SELECT * FROM activities WHERE activity_id = ?", (activity_id,)
        )
        row: Optional[sqlite3.Row] = cursor.fetchone()
        return row

    def get_all(self, limit: int = 1000) -> list[sqlite3.Row]:
        """Get all activities, ordered by start_time DESC."""
        cursor = self._conn.execute(
            "SELECT * FROM activities ORDER BY start_time DESC LIMIT ?", (limit,)
        )
        result: list[sqlite3.Row] = cursor.fetchall()
        return result

    def count(self) -> int:
        """Return total number of stored activities."""
        cursor = self._conn.execute("SELECT COUNT(*) as cnt FROM activities")
        cnt: int = cursor.fetchone()["cnt"]
        return cnt

    def get_paginated(
        self,
        page: int = 1,
        limit: int = 20,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        activity_type: Optional[str] = None,
    ) -> tuple[list[sqlite3.Row], int]:
        """Get activities with pagination and optional filters.

        Returns (rows, total_count).
        """
        where_clauses: list[str] = []
        params: list[Any] = []

        if start_date:
            where_clauses.append("date(start_time) >= ?")
            params.append(start_date)
        if end_date:
            where_clauses.append("date(start_time) <= ?")
            params.append(end_date)
        if activity_type:
            where_clauses.append("activity_type = ?")
            params.append(activity_type)

        where_sql = ""
        if where_clauses:
            where_sql = "WHERE " + " AND ".join(where_clauses)

        count_cursor = self._conn.execute(
            f"SELECT COUNT(*) as cnt FROM activities {where_sql}",  # noqa: S608
            params,
        )
        total: int = count_cursor.fetchone()["cnt"]

        offset = (page - 1) * limit
        cursor = self._conn.execute(
            f"SELECT * FROM activities {where_sql} "  # noqa: S608
            "ORDER BY start_time DESC LIMIT ? OFFSET ?",
            [*params, limit, offset],
        )
        rows: list[sqlite3.Row] = cursor.fetchall()
        return rows, total

    def get_heatmap_data(
        self,
        year: int,
        activity_type: Optional[str] = None,
    ) -> list[sqlite3.Row]:
        """Get per-day activity aggregates for a calendar year."""
        params: list[Any] = [str(year)]
        type_filter = ""
        if activity_type:
            type_filter = "AND activity_type = ?"
            params.append(activity_type)

        cursor = self._conn.execute(
            f"""
            SELECT
                date(start_time) as date,
                COUNT(*) as activity_count,
                SUM(duration_seconds) as total_duration,
                SUM(calories) as total_calories
            FROM activities
            WHERE strftime('%Y', start_time) = ?
            {type_filter}
            GROUP BY date(start_time)
            ORDER BY date(start_time)
            """,  # noqa: S608
            params,
        )
        result: list[sqlite3.Row] = cursor.fetchall()
        return result

    def get_summary_stats(self, start_date: str, end_date: str) -> Optional[sqlite3.Row]:
        """Get aggregate stats for a date range."""
        cursor = self._conn.execute(
            """
            SELECT
                COUNT(*) as total_activities,
                COALESCE(SUM(duration_seconds), 0) as total_duration_seconds,
                COALESCE(SUM(distance_meters), 0) as total_distance_meters,
                COALESCE(SUM(calories), 0) as total_calories,
                AVG(duration_seconds) as avg_duration_seconds,
                AVG(distance_meters) as avg_distance_meters,
                AVG(average_heart_rate) as avg_heart_rate
            FROM activities
            WHERE date(start_time) >= ? AND date(start_time) <= ?
            """,
            (start_date, end_date),
        )
        row: Optional[sqlite3.Row] = cursor.fetchone()
        return row


class BiometricsRepository:
    """CRUD operations for the biometrics table."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def upsert(self, row: dict[str, Any]) -> None:
        """Insert or update biometrics by date."""
        self._conn.execute(
            """
            INSERT INTO biometrics (
                date, resting_heart_rate, hrv_balance,
                body_battery_highest, body_battery_lowest,
                stress_average, raw_data
            ) VALUES (
                :date, :resting_heart_rate, :hrv_balance,
                :body_battery_highest, :body_battery_lowest,
                :stress_average, :raw_data
            )
            ON CONFLICT(date) DO UPDATE SET
                resting_heart_rate   = excluded.resting_heart_rate,
                hrv_balance          = excluded.hrv_balance,
                body_battery_highest = excluded.body_battery_highest,
                body_battery_lowest  = excluded.body_battery_lowest,
                stress_average       = excluded.stress_average,
                raw_data             = excluded.raw_data,
                updated_at           = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
            """,
            row,
        )
        self._conn.commit()

    def get_by_date(self, date: str) -> Optional[sqlite3.Row]:
        """Get biometrics for a specific date (ISO format string)."""
        cursor = self._conn.execute("SELECT * FROM biometrics WHERE date = ?", (date,))
        row: Optional[sqlite3.Row] = cursor.fetchone()
        return row

    def get_latest_date(self) -> Optional[str]:
        """Return the most recent date with biometrics data, or None."""
        cursor = self._conn.execute("SELECT date FROM biometrics ORDER BY date DESC LIMIT 1")
        row = cursor.fetchone()
        result: Optional[str] = row["date"] if row else None
        return result

    def count(self) -> int:
        """Return total number of stored biometrics rows."""
        cursor = self._conn.execute("SELECT COUNT(*) as cnt FROM biometrics")
        cnt: int = cursor.fetchone()["cnt"]
        return cnt

    def get_by_date_range(self, start_date: str, end_date: str) -> list[sqlite3.Row]:
        """Get biometrics rows within a date range (inclusive)."""
        cursor = self._conn.execute(
            "SELECT * FROM biometrics WHERE date >= ? AND date <= ? ORDER BY date",
            (start_date, end_date),
        )
        result: list[sqlite3.Row] = cursor.fetchall()
        return result

    def get_avg_stats(self, start_date: str, end_date: str) -> Optional[sqlite3.Row]:
        """Get average biometrics for a date range."""
        cursor = self._conn.execute(
            """
            SELECT
                COUNT(*) as record_count,
                AVG(resting_heart_rate) as avg_resting_heart_rate,
                AVG(stress_average) as avg_stress,
                AVG(body_battery_highest) as avg_body_battery_high,
                AVG(body_battery_lowest) as avg_body_battery_low
            FROM biometrics
            WHERE date >= ? AND date <= ?
            """,
            (start_date, end_date),
        )
        row: Optional[sqlite3.Row] = cursor.fetchone()
        return row


class SleepRepository:
    """CRUD operations for the sleep table."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def upsert(self, row: dict[str, Any]) -> None:
        """Insert or update sleep data by date."""
        self._conn.execute(
            """
            INSERT INTO sleep (
                date, sleep_start, sleep_end, total_sleep_seconds,
                deep_sleep_seconds, light_sleep_seconds, rem_sleep_seconds,
                awake_sleep_seconds, sleep_score, raw_data
            ) VALUES (
                :date, :sleep_start, :sleep_end, :total_sleep_seconds,
                :deep_sleep_seconds, :light_sleep_seconds, :rem_sleep_seconds,
                :awake_sleep_seconds, :sleep_score, :raw_data
            )
            ON CONFLICT(date) DO UPDATE SET
                sleep_start         = excluded.sleep_start,
                sleep_end           = excluded.sleep_end,
                total_sleep_seconds = excluded.total_sleep_seconds,
                deep_sleep_seconds  = excluded.deep_sleep_seconds,
                light_sleep_seconds = excluded.light_sleep_seconds,
                rem_sleep_seconds   = excluded.rem_sleep_seconds,
                awake_sleep_seconds = excluded.awake_sleep_seconds,
                sleep_score         = excluded.sleep_score,
                raw_data            = excluded.raw_data,
                updated_at          = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
            """,
            row,
        )
        self._conn.commit()

    def get_by_date(self, date: str) -> Optional[sqlite3.Row]:
        """Get sleep data for a specific date (ISO format string)."""
        cursor = self._conn.execute("SELECT * FROM sleep WHERE date = ?", (date,))
        row: Optional[sqlite3.Row] = cursor.fetchone()
        return row

    def get_latest_date(self) -> Optional[str]:
        """Return the most recent date with sleep data, or None."""
        cursor = self._conn.execute("SELECT date FROM sleep ORDER BY date DESC LIMIT 1")
        row = cursor.fetchone()
        result: Optional[str] = row["date"] if row else None
        return result

    def count(self) -> int:
        """Return total number of stored sleep rows."""
        cursor = self._conn.execute("SELECT COUNT(*) as cnt FROM sleep")
        cnt: int = cursor.fetchone()["cnt"]
        return cnt

    def get_by_date_range(self, start_date: str, end_date: str) -> list[sqlite3.Row]:
        """Get sleep rows within a date range (inclusive)."""
        cursor = self._conn.execute(
            "SELECT * FROM sleep WHERE date >= ? AND date <= ? ORDER BY date",
            (start_date, end_date),
        )
        result: list[sqlite3.Row] = cursor.fetchall()
        return result

    def get_avg_stats(self, start_date: str, end_date: str) -> Optional[sqlite3.Row]:
        """Get average sleep stats for a date range."""
        cursor = self._conn.execute(
            """
            SELECT
                COUNT(*) as record_count,
                AVG(total_sleep_seconds) as avg_sleep_seconds,
                AVG(deep_sleep_seconds) as avg_deep_sleep_seconds,
                AVG(light_sleep_seconds) as avg_light_sleep_seconds,
                AVG(rem_sleep_seconds) as avg_rem_sleep_seconds,
                AVG(sleep_score) as avg_sleep_score
            FROM sleep
            WHERE date >= ? AND date <= ?
            """,
            (start_date, end_date),
        )
        row: Optional[sqlite3.Row] = cursor.fetchone()
        return row


class SyncLogRepository:
    """Append-only audit trail for sync operations."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def log(
        self,
        sync_type: str,
        records_synced: int,
        status: str = "success",
        error_message: Optional[str] = None,
    ) -> None:
        """Append a sync log entry."""
        self._conn.execute(
            """
            INSERT INTO sync_log (sync_type, records_synced, status, error_message)
            VALUES (?, ?, ?, ?)
            """,
            (sync_type, records_synced, status, error_message),
        )
        self._conn.commit()

    def get_latest(self, sync_type: Optional[str] = None) -> Optional[sqlite3.Row]:
        """Get the most recent sync log entry, optionally filtered by type."""
        if sync_type:
            cursor = self._conn.execute(
                "SELECT * FROM sync_log WHERE sync_type = ? ORDER BY id DESC LIMIT 1",
                (sync_type,),
            )
        else:
            cursor = self._conn.execute("SELECT * FROM sync_log ORDER BY id DESC LIMIT 1")
        row: Optional[sqlite3.Row] = cursor.fetchone()
        return row

    def get_all(self, limit: int = 100) -> list[sqlite3.Row]:
        """Get recent sync log entries."""
        cursor = self._conn.execute("SELECT * FROM sync_log ORDER BY id DESC LIMIT ?", (limit,))
        result: list[sqlite3.Row] = cursor.fetchall()
        return result

    def count(self) -> int:
        """Return total number of sync log entries."""
        cursor = self._conn.execute("SELECT COUNT(*) as cnt FROM sync_log")
        cnt: int = cursor.fetchone()["cnt"]
        return cnt
