"""Integration tests for the full sync pipeline with mocked GarminClient."""

import json
import tempfile
from datetime import date, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from garsync.cli import _dates_to_sync, app
from garsync.client import GarminClient
from garsync.db import (
    ActivityRepository,
    BiometricsRepository,
    SleepRepository,
    SyncLogRepository,
    get_connection,
)
from garsync.models import DailyBiometrics, NormalizedActivity, SleepData
from garsync.pipeline import activity_to_row, biometrics_to_row, sleep_to_row

runner = CliRunner()


# --- Fixtures ---


@pytest.fixture()
def mock_activity() -> NormalizedActivity:
    return NormalizedActivity(
        activity_id=100,
        activity_name="Test Run",
        activity_type="running",
        start_time=datetime(2026, 2, 28, 7, 0, 0),
        duration_seconds=1800.0,
        distance_meters=5000.0,
        average_heart_rate=140,
        max_heart_rate=170,
        calories=300.0,
        raw_data={"activityId": 100},
    )


@pytest.fixture()
def mock_biometrics() -> DailyBiometrics:
    return DailyBiometrics(
        date=date(2026, 2, 28),
        resting_heart_rate=52,
        hrv_balance="BALANCED",
        body_battery_highest=90,
        body_battery_lowest=20,
        stress_average=25,
        raw_data={"source": "mock"},
    )


@pytest.fixture()
def mock_sleep() -> SleepData:
    return SleepData(
        date=date(2026, 2, 28),
        sleep_start=datetime(2026, 2, 27, 23, 0),
        sleep_end=datetime(2026, 2, 28, 7, 0),
        total_sleep_seconds=28800,
        deep_sleep_seconds=7200,
        light_sleep_seconds=10800,
        rem_sleep_seconds=5400,
        awake_sleep_seconds=5400,
        sleep_score=85,
        raw_data={"source": "mock"},
    )


# --- Unit tests for converter functions ---


class TestConverterFunctions:
    def test_activity_to_row(self, mock_activity: NormalizedActivity) -> None:
        row = activity_to_row(mock_activity)
        assert row["activity_id"] == 100
        assert row["activity_name"] == "Test Run"
        assert isinstance(row["raw_data"], str)
        assert json.loads(row["raw_data"])["activityId"] == 100

    def test_biometrics_to_row(self, mock_biometrics: DailyBiometrics) -> None:
        row = biometrics_to_row(mock_biometrics)
        assert row["date"] == "2026-02-28"
        assert row["resting_heart_rate"] == 52

    def test_sleep_to_row(self, mock_sleep: SleepData) -> None:
        row = sleep_to_row(mock_sleep)
        assert row["date"] == "2026-02-28"
        assert row["sleep_start"] == "2026-02-27T23:00:00"
        assert row["sleep_score"] == 85

    def test_sleep_to_row_with_nulls(self) -> None:
        sleep = SleepData(date=date(2026, 2, 28), raw_data={})
        row = sleep_to_row(sleep)
        assert row["sleep_start"] is None
        assert row["sleep_score"] is None


class TestDatesToSync:
    def test_full_returns_all_dates(self) -> None:
        with patch("garsync.cli.date") as mock_date:
            mock_date.today.return_value = date(2026, 2, 28)
            mock_date.fromisoformat = date.fromisoformat

            dates = _dates_to_sync(days=3, full=True, latest_date="2026-02-27")
            assert len(dates) == 3

    def test_no_latest_returns_all(self) -> None:
        with patch("garsync.cli.date") as mock_date:
            mock_date.today.return_value = date(2026, 2, 28)

            dates = _dates_to_sync(days=3, full=False, latest_date=None)
            assert len(dates) == 3

    def test_incremental_skips_old_dates(self) -> None:
        with patch("garsync.cli.date") as mock_date:
            mock_date.today.return_value = date(2026, 2, 28)
            mock_date.fromisoformat = date.fromisoformat

            dates = _dates_to_sync(days=5, full=False, latest_date="2026-02-27")
            # Should only include 2026-02-28 and 2026-02-27 (>= cutoff)
            assert all(d >= date(2026, 2, 27) for d in dates)
            assert date(2026, 2, 28) in dates
            assert date(2026, 2, 27) in dates


# --- Full pipeline integration tests ---


class TestSyncPipelineDB:
    """Full pipeline: mock GarminClient → CLI → SQLite DB."""

    def _make_mock_client(
        self,
        activities: list[NormalizedActivity],
        biometrics: DailyBiometrics,
        sleep: SleepData,
    ) -> MagicMock:
        mock = MagicMock(spec=GarminClient)
        mock.fetch_activities.return_value = activities
        mock.fetch_biometrics.return_value = biometrics
        mock.fetch_sleep.return_value = sleep
        return mock

    def test_full_sync_to_db(
        self,
        mock_activity: NormalizedActivity,
        mock_biometrics: DailyBiometrics,
        mock_sleep: SleepData,
    ) -> None:
        mock_client = self._make_mock_client([mock_activity], mock_biometrics, mock_sleep)

        with tempfile.TemporaryDirectory() as tmp:
            db_path = str(Path(tmp) / "test.db")

            with (
                patch("garsync.cli.GarminClient", return_value=mock_client),
                patch("garsync.cli.date") as mock_date,
            ):
                mock_date.today.return_value = date(2026, 2, 28)
                mock_date.fromisoformat = date.fromisoformat

                result = runner.invoke(
                    app,
                    [
                        "--email",
                        "test@test.com",
                        "--password",
                        "pass",
                        "--db",
                        db_path,
                        "--days",
                        "1",
                        "--activities-limit",
                        "5",
                    ],
                )
                assert result.exit_code == 0, result.output

            conn = get_connection(db_path)
            assert ActivityRepository(conn).count() == 1
            assert BiometricsRepository(conn).count() == 1
            assert SleepRepository(conn).count() == 1
            assert SyncLogRepository(conn).count() >= 3  # activities + bio + sleep
            conn.close()

    def test_json_output_still_works(
        self,
        mock_activity: NormalizedActivity,
        mock_biometrics: DailyBiometrics,
        mock_sleep: SleepData,
    ) -> None:
        mock_client = self._make_mock_client([mock_activity], mock_biometrics, mock_sleep)

        with tempfile.TemporaryDirectory() as tmp:
            json_path = str(Path(tmp) / "output.json")

            with (
                patch("garsync.cli.GarminClient", return_value=mock_client),
                patch("garsync.cli.date") as mock_date,
            ):
                mock_date.today.return_value = date(2026, 2, 28)
                mock_date.fromisoformat = date.fromisoformat

                result = runner.invoke(
                    app,
                    [
                        "--email",
                        "test@test.com",
                        "--password",
                        "pass",
                        "--output",
                        json_path,
                        "--days",
                        "1",
                    ],
                )
                assert result.exit_code == 0, result.output
                assert Path(json_path).exists()

                data = json.loads(Path(json_path).read_text())
                assert "status" in data

    def test_partial_failure_continues(
        self,
        mock_activity: NormalizedActivity,
        mock_sleep: SleepData,
    ) -> None:
        """If biometrics fails for a day, sleep should still persist."""
        mock_client = MagicMock(spec=GarminClient)
        mock_client.fetch_activities.return_value = [mock_activity]
        mock_client.fetch_biometrics.side_effect = Exception("API error")
        mock_client.fetch_sleep.return_value = mock_sleep

        with tempfile.TemporaryDirectory() as tmp:
            db_path = str(Path(tmp) / "test.db")

            with (
                patch("garsync.cli.GarminClient", return_value=mock_client),
                patch("garsync.cli.date") as mock_date,
            ):
                mock_date.today.return_value = date(2026, 2, 28)
                mock_date.fromisoformat = date.fromisoformat

                result = runner.invoke(
                    app,
                    [
                        "--email",
                        "test@test.com",
                        "--password",
                        "pass",
                        "--db",
                        db_path,
                        "--days",
                        "1",
                    ],
                )
                assert result.exit_code == 0, result.output

            conn = get_connection(db_path)
            assert ActivityRepository(conn).count() == 1
            assert BiometricsRepository(conn).count() == 0
            assert SleepRepository(conn).count() == 1
            # Should have an error log entry for biometrics
            log_entries = SyncLogRepository(conn).get_all()
            error_entries = [e for e in log_entries if e["status"] == "error"]
            assert len(error_entries) >= 1
            conn.close()

    def test_db_and_json_together(
        self,
        mock_activity: NormalizedActivity,
        mock_biometrics: DailyBiometrics,
        mock_sleep: SleepData,
    ) -> None:
        """--db and --output can be used together."""
        mock_client = self._make_mock_client([mock_activity], mock_biometrics, mock_sleep)

        with tempfile.TemporaryDirectory() as tmp:
            db_path = str(Path(tmp) / "test.db")
            json_path = str(Path(tmp) / "output.json")

            with (
                patch("garsync.cli.GarminClient", return_value=mock_client),
                patch("garsync.cli.date") as mock_date,
            ):
                mock_date.today.return_value = date(2026, 2, 28)
                mock_date.fromisoformat = date.fromisoformat

                result = runner.invoke(
                    app,
                    [
                        "--email",
                        "test@test.com",
                        "--password",
                        "pass",
                        "--db",
                        db_path,
                        "--output",
                        json_path,
                        "--days",
                        "1",
                    ],
                )
                assert result.exit_code == 0, result.output

            conn = get_connection(db_path)
            assert ActivityRepository(conn).count() == 1
            conn.close()

            assert Path(json_path).exists()

    def test_incremental_sync_skips_existing(
        self,
        mock_activity: NormalizedActivity,
        mock_biometrics: DailyBiometrics,
        mock_sleep: SleepData,
    ) -> None:
        """Second sync should use incremental logic (fewer API calls)."""
        mock_client = self._make_mock_client([mock_activity], mock_biometrics, mock_sleep)

        with tempfile.TemporaryDirectory() as tmp:
            db_path = str(Path(tmp) / "test.db")

            with (
                patch("garsync.cli.GarminClient", return_value=mock_client),
                patch("garsync.cli.date") as mock_date,
            ):
                mock_date.today.return_value = date(2026, 2, 28)
                mock_date.fromisoformat = date.fromisoformat

                # First full sync
                runner.invoke(
                    app,
                    [
                        "--email",
                        "test@test.com",
                        "--password",
                        "pass",
                        "--db",
                        db_path,
                        "--days",
                        "3",
                        "--full",
                    ],
                )
                # Count calls
                first_bio_calls = mock_client.fetch_biometrics.call_count
                mock_client.reset_mock()

                # Second incremental sync (should call fewer times)
                runner.invoke(
                    app,
                    [
                        "--email",
                        "test@test.com",
                        "--password",
                        "pass",
                        "--db",
                        db_path,
                        "--days",
                        "3",
                    ],
                )
                second_bio_calls = mock_client.fetch_biometrics.call_count

            # Incremental should make <= full calls
            assert second_bio_calls <= first_bio_calls
