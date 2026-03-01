"""Test fixtures for API integration tests."""

import json
import sqlite3

import pytest
from httpx import ASGITransport, AsyncClient

from garsync.api.main import create_app
from garsync.db.connection import get_connection
from garsync.db.schema import init_db


@pytest.fixture()
def seeded_db() -> sqlite3.Connection:
    """Create an in-memory SQLite DB with seed data for API tests."""
    conn = get_connection(":memory:")
    init_db(conn)
    _seed_activities(conn)
    _seed_biometrics(conn)
    _seed_sleep(conn)
    _seed_sync_log(conn)
    return conn


@pytest.fixture()
async def client(seeded_db: sqlite3.Connection):
    """httpx AsyncClient wired to an in-memory DB."""
    app = create_app(conn=seeded_db)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _seed_activities(conn: sqlite3.Connection) -> None:
    types = ["running", "cycling", "swimming", "running", "hiking"]
    for i in range(5):
        conn.execute(
            """
            INSERT INTO activities
                (activity_id, activity_name, activity_type, start_time,
                 duration_seconds, distance_meters, average_heart_rate,
                 max_heart_rate, calories, raw_data)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                1000 + i,
                f"Activity {i}",
                types[i],
                f"2026-02-{20 + i:02d}T08:00:00",
                1800.0 + i * 600,
                5000.0 + i * 1000,
                140 + i,
                170 + i,
                300.0 + i * 50,
                json.dumps({"activityId": 1000 + i}),
            ),
        )
    conn.commit()


def _seed_biometrics(conn: sqlite3.Connection) -> None:
    for i in range(5):
        conn.execute(
            """
            INSERT INTO biometrics
                (date, resting_heart_rate, hrv_balance,
                 body_battery_highest, body_battery_lowest, stress_average, raw_data)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"2026-02-{20 + i:02d}",
                50 + i,
                "BALANCED",
                90 - i,
                20 + i,
                25 + i * 2,
                json.dumps({"source": "test"}),
            ),
        )
    conn.commit()


def _seed_sleep(conn: sqlite3.Connection) -> None:
    for i in range(5):
        conn.execute(
            """
            INSERT INTO sleep
                (date, sleep_start, sleep_end, total_sleep_seconds,
                 deep_sleep_seconds, light_sleep_seconds, rem_sleep_seconds,
                 awake_sleep_seconds, sleep_score, raw_data)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"2026-02-{20 + i:02d}",
                f"2026-02-{19 + i:02d}T23:00:00",
                f"2026-02-{20 + i:02d}T06:30:00",
                25000 + i * 1000,
                6000 + i * 200,
                10000 + i * 300,
                5000 + i * 100,
                3000 + i * 50,
                75 + i * 2,
                json.dumps({"source": "test"}),
            ),
        )
    conn.commit()


def _seed_sync_log(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        INSERT INTO sync_log (sync_type, records_synced, status, error_message)
        VALUES (?, ?, ?, ?)
        """,
        ("activities", 5, "success", None),
    )
    conn.execute(
        """
        INSERT INTO sync_log (sync_type, records_synced, status, error_message)
        VALUES (?, ?, ?, ?)
        """,
        ("biometrics", 5, "success", None),
    )
    conn.commit()
