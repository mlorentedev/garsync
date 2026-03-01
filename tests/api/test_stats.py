"""Tests for GET /api/stats/summary and /api/stats/heatmap."""

import pytest
from httpx import AsyncClient


@pytest.mark.anyio
class TestSummary:
    async def test_default_period(self, client: AsyncClient) -> None:
        resp = await client.get("/api/stats/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["period"] == "week"
        assert "start_date" in data
        assert "end_date" in data

    async def test_custom_date_range(self, client: AsyncClient) -> None:
        resp = await client.get(
            "/api/stats/summary?period=custom&start_date=2026-02-20&end_date=2026-02-24"
        )
        data = resp.json()
        assert data["start_date"] == "2026-02-20"
        assert data["end_date"] == "2026-02-24"
        assert data["total_activities"] == 5
        assert data["total_duration_seconds"] > 0

    async def test_includes_biometrics_averages(self, client: AsyncClient) -> None:
        resp = await client.get(
            "/api/stats/summary?period=custom&start_date=2026-02-20&end_date=2026-02-24"
        )
        data = resp.json()
        assert data["avg_resting_heart_rate"] is not None
        assert data["avg_stress"] is not None

    async def test_includes_sleep_averages(self, client: AsyncClient) -> None:
        resp = await client.get(
            "/api/stats/summary?period=custom&start_date=2026-02-20&end_date=2026-02-24"
        )
        data = resp.json()
        assert data["avg_sleep_seconds"] is not None
        assert data["avg_sleep_score"] is not None

    async def test_empty_range_returns_zeros(self, client: AsyncClient) -> None:
        resp = await client.get(
            "/api/stats/summary?period=custom&start_date=2099-01-01&end_date=2099-01-31"
        )
        data = resp.json()
        assert data["total_activities"] == 0
        assert data["total_duration_seconds"] == 0.0


@pytest.mark.anyio
class TestHeatmap:
    async def test_returns_heatmap_for_year(self, client: AsyncClient) -> None:
        resp = await client.get("/api/stats/heatmap?year=2026")
        assert resp.status_code == 200
        data = resp.json()
        assert data["year"] == 2026
        assert "days" in data
        assert "statistics" in data

    async def test_heatmap_day_fields(self, client: AsyncClient) -> None:
        resp = await client.get("/api/stats/heatmap?year=2026")
        data = resp.json()
        day = data["days"][0]
        assert "date" in day
        assert "activity_count" in day
        assert "intensity_level" in day
        assert 0 <= day["intensity_level"] <= 5

    async def test_heatmap_statistics(self, client: AsyncClient) -> None:
        resp = await client.get("/api/stats/heatmap?year=2026")
        data = resp.json()
        stats = data["statistics"]
        assert stats["total_active_days"] == 5
        assert stats["total_activities"] == 5
        assert stats["max_daily_count"] >= 1

    async def test_heatmap_filter_by_type(self, client: AsyncClient) -> None:
        resp = await client.get("/api/stats/heatmap?year=2026&activity_type=running")
        data = resp.json()
        assert data["statistics"]["total_activities"] == 2

    async def test_heatmap_empty_year(self, client: AsyncClient) -> None:
        resp = await client.get("/api/stats/heatmap?year=2099")
        data = resp.json()
        assert data["days"] == []
        assert data["statistics"]["total_active_days"] == 0
