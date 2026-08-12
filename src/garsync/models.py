from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field


class NormalizedActivity(BaseModel):
    activity_id: int
    activity_name: str | None = None
    activity_type: str | None = None
    start_time: datetime | None = None
    duration_seconds: float
    distance_meters: float | None = None
    average_heart_rate: int | None = None
    max_heart_rate: int | None = None
    calories: float | None = None
    raw_data: dict[str, Any] = Field(default_factory=dict, exclude=True)


class DailyBiometrics(BaseModel):
    date: date
    resting_heart_rate: int | None = None
    hrv_balance: str | None = None
    body_battery_highest: int | None = None
    body_battery_lowest: int | None = None
    stress_average: int | None = None
    raw_data: dict[str, Any] = Field(default_factory=dict, exclude=True)


class SleepData(BaseModel):
    date: date
    sleep_start: datetime | None = None
    sleep_end: datetime | None = None
    total_sleep_seconds: int | None = None
    deep_sleep_seconds: int | None = None
    light_sleep_seconds: int | None = None
    rem_sleep_seconds: int | None = None
    awake_sleep_seconds: int | None = None
    sleep_score: int | None = None
    raw_data: dict[str, Any] = Field(default_factory=dict, exclude=True)


class SyncResult(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    activities: list[NormalizedActivity] = Field(default_factory=list)
    biometrics: list[DailyBiometrics] = Field(default_factory=list)
    sleep: list[SleepData] = Field(default_factory=list)
