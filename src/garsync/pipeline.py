"""Core synchronization pipeline logic."""

import logging
import sqlite3
from datetime import UTC, date, datetime
from typing import Any

from garsync.client import GarminClient
from garsync.db import (
    ActivityRepository,
    BiometricsRepository,
    IngestRunRepository,
    SleepRepository,
)
from garsync.ingest.payload import canonical_json
from garsync.models import DailyBiometrics, NormalizedActivity, SleepData
from garsync.timeutil import offset_minutes, parse_garmin_timestamp, utc_z

logger = logging.getLogger(__name__)

#: Provenance written on every row this process ingests. A second source (the scale, SCALE-001) gets
#: its own value here rather than a second code path.
GARMIN = "garmin"


def _now_z() -> str:
    """The instant a run began, in the at-rest spelling.

    Captured **before** the fetch, never at the ledger write: `created_at` is the commit instant (the
    finish), so a `started_at` taken at log time would silently measure the write's own latency.
    """
    return utc_z(datetime.now(UTC))


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

    def __init__(self, client: GarminClient, db_conn: sqlite3.Connection):
        self.client = client
        self.db_conn = db_conn
        self.activity_repo = ActivityRepository(db_conn)
        self.biometrics_repo = BiometricsRepository(db_conn)
        self.sleep_repo = SleepRepository(db_conn)
        self.ingest_run_repo = IngestRunRepository(db_conn)

    def sync_range(self, dates: list[date], activities_limit: int = 100) -> dict[str, int]:
        """Run a full sync for the given range of dates.

        Orchestration only. Each data class is a run, and a run answers with what it fetched or with
        `None` when it failed; the ledger row is written inside the run, never here. The grain of the
        daily classes is still one row per day rather than one per covered window — that is SUB-002
        block 5, which replaces these bodies with the transaction-and-cursor run; what changed here is
        that the ledger counts what the adapter returned instead of what it fetched.
        """
        results: dict[str, int] = {"activities": 0, "biometrics": 0, "sleep": 0, "errors": 0}

        _tally(results, "activities", self._sync_activities(activities_limit))
        for day in dates:
            _tally(results, "biometrics", self._sync_biometrics(day))
            _tally(results, "sleep", self._sync_sleep(day))
        return results

    def _sync_activities(self, activities_limit: int) -> int | None:
        """One run of the activities class. Returns what the adapter fetched, or None on failure.

        `rows_upserted` is the summed change count of the guarded upserts, so a re-pull over a covered
        window records 0 while `rows_fetched` still records the 100 rows Garmin returned (AC7). Before
        this, both columns carried the fetched count — the number that made "zero changed values"
        unauditable.
        """
        started_at = _now_z()
        try:
            activities = self.client.fetch_activities(limit=activities_limit)
            changed = sum(
                self.activity_repo.upsert(activity_to_row(activity)) for activity in activities
            )
            self.ingest_run_repo.log(
                "activities", changed, rows_fetched=len(activities), started_at=started_at
            )
            return len(activities)
        except Exception as e:  # noqa: BLE001
            logger.error(f"Failed to sync activities: {e}")
            self.ingest_run_repo.log(
                "activities", 0, "error", str(e), rows_fetched=0, started_at=started_at
            )
            return None

    def _sync_biometrics(self, day: date) -> int | None:
        """One day's biometrics run: the four endpoints behind one call, one row, one ledger entry."""
        date_str = day.isoformat()
        started_at = _now_z()
        try:
            bio = self.client.fetch_biometrics(day)
            changed = self.biometrics_repo.upsert(biometrics_to_row(bio))
            self.ingest_run_repo.log("biometrics", changed, rows_fetched=1, started_at=started_at)
            return 1
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Failed to sync biometrics for {date_str}: {e}")
            self.ingest_run_repo.log(
                "biometrics",
                0,
                "error",
                f"{date_str}: {e}",
                rows_fetched=0,
                started_at=started_at,
            )
            return None

    def _sync_sleep(self, day: date) -> int | None:
        """One night's sleep run. A night that is not published yet is an error row, not a zero."""
        date_str = day.isoformat()
        started_at = _now_z()
        try:
            sleep = self.client.fetch_sleep(day)
            changed = self.sleep_repo.upsert(sleep_to_row(sleep))
            self.ingest_run_repo.log("sleep", changed, rows_fetched=1, started_at=started_at)
            return 1
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Failed to sync sleep for {date_str}: {e}")
            self.ingest_run_repo.log(
                "sleep",
                0,
                "error",
                f"{date_str}: {e}",
                rows_fetched=0,
                started_at=started_at,
            )
            return None

    def get_latest_synced_date(self) -> str | None:
        """Get the most recent date present in the biometrics table."""
        return self.biometrics_repo.get_latest_date()
