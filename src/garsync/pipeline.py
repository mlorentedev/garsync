"""Core synchronization pipeline logic."""

import json
import logging
import sqlite3
from datetime import date
from typing import Any

from garsync.client import GarminClient
from garsync.db import (
    ActivityRepository,
    BiometricsRepository,
    IngestRunRepository,
    SleepRepository,
)
from garsync.models import DailyBiometrics, NormalizedActivity, SleepData
from garsync.timeutil import offset_minutes, parse_garmin_timestamp, utc_z

logger = logging.getLogger(__name__)

#: Provenance written on every row this process ingests. A second source (the scale, SCALE-001) gets
#: its own value here rather than a second code path.
GARMIN = "garmin"


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
        "raw_data": json.dumps(raw),
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
        "raw_data": json.dumps(bio.raw_data),
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
        "raw_data": json.dumps(sleep.raw_data),
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
        """Run a full sync for the given range of dates."""
        results = {
            "activities": 0,
            "biometrics": 0,
            "sleep": 0,
            "errors": 0,
        }

        # 1. Activities (usually fetched in bulk, not per day)
        try:
            activities = self.client.fetch_activities(limit=activities_limit)
            for activity in activities:
                self.activity_repo.upsert(activity_to_row(activity))
            results["activities"] = len(activities)
            self.ingest_run_repo.log("activities", len(activities), "success")
        except Exception as e:  # noqa: BLE001
            logger.error(f"Failed to sync activities: {e}")
            self.ingest_run_repo.log("activities", 0, "error", str(e))
            results["errors"] += 1

        # 2. Daily metrics (Biometrics and Sleep)
        for d in dates:
            date_str = d.isoformat()

            # Biometrics
            try:
                bio = self.client.fetch_biometrics(d)
                self.biometrics_repo.upsert(biometrics_to_row(bio))
                results["biometrics"] += 1
                self.ingest_run_repo.log("biometrics", 1, "success")
            except Exception as e:  # noqa: BLE001
                logger.warning(f"Failed to sync biometrics for {date_str}: {e}")
                self.ingest_run_repo.log("biometrics", 0, "error", f"{date_str}: {e}")
                results["errors"] += 1

            # Sleep
            try:
                sleep = self.client.fetch_sleep(d)
                self.sleep_repo.upsert(sleep_to_row(sleep))
                results["sleep"] += 1
                self.ingest_run_repo.log("sleep", 1, "success")
            except Exception as e:  # noqa: BLE001
                logger.warning(f"Failed to sync sleep for {date_str}: {e}")
                self.ingest_run_repo.log("sleep", 0, "error", f"{date_str}: {e}")
                results["errors"] += 1

        return results

    def get_latest_synced_date(self) -> str | None:
        """Get the most recent date present in the biometrics table."""
        return self.biometrics_repo.get_latest_date()
