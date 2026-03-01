"""Tests for GET /api/sleep."""

import pytest
from httpx import AsyncClient


@pytest.mark.anyio
class TestListSleep:
    async def test_requires_date_params(self, client: AsyncClient) -> None:
        resp = await client.get("/api/sleep")
        assert resp.status_code == 422

    async def test_returns_sessions_in_range(self, client: AsyncClient) -> None:
        resp = await client.get("/api/sleep?start_date=2026-02-20&end_date=2026-02-24")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 5
        assert len(data["sleep_sessions"]) == 5

    async def test_sleep_item_fields(self, client: AsyncClient) -> None:
        resp = await client.get("/api/sleep?start_date=2026-02-20&end_date=2026-02-20")
        data = resp.json()
        item = data["sleep_sessions"][0]
        assert "date" in item
        assert "sleep_start" in item
        assert "total_sleep_seconds" in item
        assert "sleep_score" in item
        assert "raw_data" not in item

    async def test_empty_range(self, client: AsyncClient) -> None:
        resp = await client.get("/api/sleep?start_date=2099-01-01&end_date=2099-01-31")
        data = resp.json()
        assert data["count"] == 0
        assert data["sleep_sessions"] == []

    async def test_single_day(self, client: AsyncClient) -> None:
        resp = await client.get("/api/sleep?start_date=2026-02-22&end_date=2026-02-22")
        data = resp.json()
        assert data["count"] == 1
