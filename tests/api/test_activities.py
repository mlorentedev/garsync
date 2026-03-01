"""Tests for GET /api/activities."""

import pytest
from httpx import AsyncClient


@pytest.mark.anyio
class TestListActivities:
    async def test_returns_paginated_response(self, client: AsyncClient) -> None:
        resp = await client.get("/api/activities")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "limit" in data
        assert "has_more" in data

    async def test_default_pagination(self, client: AsyncClient) -> None:
        resp = await client.get("/api/activities")
        data = resp.json()
        assert data["total"] == 5
        assert data["page"] == 1
        assert data["limit"] == 20
        assert data["has_more"] is False
        assert len(data["items"]) == 5

    async def test_custom_page_size(self, client: AsyncClient) -> None:
        resp = await client.get("/api/activities?page=1&limit=2")
        data = resp.json()
        assert len(data["items"]) == 2
        assert data["has_more"] is True
        assert data["total"] == 5

    async def test_second_page(self, client: AsyncClient) -> None:
        resp = await client.get("/api/activities?page=2&limit=2")
        data = resp.json()
        assert len(data["items"]) == 2
        assert data["has_more"] is True

    async def test_filter_by_activity_type(self, client: AsyncClient) -> None:
        resp = await client.get("/api/activities?activity_type=running")
        data = resp.json()
        assert data["total"] == 2
        for item in data["items"]:
            assert item["activity_type"] == "running"

    async def test_filter_by_date_range(self, client: AsyncClient) -> None:
        resp = await client.get("/api/activities?start_date=2026-02-21&end_date=2026-02-22")
        data = resp.json()
        assert data["total"] == 2

    async def test_activity_item_fields(self, client: AsyncClient) -> None:
        resp = await client.get("/api/activities?limit=1")
        data = resp.json()
        item = data["items"][0]
        assert "activity_id" in item
        assert "activity_name" in item
        assert "activity_type" in item
        assert "start_time" in item
        assert "duration_seconds" in item
        assert "raw_data" not in item

    async def test_empty_result(self, client: AsyncClient) -> None:
        resp = await client.get("/api/activities?activity_type=nonexistent")
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []
        assert data["has_more"] is False
