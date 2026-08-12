"""Pydantic response models for the garsync API."""

from pydantic import BaseModel, Field

# --- Activities ---


class ActivityItem(BaseModel):
    activity_id: int
    activity_name: str | None = None
    activity_type: str | None = None
    start_time: str | None = None
    duration_seconds: float | None = None
    distance_meters: float | None = None
    average_heart_rate: int | None = None
    max_heart_rate: int | None = None
    calories: float | None = None


class PaginatedActivities(BaseModel):
    items: list[ActivityItem]
    total: int
    page: int
    limit: int
    has_more: bool


# --- Biometrics ---


class BiometricItem(BaseModel):
    date: str
    resting_heart_rate: int | None = None
    hrv_balance: str | None = None
    body_battery_highest: int | None = None
    body_battery_lowest: int | None = None
    stress_average: int | None = None


class BiometricsResponse(BaseModel):
    metrics: list[BiometricItem]
    start_date: str
    end_date: str
    count: int


# --- Sleep ---


class SleepItem(BaseModel):
    date: str
    sleep_start: str | None = None
    sleep_end: str | None = None
    total_sleep_seconds: int | None = None
    deep_sleep_seconds: int | None = None
    light_sleep_seconds: int | None = None
    rem_sleep_seconds: int | None = None
    awake_sleep_seconds: int | None = None
    sleep_score: int | None = None


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
    avg_duration_seconds: float | None = None
    avg_distance_meters: float | None = None
    avg_heart_rate: float | None = None
    avg_resting_heart_rate: float | None = None
    avg_stress: float | None = None
    avg_body_battery_high: float | None = None
    avg_sleep_seconds: float | None = None
    avg_sleep_score: float | None = None


class HeatmapDay(BaseModel):
    date: str
    activity_count: int
    total_duration: float | None = None
    total_calories: float | None = None
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
    last_sync_time: str | None = None
    last_sync_status: str | None = None
    total_activities: int = 0
    total_biometrics: int = 0
    total_sleep: int = 0
    total_sync_logs: int = 0
