"""Stats endpoints — summary and heatmap."""

from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query

from garsync.api.deps import get_activity_repo, get_biometrics_repo, get_sleep_repo
from garsync.api.schemas import (
    HeatmapDay,
    HeatmapResponse,
    HeatmapStatistics,
    SummaryStats,
)
from garsync.db.repository import (
    ActivityRepository,
    BiometricsRepository,
    SleepRepository,
)

router = APIRouter(prefix="/api/stats", tags=["stats"])


def _resolve_dates(
    period: str,
    start_date: Optional[str],
    end_date: Optional[str],
) -> tuple[str, str]:
    """Resolve start/end dates from period or explicit params."""
    today = date.today()
    if start_date and end_date:
        return start_date, end_date
    if period == "week":
        start = today - timedelta(days=7)
    elif period == "month":
        start = today - timedelta(days=30)
    else:
        start = today - timedelta(days=30)
    return start.isoformat(), today.isoformat()


@router.get("/summary", response_model=SummaryStats)
def summary(
    period: str = Query(default="week"),
    start_date: Optional[str] = Query(default=None),
    end_date: Optional[str] = Query(default=None),
    activity_repo: ActivityRepository = Depends(get_activity_repo),
    biometrics_repo: BiometricsRepository = Depends(get_biometrics_repo),
    sleep_repo: SleepRepository = Depends(get_sleep_repo),
) -> SummaryStats:
    """Get aggregated stats for a period."""
    sd, ed = _resolve_dates(period, start_date, end_date)

    activity_stats = activity_repo.get_summary_stats(sd, ed)
    bio_stats = biometrics_repo.get_avg_stats(sd, ed)
    sleep_stats = sleep_repo.get_avg_stats(sd, ed)

    return SummaryStats(
        period=period,
        start_date=sd,
        end_date=ed,
        total_activities=activity_stats["total_activities"] if activity_stats else 0,
        total_duration_seconds=activity_stats["total_duration_seconds"] if activity_stats else 0.0,
        total_distance_meters=activity_stats["total_distance_meters"] if activity_stats else 0.0,
        total_calories=activity_stats["total_calories"] if activity_stats else 0.0,
        avg_duration_seconds=activity_stats["avg_duration_seconds"] if activity_stats else None,
        avg_distance_meters=activity_stats["avg_distance_meters"] if activity_stats else None,
        avg_heart_rate=activity_stats["avg_heart_rate"] if activity_stats else None,
        avg_resting_heart_rate=bio_stats["avg_resting_heart_rate"] if bio_stats else None,
        avg_stress=bio_stats["avg_stress"] if bio_stats else None,
        avg_body_battery_high=bio_stats["avg_body_battery_high"] if bio_stats else None,
        avg_sleep_seconds=sleep_stats["avg_sleep_seconds"] if sleep_stats else None,
        avg_sleep_score=sleep_stats["avg_sleep_score"] if sleep_stats else None,
    )


def _compute_intensity(count: int, max_count: int) -> int:
    """Map activity count to 0-5 intensity level."""
    if count == 0 or max_count == 0:
        return 0
    ratio = count / max_count
    if ratio <= 0.2:
        return 1
    if ratio <= 0.4:
        return 2
    if ratio <= 0.6:
        return 3
    if ratio <= 0.8:
        return 4
    return 5


@router.get("/heatmap", response_model=HeatmapResponse)
def heatmap(
    year: Optional[int] = Query(default=None),
    activity_type: Optional[str] = Query(default=None),
    repo: ActivityRepository = Depends(get_activity_repo),
) -> HeatmapResponse:
    """Get activity heatmap data for a year."""
    target_year = year or date.today().year
    rows = repo.get_heatmap_data(target_year, activity_type)

    max_count = max((row["activity_count"] for row in rows), default=0)
    days = [
        HeatmapDay(
            date=row["date"],
            activity_count=row["activity_count"],
            total_duration=row["total_duration"],
            total_calories=row["total_calories"],
            intensity_level=_compute_intensity(row["activity_count"], max_count),
        )
        for row in rows
    ]

    total_activities = sum(d.activity_count for d in days)
    return HeatmapResponse(
        year=target_year,
        days=days,
        statistics=HeatmapStatistics(
            total_active_days=len(days),
            total_activities=total_activities,
            max_daily_count=max_count,
        ),
    )
