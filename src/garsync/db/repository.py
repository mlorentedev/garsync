"""Repository classes for garsync SQLite tables.

Each repository wraps a single table with upsert, query, and count operations.
Connection is injected — the caller manages lifecycle and transactions.
"""

import sqlite3
from typing import Any

#: Garmin's own derived numbers. Re-read from the retained payload rather than refetched, and NULL
#: wherever the payload did not carry them — `activityTrainingLoad` is absent from most list-endpoint
#: responses, so the gap is a property of the source, not of the migration.
DERIVED_COLUMNS = ("training_load", "aerobic_te", "anaerobic_te", "normalized_power", "avg_power")

#: One statement for both the single and the batch path: two copies of an upsert is two places for a
#: new column to be forgotten.
_ACTIVITY_UPSERT = """
    INSERT INTO activities (
        activity_id, source, source_id, activity_name, activity_type, start_time,
        tz_offset_minutes, duration_seconds, distance_meters, average_heart_rate,
        max_heart_rate, calories, training_load, aerobic_te, anaerobic_te,
        normalized_power, avg_power, raw_data
    ) VALUES (
        :activity_id, :source, :source_id, :activity_name, :activity_type, :start_time,
        :tz_offset_minutes, :duration_seconds, :distance_meters, :average_heart_rate,
        :max_heart_rate, :calories, :training_load, :aerobic_te, :anaerobic_te,
        :normalized_power, :avg_power, :raw_data
    )
    ON CONFLICT(source, source_id) DO UPDATE SET
        activity_name      = excluded.activity_name,
        activity_type      = excluded.activity_type,
        start_time         = excluded.start_time,
        tz_offset_minutes  = excluded.tz_offset_minutes,
        duration_seconds   = excluded.duration_seconds,
        distance_meters    = excluded.distance_meters,
        average_heart_rate = excluded.average_heart_rate,
        max_heart_rate     = excluded.max_heart_rate,
        calories           = excluded.calories,
        training_load      = excluded.training_load,
        aerobic_te         = excluded.aerobic_te,
        anaerobic_te       = excluded.anaerobic_te,
        normalized_power   = excluded.normalized_power,
        avg_power          = excluded.avg_power,
        raw_data           = excluded.raw_data,
        updated_at         = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
"""


class ActivityRepository:
    """CRUD operations for the activities table."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def upsert(self, row: dict[str, Any]) -> None:
        """Insert or update an activity, keyed on its (source, source_id) natural key."""
        self._conn.execute(_ACTIVITY_UPSERT, row)
        self._conn.commit()

    def derived_gap_counts(self) -> dict[str, int]:
        """How many activities the payload did not supply each derived column for.

        Reported rather than estimated: the metric layer inherits a measured gap instead of
        discovering, months later, that its cross-check covers almost no history.
        """
        total = self.count()
        return {
            column: total
            - self._conn.execute(
                f"SELECT COUNT(*) AS c FROM activities WHERE {column} IS NOT NULL"
            ).fetchone()["c"]
            for column in DERIVED_COLUMNS
        }

    def upsert_batch(self, rows: list[dict[str, Any]]) -> None:
        """Upsert multiple activities in a single transaction."""
        for row in rows:
            self._conn.execute(_ACTIVITY_UPSERT, row)
        self._conn.commit()

    def get_by_id(self, activity_id: int) -> sqlite3.Row | None:
        """Get a single activity by ID, or None."""
        cursor = self._conn.execute(
            "SELECT * FROM activities WHERE activity_id = ?", (activity_id,)
        )
        row: sqlite3.Row | None = cursor.fetchone()
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
        start_date: str | None = None,
        end_date: str | None = None,
        activity_type: str | None = None,
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
            f"SELECT COUNT(*) as cnt FROM activities {where_sql}",
            params,
        )
        total: int = count_cursor.fetchone()["cnt"]

        offset = (page - 1) * limit
        cursor = self._conn.execute(
            f"SELECT * FROM activities {where_sql} ORDER BY start_time DESC LIMIT ? OFFSET ?",
            [*params, limit, offset],
        )
        rows: list[sqlite3.Row] = cursor.fetchall()
        return rows, total

    def get_heatmap_data(
        self,
        year: int,
        activity_type: str | None = None,
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
            """,
            params,
        )
        result: list[sqlite3.Row] = cursor.fetchall()
        return result

    def get_summary_stats(self, start_date: str, end_date: str) -> sqlite3.Row | None:
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
        row: sqlite3.Row | None = cursor.fetchone()
        return row


class BiometricsRepository:
    """CRUD operations for the daily_metrics table (v1's `biometrics`)."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def upsert(self, row: dict[str, Any]) -> None:
        """Insert or update daily metrics by date."""
        self._conn.execute(
            """
            INSERT INTO daily_metrics (
                date, resting_heart_rate, hrv_baseline_status,
                body_battery_highest, body_battery_lowest,
                stress_average, raw_data
            ) VALUES (
                :date, :resting_heart_rate, :hrv_baseline_status,
                :body_battery_highest, :body_battery_lowest,
                :stress_average, :raw_data
            )
            ON CONFLICT(date) DO UPDATE SET
                resting_heart_rate   = excluded.resting_heart_rate,
                hrv_baseline_status  = excluded.hrv_baseline_status,
                body_battery_highest = excluded.body_battery_highest,
                body_battery_lowest  = excluded.body_battery_lowest,
                stress_average       = excluded.stress_average,
                raw_data             = excluded.raw_data,
                updated_at           = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
            """,
            row,
        )
        self._conn.commit()

    def get_by_date(self, date: str) -> sqlite3.Row | None:
        """Get daily metrics for a specific date (ISO format string).

        `hrv_baseline_status` is aliased back to the name the models and the API use. The column was
        renamed because the value is a status word rather than a balance number — a storage decision;
        renaming the wire contract alongside it is not one this PR is entitled to make.
        """
        cursor = self._conn.execute(
            "SELECT *, hrv_baseline_status AS hrv_balance FROM daily_metrics WHERE date = ?",
            (date,),
        )
        row: sqlite3.Row | None = cursor.fetchone()
        return row

    def get_latest_date(self) -> str | None:
        """Return the most recent date with daily metrics, or None."""
        cursor = self._conn.execute("SELECT date FROM daily_metrics ORDER BY date DESC LIMIT 1")
        row = cursor.fetchone()
        result: str | None = row["date"] if row else None
        return result

    def count(self) -> int:
        """Return total number of stored daily metric rows."""
        cursor = self._conn.execute("SELECT COUNT(*) as cnt FROM daily_metrics")
        cnt: int = cursor.fetchone()["cnt"]
        return cnt

    def get_by_date_range(self, start_date: str, end_date: str) -> list[sqlite3.Row]:
        """Get daily metric rows within a date range (inclusive)."""
        cursor = self._conn.execute(
            "SELECT *, hrv_baseline_status AS hrv_balance FROM daily_metrics "
            "WHERE date >= ? AND date <= ? ORDER BY date",
            (start_date, end_date),
        )
        result: list[sqlite3.Row] = cursor.fetchall()
        return result

    def get_avg_stats(self, start_date: str, end_date: str) -> sqlite3.Row | None:
        """Get average daily metrics for a date range."""
        cursor = self._conn.execute(
            """
            SELECT
                COUNT(*) as record_count,
                AVG(resting_heart_rate) as avg_resting_heart_rate,
                AVG(stress_average) as avg_stress,
                AVG(body_battery_highest) as avg_body_battery_high,
                AVG(body_battery_lowest) as avg_body_battery_low
            FROM daily_metrics
            WHERE date >= ? AND date <= ?
            """,
            (start_date, end_date),
        )
        row: sqlite3.Row | None = cursor.fetchone()
        return row


class SleepRepository:
    """CRUD operations for the sleep_sessions table (v1's `sleep`)."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def upsert(self, row: dict[str, Any]) -> None:
        """Insert or update sleep data by date."""
        self._conn.execute(
            """
            INSERT INTO sleep_sessions (
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

    def get_by_date(self, date: str) -> sqlite3.Row | None:
        """Get sleep data for a specific date (ISO format string)."""
        cursor = self._conn.execute("SELECT * FROM sleep_sessions WHERE date = ?", (date,))
        row: sqlite3.Row | None = cursor.fetchone()
        return row

    def get_latest_date(self) -> str | None:
        """Return the most recent date with sleep data, or None."""
        cursor = self._conn.execute("SELECT date FROM sleep_sessions ORDER BY date DESC LIMIT 1")
        row = cursor.fetchone()
        result: str | None = row["date"] if row else None
        return result

    def count(self) -> int:
        """Return total number of stored sleep rows."""
        cursor = self._conn.execute("SELECT COUNT(*) as cnt FROM sleep_sessions")
        cnt: int = cursor.fetchone()["cnt"]
        return cnt

    def get_by_date_range(self, start_date: str, end_date: str) -> list[sqlite3.Row]:
        """Get sleep rows within a date range (inclusive)."""
        cursor = self._conn.execute(
            "SELECT * FROM sleep_sessions WHERE date >= ? AND date <= ? ORDER BY date",
            (start_date, end_date),
        )
        result: list[sqlite3.Row] = cursor.fetchall()
        return result

    def get_avg_stats(self, start_date: str, end_date: str) -> sqlite3.Row | None:
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
            FROM sleep_sessions
            WHERE date >= ? AND date <= ?
            """,
            (start_date, end_date),
        )
        row: sqlite3.Row | None = cursor.fetchone()
        return row


class IngestRunRepository:
    """Append-only audit trail for ingest runs.

    v1's `sync_log` held one row per data class per run. The v2 table separates two axes that were
    always distinct: `source` is *where the data came from*, `sync_type` is *which class of data the
    run covered*. Rows copied out of v1 carry `source='legacy'` — the old table never recorded
    provenance — and NULL cursors, because it recorded none of those either. The legacy table stays in
    place and inert until SUB-002 owns the cursor contract.
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def log(
        self,
        sync_type: str,
        rows_upserted: int,
        status: str = "success",
        error_message: str | None = None,
        source: str = "garmin",
    ) -> None:
        """Append an ingest run entry."""
        self._conn.execute(
            """
            INSERT INTO ingest_run (source, sync_type, rows_upserted, status, error_message)
            VALUES (?, ?, ?, ?, ?)
            """,
            (source, sync_type, rows_upserted, status, error_message),
        )
        self._conn.commit()

    def get_latest(self, sync_type: str | None = None) -> sqlite3.Row | None:
        """Get the most recent ingest run, optionally filtered by data class."""
        if sync_type:
            cursor = self._conn.execute(
                "SELECT * FROM ingest_run WHERE sync_type = ? ORDER BY id DESC LIMIT 1",
                (sync_type,),
            )
        else:
            cursor = self._conn.execute("SELECT * FROM ingest_run ORDER BY id DESC LIMIT 1")
        row: sqlite3.Row | None = cursor.fetchone()
        return row

    def get_all(self, limit: int = 100) -> list[sqlite3.Row]:
        """Get recent ingest runs."""
        cursor = self._conn.execute("SELECT * FROM ingest_run ORDER BY id DESC LIMIT ?", (limit,))
        result: list[sqlite3.Row] = cursor.fetchall()
        return result

    def count(self) -> int:
        """Return total number of ingest runs."""
        cursor = self._conn.execute("SELECT COUNT(*) as cnt FROM ingest_run")
        cnt: int = cursor.fetchone()["cnt"]
        return cnt
