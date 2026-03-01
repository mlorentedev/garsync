"""Tests for GET /api/sync/status."""

import pytest
from httpx import AsyncClient


@pytest.mark.anyio
class TestSyncStatus:
    async def test_returns_sync_status(self, client: AsyncClient) -> None:
        resp = await client.get("/api/sync/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "last_sync_time" in data
        assert "total_activities" in data
        assert "total_biometrics" in data
        assert "total_sleep" in data

    async def test_counts_match_seeded_data(self, client: AsyncClient) -> None:
        resp = await client.get("/api/sync/status")
        data = resp.json()
        assert data["total_activities"] == 5
        assert data["total_biometrics"] == 5
        assert data["total_sleep"] == 5
        assert data["total_sync_logs"] == 2

    async def test_last_sync_present(self, client: AsyncClient) -> None:
        resp = await client.get("/api/sync/status")
        data = resp.json()
        assert data["last_sync_time"] is not None
        assert data["last_sync_status"] == "success"

    async def test_no_raw_data_exposed(self, client: AsyncClient) -> None:
        resp = await client.get("/api/sync/status")
        data = resp.json()
        assert "raw_data" not in data
