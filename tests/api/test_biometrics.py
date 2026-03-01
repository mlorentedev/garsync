"""Tests for GET /api/biometrics."""

import pytest
from httpx import AsyncClient


@pytest.mark.anyio
class TestListBiometrics:
    async def test_requires_date_params(self, client: AsyncClient) -> None:
        resp = await client.get("/api/biometrics")
        assert resp.status_code == 422

    async def test_returns_metrics_in_range(self, client: AsyncClient) -> None:
        resp = await client.get("/api/biometrics?start_date=2026-02-20&end_date=2026-02-24")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 5
        assert data["start_date"] == "2026-02-20"
        assert data["end_date"] == "2026-02-24"
        assert len(data["metrics"]) == 5

    async def test_biometric_item_fields(self, client: AsyncClient) -> None:
        resp = await client.get("/api/biometrics?start_date=2026-02-20&end_date=2026-02-20")
        data = resp.json()
        item = data["metrics"][0]
        assert "date" in item
        assert "resting_heart_rate" in item
        assert "hrv_balance" in item
        assert "body_battery_highest" in item
        assert "stress_average" in item
        assert "raw_data" not in item

    async def test_empty_range(self, client: AsyncClient) -> None:
        resp = await client.get("/api/biometrics?start_date=2099-01-01&end_date=2099-01-31")
        data = resp.json()
        assert data["count"] == 0
        assert data["metrics"] == []

    async def test_single_day(self, client: AsyncClient) -> None:
        resp = await client.get("/api/biometrics?start_date=2026-02-22&end_date=2026-02-22")
        data = resp.json()
        assert data["count"] == 1
        assert data["metrics"][0]["date"] == "2026-02-22"
