"""Core synchronization pipeline logic."""

import logging
import sqlite3
from collections.abc import Callable
from datetime import UTC, date, datetime
from typing import Any

from garsync.client import GarminClient
from garsync.db import (
    ActivityRepository,
    BiometricsRepository,
    IngestRunRepository,
    SleepRepository,
)
from garsync.db.connection import transaction
from garsync.ingest.payload import canonical_json
from garsync.ingest.window import CLASSES, Window, resolve_window
from garsync.models import DailyBiometrics, NormalizedActivity, SleepData
from garsync.timeutil import offset_minutes, parse_garmin_timestamp, utc_z

logger = logging.getLogger(__name__)

#: Provenance written on every row this process ingests. A second source (the scale, SCALE-001) gets
#: its own value here rather than a second code path.
GARMIN = "garmin"


def _utc_now() -> datetime:
    """The default clock. Injectable, because a run's window is derived from this instant — and the
    instant a run *began* is what `started_at` records."""
    return datetime.now(UTC)


def _tally(results: dict[str, int], key: str, outcome: int | None) -> None:
    """Fold one run's answer into the summary: `None` is a failed run, a number is what arrived.

    The two axes stay separate on the way out exactly as they are separate in the ledger: a run that
    fetched nothing and a run that failed are different facts, and `errors` counts only the second.
    """
    if outcome is None:
        results["errors"] += 1
    else:
        results[key] += outcome


def activity_to_row(activity: NormalizedActivity) -> dict[str, Any]:
    """Convert activity model to DB row dict.

    UTC comes from the payload, not from the model's `start_time` — that field is Garmin's
    *local* spelling, and storing it as if it were absolute is the defect this migration exists to
    fix. `start_time` is only the fallback for a payload that does not carry a GMT value, in which
    case `tz_offset_minutes` is None rather than guessed.
    """
    raw = activity.raw_data
    gmt = parse_garmin_timestamp(raw.get("startTimeGMT"))
    start_time: str | None = None
    if gmt is not None:
        start_time = utc_z(gmt)
    elif activity.start_time is not None:
        start_time = utc_z(activity.start_time)
    return {
        "activity_id": activity.activity_id,
        "source": GARMIN,
        "source_id": str(activity.activity_id),
        "activity_name": activity.activity_name,
        "activity_type": activity.activity_type,
        "start_time": start_time,
        "tz_offset_minutes": offset_minutes(raw.get("startTimeLocal"), raw.get("startTimeGMT")),
        "duration_seconds": activity.duration_seconds,
        "distance_meters": activity.distance_meters,
        "average_heart_rate": activity.average_heart_rate,
        "max_heart_rate": activity.max_heart_rate,
        "calories": activity.calories,
        # Garmin's own derived numbers, kept verbatim as a cross-check. NULL when the list endpoint
        # did not carry them, which for `activityTrainingLoad` is the common case.
        "training_load": raw.get("activityTrainingLoad"),
        "aerobic_te": raw.get("aerobicTrainingEffect"),
        "anaerobic_te": raw.get("anaerobicTrainingEffect"),
        "normalized_power": raw.get("normPower"),
        "avg_power": raw.get("avgPower"),
        "raw_data": canonical_json(raw),
    }


def biometrics_to_row(bio: DailyBiometrics) -> dict[str, Any]:
    """Convert biometrics model to DB row dict — the column is `hrv_baseline_status` in v2."""
    return {
        "date": bio.date.isoformat(),
        "resting_heart_rate": bio.resting_heart_rate,
        "hrv_baseline_status": bio.hrv_balance,
        "body_battery_highest": bio.body_battery_highest,
        "body_battery_lowest": bio.body_battery_lowest,
        "stress_average": bio.stress_average,
        "raw_data": canonical_json(bio.raw_data),
    }


def sleep_to_row(sleep: SleepData) -> dict[str, Any]:
    """Convert sleep model to DB row dict."""
    return {
        "date": sleep.date.isoformat(),
        # v1 wrote `isoformat()`, whose aware UTC form is `+00:00`. One column, one spelling.
        "sleep_start": utc_z(sleep.sleep_start) if sleep.sleep_start else None,
        "sleep_end": utc_z(sleep.sleep_end) if sleep.sleep_end else None,
        "total_sleep_seconds": sleep.total_sleep_seconds,
        "deep_sleep_seconds": sleep.deep_sleep_seconds,
        "light_sleep_seconds": sleep.light_sleep_seconds,
        "rem_sleep_seconds": sleep.rem_sleep_seconds,
        "awake_sleep_seconds": sleep.awake_sleep_seconds,
        "sleep_score": sleep.sleep_score,
        "raw_data": canonical_json(sleep.raw_data),
    }


class SyncService:
    """Orchestrates the synchronization process between Garmin and SQLite."""

    def __init__(
        self,
        client: GarminClient,
        db_conn: sqlite3.Connection,
        *,
        now: Callable[[], datetime] = _utc_now,
    ) -> None:
        self.client = client
        self.db_conn = db_conn
        #: The run's clock, injected. A run derives its window from `now` and records that same instant
        #: as `started_at`, so the two cannot disagree — and a test can pin a window without patching a
        #: module's globals.
        self._now = now
        self.activity_repo = ActivityRepository(db_conn)
        self.biometrics_repo = BiometricsRepository(db_conn)
        self.sleep_repo = SleepRepository(db_conn)
        self.ingest_run_repo = IngestRunRepository(db_conn)

    def sync_range(self, dates: list[date], activities_limit: int = 100) -> dict[str, int]:
        """Run one ingest per data class, and report what each one saw.

        Three runs, three ledger rows — the grain D1 ratifies: `(source, sync_type)` is the unit, not
        the calendar day. `dates` says how far back a run may reach (its **floor**); the window it
        actually covers comes from that floor and the class's watermark. The caller's list of days is
        deliberately not the source of coverage, because "the last record I saw" is the cursor this
        spec exists to replace. A stale watermark therefore moves the left edge earlier and the gap
        closes one floor-sized chunk per run (`resolve_window`'s `end_effective`), which bounds the
        daily run at ≈71 calls instead of letting a backfill open with a year of requests.
        """
        results: dict[str, int] = {"activities": 0, "biometrics": 0, "sleep": 0, "errors": 0}
        trailing_days = max(len(dates), 1)

        _tally(results, "activities", self._run_activities(trailing_days, activities_limit))
        _tally(
            results,
            "biometrics",
            self._run_daily(
                "daily_metrics",
                trailing_days,
                self.client.fetch_biometrics,
                biometrics_to_row,
                self.biometrics_repo.upsert,
            ),
        )
        _tally(
            results,
            "sleep",
            self._run_daily(
                "sleep",
                trailing_days,
                self.client.fetch_sleep,
                sleep_to_row,
                self.sleep_repo.upsert,
            ),
        )
        return results

    def _run_activities(self, trailing_days: int, limit: int) -> int | None:
        """The activities run, whose fetch is `limit`-based — which is why it claims no cursor (Q4)."""
        return self._run(
            "activities",
            trailing_days,
            lambda _window: [
                activity_to_row(activity) for activity in self.client.fetch_activities(limit=limit)
            ],
            self.activity_repo.upsert,
        )

    def _run_daily(
        self,
        sync_type: str,
        trailing_days: int,
        fetch_day: Callable[[date], Any],
        to_row: Callable[[Any], dict[str, Any]],
        upsert: Callable[[dict[str, Any]], int],
    ) -> int | None:
        """One daily class: the window's days are fetched one per unit and written as one run."""
        return self._run(
            sync_type,
            trailing_days,
            lambda window: [to_row(fetch_day(day)) for day in window.days()],
            upsert,
        )

    def _run(
        self,
        sync_type: str,
        trailing_days: int,
        fetch: Callable[[Window], list[dict[str, Any]]],
        upsert: Callable[[dict[str, Any]], int],
    ) -> int | None:
        """One run of one class: window, fetch, transaction, ledger row — in that order.

        The order *is* the contract, and each step is a separate assertion:

        * the window is resolved **before** the fetch, so a run can never claim coverage past the
          instant it started with (D1, and the reason `started_at` is the same instant);
        * the fetch runs with **no transaction open** (AC5): `BEGIN IMMEDIATE` takes the write lock for
          the whole daily window's ≈71 HTTP calls if it is opened first;
        * every write and the `success` row share **one commit** (AC1), so a reader sees the data and
          its ledger row together or not at all;
        * a failure writes its `error` row afterwards, in its own unit, and never a cursor.
        """
        instant = self._now()
        started_at = utc_z(instant)
        window = resolve_window(
            sync_type,
            instant,
            self.ingest_run_repo.last_cursor(GARMIN, sync_type),
            trailing_days=trailing_days,
        )
        try:
            rows = fetch(window)
        except Exception as error:  # noqa: BLE001
            logger.error(f"{sync_type}: the fetch failed, so nothing was written: {error}")
            self._record_failure(sync_type, started_at, 0, error)
            return None
        try:
            with transaction(self.db_conn):
                changed = sum(upsert(row) for row in rows)
                self._record_success(sync_type, window, started_at, len(rows), changed)
        except Exception as error:  # noqa: BLE001
            logger.error(f"{sync_type}: the run rolled back: {error}")
            self._record_failure(sync_type, started_at, len(rows), error)
            return None
        return len(rows)

    def _record_success(
        self,
        sync_type: str,
        window: Window,
        started_at: str,
        fetched: int,
        changed: int,
    ) -> None:
        """Write the run's ledger row **inside** its transaction (`transaction()` is the caller's).

        The coverage claim is taken from the class table, not from an `if` here: activities are fetched
        by `limit`, so their row says what arrived and claims no window (Q4).
        """
        claims = CLASSES[sync_type].claims_cursor
        self.ingest_run_repo.log(
            sync_type,
            changed,
            rows_fetched=fetched,
            started_at=started_at,
            cursor_before=window.start if claims else None,
            cursor_after=window.covered_through if claims else None,
        )

    def _record_failure(
        self, sync_type: str, started_at: str, fetched: int, error: Exception
    ) -> None:
        """One error row, committed after the rollback, in a transaction of its own (AC1, SC-10).

        SC-10 alarms on the **absence** of a success row, so the failure has to survive the rollback it
        describes — and it carries what the run genuinely knew (that it asked, and how much arrived)
        while claiming no coverage: a rolled-back window was not covered, whatever arrived.
        """
        with transaction(self.db_conn):
            self.ingest_run_repo.log(
                sync_type,
                0,
                "error",
                str(error),
                rows_fetched=fetched,
                started_at=started_at,
            )

    def get_latest_synced_date(self) -> str | None:
        """Get the most recent date present in the biometrics table."""
        return self.biometrics_repo.get_latest_date()
