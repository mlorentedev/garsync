"""Activity endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends, Query

from garsync.api.deps import get_activity_repo
from garsync.api.schemas import ActivityItem, PaginatedActivities
from garsync.db.repository import ActivityRepository

router = APIRouter(prefix="/api", tags=["activities"])


@router.get("/activities", response_model=PaginatedActivities)
def list_activities(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    start_date: Optional[str] = Query(default=None),
    end_date: Optional[str] = Query(default=None),
    activity_type: Optional[str] = Query(default=None),
    repo: ActivityRepository = Depends(get_activity_repo),
) -> PaginatedActivities:
    """List activities with pagination and optional filters."""
    rows, total = repo.get_paginated(
        page=page,
        limit=limit,
        start_date=start_date,
        end_date=end_date,
        activity_type=activity_type,
    )
    items = [ActivityItem(**dict(row)) for row in rows]
    return PaginatedActivities(
        items=items,
        total=total,
        page=page,
        limit=limit,
        has_more=(page * limit) < total,
    )
