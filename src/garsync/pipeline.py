"""Core synchronization pipeline logic."""

import json
import logging
from datetime import date
from typing import Optional

from garsync.client import GarminClient
from garsync.db import (
    ActivityRepository,
    BiometricsRepository,
    SleepRepository,
    SyncLogRepository,
)
from garsync.models import DailyBiometrics, NormalizedActivity, SleepData

logger = logging.getLogger(__name__)


class SyncService:
    """Orchestrates the synchronization process between Garmin and SQLite."""

    def __init__(self, client: GarminClient, db_conn):
        self.client = client
        self.db_conn = db_conn
        self.activity_repo = ActivityRepository(db_conn)
        self.biometrics_repo = BiometricsRepository(db_conn)
        self.sleep_repo = SleepRepository(db_conn)
        self.sync_log_repo = SyncLogRepository(db_conn)

    def sync_range(self, dates: list[date], activities_limit: int = 100) -> dict:
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
                self.activity_repo.upsert(self._activity_to_row(activity))
            results["activities"] = len(activities)
            self.sync_log_repo.log("activities", len(activities), "success")
        except Exception as e:
            logger.error(f"Failed to sync activities: {e}")
            self.sync_log_repo.log("activities", 0, "error", str(e))
            results["errors"] += 1

        # 2. Daily metrics (Biometrics and Sleep)
        for d in dates:
            date_str = d.isoformat()
            
            # Biometrics
            try:
                bio = self.client.fetch_biometrics(d)
                self.biometrics_repo.upsert(self._biometrics_to_row(bio))
                results["biometrics"] += 1
                self.sync_log_repo.log("biometrics", 1, "success")
            except Exception as e:
                logger.warning(f"Failed to sync biometrics for {date_str}: {e}")
                self.sync_log_repo.log("biometrics", 0, "error", f"{date_str}: {e}")
                results["errors"] += 1

            # Sleep
            try:
                sleep = self.client.fetch_sleep(d)
                self.sleep_repo.upsert(self._sleep_to_row(sleep))
                results["sleep"] += 1
                self.sync_log_repo.log("sleep", 1, "success")
            except Exception as e:
                logger.warning(f"Failed to sync sleep for {date_str}: {e}")
                self.sync_log_repo.log("sleep", 0, "error", f"{date_str}: {e}")
                results["errors"] += 1

        return results

    def get_latest_synced_date(self) -> Optional[str]:
        """Get the most recent date present in the biometrics table."""
        return self.biometrics_repo.get_latest_date()

    # --- Internal Converters ---

    def _activity_to_row(self, activity: NormalizedActivity) -> dict:
        return {
            "activity_id": activity.activity_id,
            "activity_name": activity.activity_name,
            "activity_type": activity.activity_type,
            "start_time": activity.start_time.isoformat() if activity.start_time else None,
            "duration_seconds": activity.duration_seconds,
            "distance_meters": activity.distance_meters,
            "average_heart_rate": activity.average_heart_rate,
            "max_heart_rate": activity.max_heart_rate,
            "calories": activity.calories,
            "raw_data": json.dumps(activity.raw_data),
        }

    def _biometrics_to_row(self, bio: DailyBiometrics) -> dict:
        return {
            "date": bio.date.isoformat(),
            "resting_heart_rate": bio.resting_heart_rate,
            "hrv_balance": bio.hrv_balance,
            "body_battery_highest": bio.body_battery_highest,
            "body_battery_lowest": bio.body_battery_lowest,
            "stress_average": bio.stress_average,
            "raw_data": json.dumps(bio.raw_data),
        }

    def _sleep_to_row(self, sleep: SleepData) -> dict:
        return {
            "date": sleep.date.isoformat(),
            "sleep_start": sleep.sleep_start.isoformat() if sleep.sleep_start else None,
            "sleep_end": sleep.sleep_end.isoformat() if sleep.sleep_end else None,
            "total_sleep_seconds": sleep.total_sleep_seconds,
            "deep_sleep_seconds": sleep.deep_sleep_seconds,
            "light_sleep_seconds": sleep.light_sleep_seconds,
            "rem_sleep_seconds": sleep.rem_sleep_seconds,
            "awake_sleep_seconds": sleep.awake_sleep_seconds,
            "sleep_score": sleep.sleep_score,
            "raw_data": json.dumps(sleep.raw_data),
        }
