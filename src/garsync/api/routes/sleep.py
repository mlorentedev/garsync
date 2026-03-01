"""Sleep endpoints."""

from fastapi import APIRouter, Depends, Query

from garsync.api.deps import get_sleep_repo
from garsync.api.schemas import SleepItem, SleepResponse
from garsync.db.repository import SleepRepository

router = APIRouter(prefix="/api", tags=["sleep"])


@router.get("/sleep", response_model=SleepResponse)
def list_sleep(
    start_date: str = Query(),
    end_date: str = Query(),
    repo: SleepRepository = Depends(get_sleep_repo),
) -> SleepResponse:
    """List sleep sessions within a date range."""
    rows = repo.get_by_date_range(start_date, end_date)
    sessions = [SleepItem(**dict(row)) for row in rows]
    return SleepResponse(
        sleep_sessions=sessions,
        start_date=start_date,
        end_date=end_date,
        count=len(sessions),
    )
