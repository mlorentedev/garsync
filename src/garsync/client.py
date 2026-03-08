import datetime
import logging
import os
from typing import List, Optional

from garminconnect import Garmin
from tenacity import retry, stop_after_attempt, wait_exponential

from garsync.models import DailyBiometrics, NormalizedActivity, SleepData

logger = logging.getLogger(__name__)


class GarminClient:
    """Wrapper for Garmin Connect API with token caching support."""

    def __init__(self, email: str, password: str, token_store: Optional[str] = None):
        self.email = email
        self.password = password
        self.token_store = token_store
        self.client = Garmin(self.email, self.password)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def login(self) -> None:
        """Authenticate with Garmin Connect using tokens or credentials."""
        try:
            if self.token_store and os.path.exists(self.token_store):
                logger.info(f"Attempting to login using tokens from {self.token_store}...")
                self.client.login(self.token_store)
                logger.info("Token-based authentication successful.")
            else:
                logger.info("Authenticating with Garmin Connect credentials...")
                self.client.login()
                logger.info("Authentication successful.")
                if self.token_store:
                    # Save tokens for next time
                    os.makedirs(os.path.dirname(self.token_store), exist_ok=True)
                    self.client.garth.save(self.token_store)
                    logger.info(f"Session tokens saved to {self.token_store}")
        except Exception as e:
            logger.error(f"Failed to authenticate: {e}")
            # If token login fails, try one more time with credentials (if they exist)
            if self.token_store and os.path.exists(self.token_store):
                logger.warning("Token login failed, falling back to credentials...")
                try:
                    self.client.login()
                    if self.token_store:
                        self.client.garth.save(self.token_store)
                    return
                except Exception as cred_err:
                    logger.error(f"Fallback credential login also failed: {cred_err}")
            raise

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def fetch_activities(self, start: int = 0, limit: int = 100) -> List[NormalizedActivity]:
        logger.info(f"Fetching activities (start={start}, limit={limit})...")
        raw_activities = self.client.get_activities(start, limit)
        activities = []
        for raw in raw_activities:
            try:
                # Convert timestamp from Garmin format
                start_time_str = raw.get("startTimeLocal", raw.get("startTimeGMT"))
                start_time = datetime.datetime.fromisoformat(start_time_str) if start_time_str else None
                
                activities.append(
                    NormalizedActivity(
                        activity_id=raw.get("activityId"),
                        activity_name=raw.get("activityName"),
                        activity_type=raw.get("activityType", {}).get("typeKey"),
                        start_time=start_time,
                        duration_seconds=raw.get("duration", 0.0),
                        distance_meters=raw.get("distance"),
                        average_heart_rate=raw.get("averageHR"),
                        max_heart_rate=raw.get("maxHR"),
                        calories=raw.get("calories"),
                        raw_data=raw,
                    )
                )
            except Exception as e:
                logger.warning(f"Failed to parse activity {raw.get('activityId')}: {e}")
        return activities

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def fetch_biometrics(self, date: datetime.date) -> DailyBiometrics:
        logger.info(f"Fetching biometrics for {date}...")
        try:
            date_str = date.isoformat()
            hr_data = self.client.get_heart_rates(date_str)
            bb_data = self.client.get_body_battery(date_str)
            stress_data = self.client.get_all_day_stress(date_str)
            hrv_data = self.client.get_hrv_data(date_str)

            # Helpers to safely extract data whether it's a list or dict
            def get_dict(data):
                if isinstance(data, list):
                    return data[0] if data else {}
                return data or {}

            hr_dict = get_dict(hr_data)
            bb_dict = get_dict(bb_data)
            stress_dict = get_dict(stress_data)
            hrv_dict = get_dict(hrv_data)

            # Simple aggregations
            rhr = hr_dict.get("restingHeartRate")

            bb_values = [v for t, v in bb_dict.get("bodyBatteryValues", []) if v] if bb_dict else []
            bb_highest = max(bb_values) if bb_values else None
            bb_lowest = min(bb_values) if bb_values else None

            stress_avg = stress_dict.get("averageStressLevel")
            hrv_bal = hrv_dict.get("hrvSummary", {}).get("baselineStatus")

            return DailyBiometrics(
                date=date,
                resting_heart_rate=rhr,
                hrv_balance=hrv_bal,
                body_battery_highest=bb_highest,
                body_battery_lowest=bb_lowest,
                stress_average=stress_avg,
                raw_data={
                    "hr": hr_data,
                    "bb": bb_data,
                    "stress": stress_data,
                    "hrv": hrv_data,
                },
            )
        except Exception as e:
            logger.error(f"Failed to fetch biometrics for {date}: {e}")
            raise

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def fetch_sleep(self, date: datetime.date) -> SleepData:
        logger.info(f"Fetching sleep data for {date}...")
        try:
            sleep_data = self.client.get_sleep_data(date.isoformat())

            # Check if sleep data is available
            daily_sleep = sleep_data.get("dailySleepDTO", {})
            if not daily_sleep:
                return SleepData(date=date, raw_data=sleep_data)

            sleep_start = None
            if start_timestamp := daily_sleep.get("sleepStartTimestampGMT"):
                sleep_start = datetime.datetime.fromtimestamp(start_timestamp / 1000.0, datetime.UTC)

            sleep_end = None
            if end_timestamp := daily_sleep.get("sleepEndTimestampGMT"):
                sleep_end = datetime.datetime.fromtimestamp(end_timestamp / 1000.0, datetime.UTC)

            return SleepData(
                date=date,
                sleep_start=sleep_start,
                sleep_end=sleep_end,
                total_sleep_seconds=daily_sleep.get("sleepTimeSeconds"),
                deep_sleep_seconds=daily_sleep.get("deepSleepSeconds"),
                light_sleep_seconds=daily_sleep.get("lightSleepSeconds"),
                rem_sleep_seconds=daily_sleep.get("remSleepSeconds"),
                awake_sleep_seconds=daily_sleep.get("awakeSleepSeconds"),
                sleep_score=sleep_data.get("sleepScore", {}).get("value"),
                raw_data=sleep_data,
            )
        except Exception as e:
            logger.error(f"Failed to fetch sleep for {date}: {e}")
            raise
