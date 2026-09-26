"""Repository classes for garsync SQLite tables.

Each repository wraps a single table with upsert, query, and count operations.

Connection is injected, and so is the transaction: a write here **joins** whatever unit of work the
caller opened (`db.connection.transaction`) and never commits it. A per-row commit is what turned a run
into a sequence of independent commits once the run began opening its own transaction (lesson 028);
a write outside any transaction simply autocommits, because the connection runs with
`isolation_level=None`.
"""

import sqlite3
from datetime import date, timedelta
from typing import Any, Final

from garsync.db.connection import transaction
from garsync.ingest.window import CLASSES, Granularity

#: Garmin's own derived numbers. Re-read from the retained payload rather than refetched, and NULL
#: wherever the payload did not carry them — `activityTrainingLoad` is absent from most list-endpoint
#: responses, so the gap is a property of the source, not of the migration.
DERIVED_COLUMNS = ("training_load", "aerobic_te", "anaerobic_te", "normalized_power", "avg_power")

#: Columns whose **absence must not erase a known value**, per table: the fields a class's request may
#: legitimately not supply. Getting this wrong is a silent data loss, so each set is a decision:
#:
#: * `activities` — the five derived numbers, by measurement: `activityTrainingLoad` is absent from 98 of
#:   100 list payloads. The core summary fields (calories, distance, heart rate) are always carried by
#:   this request, so a `None` there is Garmin withdrawing a value and it lands.
#: * the daily classes — **every** payload column, because one of the four biometrics endpoints can come
#:   back empty and a night's sleep can simply not be published yet; a re-pull of the 14-day window would
#:   otherwise null a day that already had values (ADR-008 §5 amendment, SUB-002 §Q1).
CARRY_ON_ABSENCE: dict[str, tuple[str, ...]] = {
    "activities": DERIVED_COLUMNS,
    "daily_metrics": (
        "resting_heart_rate",
        "hrv_baseline_status",
        "body_battery_highest",
        "body_battery_lowest",
        "stress_average",
        "raw_data",
    ),
    "sleep_sessions": (
        "sleep_start",
        "sleep_end",
        "total_sleep_seconds",
        "deep_sleep_seconds",
        "light_sleep_seconds",
        "rem_sleep_seconds",
        "awake_sleep_seconds",
        "sleep_score",
        "raw_data",
    ),
}

#: The columns each upsert takes from a row dict, in the order the table declares them. The key columns
#: are listed separately because they are matched, never updated.
ACTIVITY_PAYLOAD_COLUMNS = (
    "activity_name",
    "activity_type",
    "start_time",
    "tz_offset_minutes",
    "duration_seconds",
    "distance_meters",
    "average_heart_rate",
    "max_heart_rate",
    "calories",
    *DERIVED_COLUMNS,
    "raw_data",
)
DAILY_METRICS_PAYLOAD_COLUMNS = (
    "resting_heart_rate",
    "hrv_baseline_status",
    "body_battery_highest",
    "body_battery_lowest",
    "stress_average",
    "raw_data",
)
SLEEP_PAYLOAD_COLUMNS = (
    "sleep_start",
    "sleep_end",
    "total_sleep_seconds",
    "deep_sleep_seconds",
    "light_sleep_seconds",
    "rem_sleep_seconds",
    "awake_sleep_seconds",
    "sleep_score",
    "raw_data",
)


#: Which storage table holds a coverage class's day-keyed rows. The two classes missing from it are
#: missing on purpose: `activities` is minute-resolved and claims no cursor (its fetch is not
#: window-complete until SUB-003), and `stress` is windowed but has no storage yet. Asking either is
#: refused in `_day_table`, never answered with an empty list — an empty answer reads as "we looked and
#: the body produced nothing", which is a claim about the body, not about the code.
DAY_KEYED_TABLES: Final[dict[str, str]] = {
    "daily_metrics": "daily_metrics",
    "sleep": "sleep_sessions",
}


def _day_table(sync_type: str) -> str:
    """The table a coverage class's day-keyed rows live in, or the reason the question is refused.

    Refusing loudly is the point. An empty list would be a true-looking answer to a question the schema
    cannot support, and "the ledger asked about every day and found nothing" is the most confident wrong
    sentence this subsystem can produce.
    """
    spec = CLASSES.get(sync_type)
    if spec is None:
        raise ValueError(f"{sync_type!r} is not a coverage class ({', '.join(sorted(CLASSES))})")
    if spec.granularity is not Granularity.DAY or not spec.claims_cursor:
        raise ValueError(
            f"{sync_type} is resolved by minute, not by day: its coverage is not window-complete until "
            "SUB-003 lands the date-range fetch (Q4)"
        )
    table = DAY_KEYED_TABLES.get(sync_type)
    if table is None:
        raise ValueError(f"{sync_type} is windowed but has no day-keyed table to check yet")
    return table


def _days_between(before: str, after: str, start: date, end: date) -> set[str]:
    """The days a run's covered window contributes to the question, clamped to `[start, end]`.

    The clamp is the part that matters: a run that covered a month answers a question about one week with
    one week of days, not with the month. `max(..., 0)` rather than an `if`, because the query already
    filters to overlapping windows — an uncovered branch here would be an assertion that the SQL can be
    bypassed.
    """
    first = max(date.fromisoformat(before), start)
    last = min(date.fromisoformat(after), end)
    span = max((last - first).days + 1, 0)
    return {(first + timedelta(days=offset)).isoformat() for offset in range(span)}


def _incoming(column: str, table: str, carried: tuple[str, ...]) -> str:
    """The value a column would take: the incoming one, or the stored one when absence must not win."""
    if column in carried:
        return f"COALESCE(excluded.{column}, {table}.{column})"
    return f"excluded.{column}"


def _guarded_upsert(
    table: str,
    key_columns: tuple[str, ...],
    conflict_on: tuple[str, ...],
    payload_columns: tuple[str, ...],
) -> str:
    """`INSERT … ON CONFLICT … DO UPDATE SET … WHERE …`, built from one column list.

    The `SET` clause and the change predicate are generated from the same list on purpose: a predicate
    maintained by hand is a column list that drifts from the `SET` clause the first time a column is
    added, and the drift is silent (lesson 026). The predicate uses `IS NOT` rather than `!=` so that
    `NULL` compares — a column that is `NULL` on both sides is not a change — which is what makes an
    identical re-pull execute **no UPDATE at all**, so `updated_at` cannot move either (ADR-008 §5).
    """
    carried = CARRY_ON_ABSENCE[table]
    columns = (*key_columns, *payload_columns)
    assignments = ", ".join(
        f"{column} = {_incoming(column, table, carried)}" for column in payload_columns
    )
    predicate = " OR ".join(
        f"{_incoming(column, table, carried)} IS NOT {table}.{column}" for column in payload_columns
    )
    return (
        f"INSERT INTO {table} ({', '.join(columns)})\n"
        f"VALUES ({', '.join(':' + column for column in columns)})\n"
        f"ON CONFLICT({', '.join(conflict_on)}) DO UPDATE SET\n"
        f"    {assignments},\n"
        f"    updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')\n"
        f"WHERE {predicate}\n"
    )


#: One statement per table for both the single and the batch path: two copies of an upsert is two places
#: for a new column to be forgotten.
_ACTIVITY_UPSERT = _guarded_upsert(
    "activities",
    ("activity_id", "source", "source_id"),
    ("source", "source_id"),
    ACTIVITY_PAYLOAD_COLUMNS,
)
_DAILY_METRICS_UPSERT = _guarded_upsert(
    "daily_metrics", ("date",), ("date",), DAILY_METRICS_PAYLOAD_COLUMNS
)
_SLEEP_UPSERT = _guarded_upsert("sleep_sessions", ("date",), ("date",), SLEEP_PAYLOAD_COLUMNS)


class ActivityRepository:
    """CRUD operations for the activities table."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def upsert(self, row: dict[str, Any]) -> int:
        """Insert or update an activity, keyed on its (source, source_id) natural key.

        The write joins whatever transaction the caller owns; committing here would end that
        transaction and publish a half-written run (lesson 028).

        Returns how many rows the statement actually changed — 0 when the guard found nothing new,
        which is what the ledger records as `rows_upserted` (ADR-008 §5).
        """
        return self._conn.execute(_ACTIVITY_UPSERT, row).rowcount

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

    def upsert_batch(self, rows: list[dict[str, Any]]) -> int:
        """Upsert multiple activities as one unit of work, joining the caller's if there is one.

        Returns the number of rows that actually changed, summed over the batch.
        """
        with transaction(self._conn):
            return sum(self._conn.execute(_ACTIVITY_UPSERT, row).rowcount for row in rows)

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

    def upsert(self, row: dict[str, Any]) -> int:
        """Insert or update daily metrics by date, returning the rows actually changed."""
        return self._conn.execute(_DAILY_METRICS_UPSERT, row).rowcount

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

    def upsert(self, row: dict[str, Any]) -> int:
        """Insert or update sleep data by date, returning the rows actually changed."""
        return self._conn.execute(_SLEEP_UPSERT, row).rowcount

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
        *,
        rows_fetched: int = 0,
        started_at: str | None = None,
        cursor_before: str | None = None,
        cursor_after: str | None = None,
    ) -> None:
        """Append an ingest run entry (joins the caller's transaction; see ActivityRepository.upsert).

        The two counts are not interchangeable and the row records both (ADR-008 §5, AC7):
        `rows_fetched` is what the adapter returned, `rows_upserted` is how many of them the guarded
        upsert actually changed — so a re-pull of a quiet window reads `rows_fetched=14,
        rows_upserted=0`, and "asked, nothing yet" reads `rows_fetched=0`. Defaults keep today's
        callers compiling; a caller that leaves them at 0 claims nothing arrived, so the run passes
        them explicitly.

        `started_at` is the instant the run captured *before* it fetched, never the insert instant
        (`created_at` is that, and it is the finish). `cursor_before`/`cursor_after` are the window
        the run covered — the watermark is read back from the ledger by `id`, not by timestamp, which
        is what makes a late-arriving row with a smaller window the authoritative one.
        """
        self._conn.execute(
            """
            INSERT INTO ingest_run (
                source, sync_type, rows_upserted, rows_fetched, started_at,
                status, error_message, cursor_before, cursor_after
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source,
                sync_type,
                rows_upserted,
                rows_fetched,
                started_at,
                status,
                error_message,
                cursor_before,
                cursor_after,
            ),
        )

    def last_cursor(self, source: str, sync_type: str) -> str | None:
        """The class's coverage watermark: `cursor_after` of its newest **successful** ledger row.

        Three rules the naive query gets wrong, each asserted in `TestCursors`:

        * ordered by `id`, never `created_at` — ADR-008 §8 measured two logical states sharing one
          timestamp, so an ordering that reads it is a coin flip;
        * filtered on `status = 'success'` — an error row that carries a cursor would claim coverage
          for a run whose data was rolled back out of the database;
        * keyed on `(source, sync_type)` — the axis D1 defines, so a scale's watermark is never read as
          Garmin's, and a night's never as a day's.

        `None` means no successful run has ever covered this class — not the same fact as a cursor at
        the epoch: the caller's trailing floor decides where the first run starts.
        """
        row = self._conn.execute(
            "SELECT cursor_after FROM ingest_run "
            "WHERE source = ? AND sync_type = ? AND status = 'success' "
            "ORDER BY id DESC LIMIT 1",
            (source, sync_type),
        ).fetchone()
        if row is None:
            return None
        cursor: str | None = row["cursor_after"]
        return cursor

    def covered_days(
        self, sync_type: str, start: date, end: date, source: str = "garmin"
    ) -> set[str]:
        """Which days in `[start, end]` a **successful** run has covered. Empty is not the same as none.

        SC-02(3)'s first axis: a day outside every window was never asked about, which is a fact about the
        runner, while the two questions below are facts about the data. Only `success` rows count (a run
        whose data rolled back covered nothing), and `source='legacy'` rows cannot count even if they grew
        cursors — v1 recorded no window, so it can support no claim about one (decision 9).
        """
        days: set[str] = set()
        for row in self._covering_runs(sync_type, start, end, source):
            days |= _days_between(row["cursor_before"], row["cursor_after"], start, end)
        return days

    def days_not_uploaded_yet(
        self, sync_type: str, start: date, end: date, source: str = "garmin"
    ) -> list[str]:
        """Covered days the class table is silent about, where every covering run fetched zero rows.

        "We asked, nothing had arrived." SC-02(3)'s late-upload state: expected, not a failure, and the
        reason the staleness alert must sit above the normal lateness rather than at zero.
        """
        return self._absent_days(sync_type, start, end, source)[0]

    def days_with_no_data(
        self, sync_type: str, start: date, end: date, source: str = "garmin"
    ) -> list[str]:
        """Covered days with no row, inside a window that **did** return rows for other days.

        "There is no data for that day." A rest day, a night the watch was not worn: also expected, but a
        different sentence in the digest, and it is only distinguishable from the state above because AC7
        made `rows_fetched` count what arrived rather than what the loop wrote.
        """
        return self._absent_days(sync_type, start, end, source)[1]

    def _absent_days(
        self, sync_type: str, start: date, end: date, source: str
    ) -> tuple[list[str], list[str]]:
        table = _day_table(sync_type)
        arrived: dict[str, bool] = {}
        for row in self._covering_runs(sync_type, start, end, source):
            anything = bool(row["rows_fetched"])
            for day in _days_between(row["cursor_before"], row["cursor_after"], start, end):
                arrived[day] = arrived.get(day, False) or anything
        stored = {
            row["date"]
            for row in self._conn.execute(
                f"SELECT date FROM {table} WHERE date BETWEEN ? AND ?",
                (start.isoformat(), end.isoformat()),
            )
        }
        absent = sorted(day for day in arrived if day not in stored)
        return (
            [day for day in absent if not arrived[day]],
            [day for day in absent if arrived[day]],
        )

    def _covering_runs(
        self, sync_type: str, start: date, end: date, source: str
    ) -> list[sqlite3.Row]:
        """Successful rows whose window touches `[start, end]`, newest shape unchanged.

        The comparison is lexical and safe because the cursors are ISO dates — the same reason `utc_z`
        exists for timestamps. `start <= cursor_after and end >= cursor_before` is the interval overlap,
        so a run that closed before the question began is excluded without a date parse in SQL.
        """
        _day_table(sync_type)  # refuse the classes that cannot answer a day question
        return list(
            self._conn.execute(
                """
                SELECT cursor_before, cursor_after, rows_fetched
                FROM ingest_run
                WHERE source = ? AND sync_type = ? AND status = 'success'
                  AND cursor_before IS NOT NULL AND cursor_after IS NOT NULL
                  AND cursor_after >= ? AND cursor_before <= ?
                ORDER BY id
                """,
                (source, sync_type, start.isoformat(), end.isoformat()),
            ).fetchall()
        )

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
