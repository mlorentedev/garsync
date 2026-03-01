"""Sync status endpoint."""

from fastapi import APIRouter, Depends

from garsync.api.deps import (
    get_activity_repo,
    get_biometrics_repo,
    get_sleep_repo,
    get_sync_log_repo,
)
from garsync.api.schemas import SyncStatus
from garsync.db.repository import (
    ActivityRepository,
    BiometricsRepository,
    SleepRepository,
    SyncLogRepository,
)

router = APIRouter(prefix="/api", tags=["sync"])


@router.get("/sync/status", response_model=SyncStatus)
def sync_status(
    activity_repo: ActivityRepository = Depends(get_activity_repo),
    biometrics_repo: BiometricsRepository = Depends(get_biometrics_repo),
    sleep_repo: SleepRepository = Depends(get_sleep_repo),
    sync_log_repo: SyncLogRepository = Depends(get_sync_log_repo),
) -> SyncStatus:
    """Get current sync status and record counts."""
    latest = sync_log_repo.get_latest()
    return SyncStatus(
        last_sync_time=latest["created_at"] if latest else None,
        last_sync_status=latest["status"] if latest else None,
        total_activities=activity_repo.count(),
        total_biometrics=biometrics_repo.count(),
        total_sleep=sleep_repo.count(),
        total_sync_logs=sync_log_repo.count(),
    )
