"""Shared test fixtures for garsync tests."""

import json
import sqlite3

import pytest

from garsync.db.connection import get_connection
from garsync.db.schema import init_db


@pytest.fixture()
def in_memory_db() -> sqlite3.Connection:
    """Create an in-memory SQLite connection with schema initialized."""
    conn = get_connection(":memory:")
    init_db(conn)
    yield conn
    conn.close()


@pytest.fixture()
def sample_activity_row() -> dict:
    """A single activity row dict matching the activities table columns."""
    return {
        "activity_id": 123456789,
        "activity_name": "Morning Run",
        "activity_type": "running",
        "start_time": "2026-02-28T07:30:00",
        "duration_seconds": 1800.0,
        "distance_meters": 5000.0,
        "average_heart_rate": 145,
        "max_heart_rate": 172,
        "calories": 350.0,
        "raw_data": json.dumps({"activityId": 123456789, "source": "test"}),
    }


@pytest.fixture()
def sample_biometrics_row() -> dict:
    """A single biometrics row dict matching the biometrics table columns."""
    return {
        "date": "2026-02-28",
        "resting_heart_rate": 52,
        "hrv_balance": "BALANCED",
        "body_battery_highest": 95,
        "body_battery_lowest": 22,
        "stress_average": 28,
        "raw_data": json.dumps({"source": "test"}),
    }


@pytest.fixture()
def sample_sleep_row() -> dict:
    """A single sleep row dict matching the sleep table columns."""
    return {
        "date": "2026-02-28",
        "sleep_start": "2026-02-27T23:15:00",
        "sleep_end": "2026-02-28T06:45:00",
        "total_sleep_seconds": 27000,
        "deep_sleep_seconds": 7200,
        "light_sleep_seconds": 10800,
        "rem_sleep_seconds": 5400,
        "awake_sleep_seconds": 3600,
        "sleep_score": 82,
        "raw_data": json.dumps({"source": "test"}),
    }
