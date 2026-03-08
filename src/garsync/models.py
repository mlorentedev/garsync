from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class NormalizedActivity(BaseModel):
    activity_id: int
    activity_name: Optional[str] = None
    activity_type: Optional[str] = None
    start_time: Optional[datetime] = None
    duration_seconds: float
    distance_meters: Optional[float] = None
    average_heart_rate: Optional[int] = None
    max_heart_rate: Optional[int] = None
    calories: Optional[float] = None
    raw_data: dict[str, Any] = Field(default_factory=dict, exclude=True)


class DailyBiometrics(BaseModel):
    date: date
    resting_heart_rate: Optional[int] = None
    hrv_balance: Optional[str] = None
    body_battery_highest: Optional[int] = None
    body_battery_lowest: Optional[int] = None
    stress_average: Optional[int] = None
    raw_data: dict[str, Any] = Field(default_factory=dict, exclude=True)


class SleepData(BaseModel):
    date: date
    sleep_start: Optional[datetime] = None
    sleep_end: Optional[datetime] = None
    total_sleep_seconds: Optional[int] = None
    deep_sleep_seconds: Optional[int] = None
    light_sleep_seconds: Optional[int] = None
    rem_sleep_seconds: Optional[int] = None
    awake_sleep_seconds: Optional[int] = None
    sleep_score: Optional[int] = None
    raw_data: dict[str, Any] = Field(default_factory=dict, exclude=True)


class SyncResult(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    activities: list[NormalizedActivity] = Field(default_factory=list)
    biometrics: list[DailyBiometrics] = Field(default_factory=list)
    sleep: list[SleepData] = Field(default_factory=list)
