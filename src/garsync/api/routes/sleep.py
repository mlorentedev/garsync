"""Sleep endpoints."""

import datetime

from fastapi import APIRouter, Depends, Query

from garsync.api.deps import get_sleep_repo
from garsync.api.schemas import SleepItem, SleepResponse
from garsync.db.repository import SleepRepository

router = APIRouter(prefix="/api", tags=["sleep"])


@router.get("/sleep", response_model=SleepResponse)
def list_sleep(
    start_date: datetime.date = Query(),
    end_date: datetime.date = Query(),
    repo: SleepRepository = Depends(get_sleep_repo),
) -> SleepResponse:
    """List sleep sessions within a date range."""
    rows = repo.get_by_date_range(start_date.isoformat(), end_date.isoformat())
    sessions = [SleepItem(**dict(row)) for row in rows]
    return SleepResponse(
        sleep_sessions=sessions,
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat(),
        count=len(sessions),
    )
