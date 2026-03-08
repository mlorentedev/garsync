"""Full end-to-end integration test: CLI sync → SQLite DB → FastAPI API."""

import tempfile
from datetime import date, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from typer.testing import CliRunner

from garsync.api.main import create_app
from garsync.cli import app as cli_app
from garsync.client import GarminClient
from garsync.models import DailyBiometrics, NormalizedActivity, SleepData

runner = CliRunner()


@pytest.fixture()
def mock_garmin_data():
    """Return consistent mock data for integration testing."""
    activity = NormalizedActivity(
        activity_id=999,
        activity_name="Integration Run",
        activity_type="running",
        start_time=datetime(2026, 3, 7, 10, 0, 0),
        duration_seconds=3600.0,
        distance_meters=10000.0,
        average_heart_rate=150,
        max_heart_rate=180,
        calories=800.0,
        raw_data={"activityId": 999},
    )
    biometrics = DailyBiometrics(
        date=date(2026, 3, 7),
        resting_heart_rate=48,
        hrv_balance="BALANCED",
        body_battery_highest=95,
        body_battery_lowest=15,
        stress_average=20,
        raw_data={"source": "integration-test"},
    )
    sleep = SleepData(
        date=date(2026, 3, 7),
        sleep_start=datetime(2026, 3, 6, 23, 0),
        sleep_end=datetime(2026, 3, 7, 7, 0),
        total_sleep_seconds=28800,
        sleep_score=92,
        raw_data={"source": "integration-test"},
    )
    return [activity], biometrics, sleep


@pytest.mark.anyio
async def test_full_pipeline_sync_to_api(mock_garmin_data) -> None:
    activities, biometrics, sleep = mock_garmin_data

    # 1. Setup temporary DB
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "integration_test.db"

        # 2. Mock GarminClient
        mock_client = MagicMock(spec=GarminClient)
        mock_client.fetch_activities.return_value = activities
        mock_client.fetch_biometrics.return_value = biometrics
        mock_client.fetch_sleep.return_value = sleep

        # 3. Run CLI sync
        with patch("garsync.cli.GarminClient", return_value=mock_client):
            result = runner.invoke(
                cli_app,
                [
                    "--email",
                    "test@example.com",
                    "--password",
                    "secret",
                    "--db",
                    str(db_path),
                    "--days",
                    "1",
                ],
            )
            assert result.exit_code == 0

        # 4. Initialize FastAPI with the SAME database
        # We set the environment variable so create_app() picks it up in lifespan if needed,
        # but here we'll just pass the connection explicitly for simplicity and speed.
        import garsync.db.connection as db_conn

        conn = db_conn.get_connection(str(db_path))

        app = create_app(conn=conn)
        transport = ASGITransport(app=app)

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            headers = {"X-API-KEY": "dev_key"}
            # 5. Verify API endpoints
            # Check activities
            resp = await client.get("/api/activities", headers=headers)
            assert resp.status_code == 200
            data = resp.json()
            assert data["total"] == 1
            assert data["items"][0]["activity_name"] == "Integration Run"

            # Check biometrics
            resp = await client.get(
                "/api/biometrics?start_date=2026-03-01&end_date=2026-03-31", headers=headers
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["count"] == 1
            assert data["metrics"][0]["resting_heart_rate"] == 48

            # Check stats summary
            resp = await client.get("/api/stats/summary", headers=headers)
            assert resp.status_code == 200
            data = resp.json()
            assert data["total_activities"] == 1
            assert data["total_distance_meters"] == 10000.0

            # Check sync status
            resp = await client.get("/api/sync/status", headers=headers)
            assert resp.status_code == 200
            data = resp.json()
            assert data["total_activities"] == 1
            assert data["last_sync_time"] is not None

        conn.close()
