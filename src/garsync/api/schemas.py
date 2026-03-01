"""Pydantic response models for the garsync API."""

from typing import Optional

from pydantic import BaseModel, Field

# --- Activities ---


class ActivityItem(BaseModel):
    activity_id: int
    activity_name: Optional[str] = None
    activity_type: Optional[str] = None
    start_time: Optional[str] = None
    duration_seconds: Optional[float] = None
    distance_meters: Optional[float] = None
    average_heart_rate: Optional[int] = None
    max_heart_rate: Optional[int] = None
    calories: Optional[float] = None


class PaginatedActivities(BaseModel):
    items: list[ActivityItem]
    total: int
    page: int
    limit: int
    has_more: bool


# --- Biometrics ---


class BiometricItem(BaseModel):
    date: str
    resting_heart_rate: Optional[int] = None
    hrv_balance: Optional[str] = None
    body_battery_highest: Optional[int] = None
    body_battery_lowest: Optional[int] = None
    stress_average: Optional[int] = None


class BiometricsResponse(BaseModel):
    metrics: list[BiometricItem]
    start_date: str
    end_date: str
    count: int


# --- Sleep ---


class SleepItem(BaseModel):
    date: str
    sleep_start: Optional[str] = None
    sleep_end: Optional[str] = None
    total_sleep_seconds: Optional[int] = None
    deep_sleep_seconds: Optional[int] = None
    light_sleep_seconds: Optional[int] = None
    rem_sleep_seconds: Optional[int] = None
    awake_sleep_seconds: Optional[int] = None
    sleep_score: Optional[int] = None


class SleepResponse(BaseModel):
    sleep_sessions: list[SleepItem]
    start_date: str
    end_date: str
    count: int


# --- Stats ---


class SummaryStats(BaseModel):
    period: str
    start_date: str
    end_date: str
    total_activities: int = 0
    total_duration_seconds: float = 0.0
    total_distance_meters: float = 0.0
    total_calories: float = 0.0
    avg_duration_seconds: Optional[float] = None
    avg_distance_meters: Optional[float] = None
    avg_heart_rate: Optional[float] = None
    avg_resting_heart_rate: Optional[float] = None
    avg_stress: Optional[float] = None
    avg_body_battery_high: Optional[float] = None
    avg_sleep_seconds: Optional[float] = None
    avg_sleep_score: Optional[float] = None


class HeatmapDay(BaseModel):
    date: str
    activity_count: int
    total_duration: Optional[float] = None
    total_calories: Optional[float] = None
    intensity_level: int = Field(ge=0, le=5)


class HeatmapStatistics(BaseModel):
    total_active_days: int
    total_activities: int
    max_daily_count: int


class HeatmapResponse(BaseModel):
    year: int
    days: list[HeatmapDay]
    statistics: HeatmapStatistics


# --- Sync ---


class SyncStatus(BaseModel):
    last_sync_time: Optional[str] = None
    last_sync_status: Optional[str] = None
    total_activities: int = 0
    total_biometrics: int = 0
    total_sleep: int = 0
    total_sync_logs: int = 0
