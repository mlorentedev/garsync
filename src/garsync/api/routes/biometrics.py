"""Biometrics endpoints."""

from fastapi import APIRouter, Depends, Query

from garsync.api.deps import get_biometrics_repo
from garsync.api.schemas import BiometricItem, BiometricsResponse
from garsync.db.repository import BiometricsRepository

router = APIRouter(prefix="/api", tags=["biometrics"])


@router.get("/biometrics", response_model=BiometricsResponse)
def list_biometrics(
    start_date: str = Query(),
    end_date: str = Query(),
    repo: BiometricsRepository = Depends(get_biometrics_repo),
) -> BiometricsResponse:
    """List biometrics within a date range."""
    rows = repo.get_by_date_range(start_date, end_date)
    metrics = [BiometricItem(**dict(row)) for row in rows]
    return BiometricsResponse(
        metrics=metrics,
        start_date=start_date,
        end_date=end_date,
        count=len(metrics),
    )
