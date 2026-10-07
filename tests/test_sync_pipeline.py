"""Integration tests for the full sync pipeline with mocked GarminClient."""

import json
import re
import sqlite3
import tempfile
from datetime import UTC, date, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from garsync.cli import _dates_to_sync, app
from garsync.client import GarminClient
from garsync.db import (
    ActivityRepository,
    BiometricsRepository,
    IngestRunRepository,
    SleepRepository,
    get_connection,
    init_db,
)
from garsync.models import DailyBiometrics, NormalizedActivity, SleepData
from garsync.pipeline import SyncService, activity_to_row, biometrics_to_row, sleep_to_row

pytestmark = pytest.mark.unit

runner = CliRunner()


# --- Fixtures ---


@pytest.fixture()
def mock_activity() -> NormalizedActivity:
    return NormalizedActivity(
        activity_id=100,
        activity_name="Test Run",
        activity_type="running",
        start_time=datetime(2026, 2, 28, 7, 0, 0, tzinfo=UTC),
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
        sleep_start=datetime(2026, 2, 27, 23, 0, tzinfo=UTC),
        sleep_end=datetime(2026, 2, 28, 7, 0, tzinfo=UTC),
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
        assert row["sleep_start"] == "2026-02-27T23:00:00Z"
        assert row["sleep_score"] == 85

    def test_sleep_to_row_with_nulls(self) -> None:
        sleep = SleepData(date=date(2026, 2, 28), raw_data={})
        row = sleep_to_row(sleep)
        assert row["sleep_start"] is None
        assert row["sleep_score"] is None


class TestDatesToSync:
    def test_full_returns_all_dates(self) -> None:
        with patch("garsync.cli.datetime") as mock_datetime:
            mock_datetime.now.return_value = datetime(2026, 2, 28, 12, 0, 0, tzinfo=UTC)

            dates = _dates_to_sync(days=3, full=True, latest_date="2026-02-27")
            assert len(dates) == 3

    def test_no_latest_returns_all(self) -> None:
        with patch("garsync.cli.datetime") as mock_datetime:
            mock_datetime.now.return_value = datetime(2026, 2, 28, 12, 0, 0, tzinfo=UTC)

            dates = _dates_to_sync(days=3, full=False, latest_date=None)
            assert len(dates) == 3

    def test_incremental_skips_old_dates(self) -> None:
        with patch("garsync.cli.datetime") as mock_datetime:
            mock_datetime.now.return_value = datetime(2026, 2, 28, 12, 0, 0, tzinfo=UTC)

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
                patch("garsync.cli.datetime") as mock_datetime,
            ):
                mock_datetime.now.return_value = datetime(2026, 2, 28, 12, 0, 0, tzinfo=UTC)

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
            assert IngestRunRepository(conn).count() >= 3  # activities + bio + sleep
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
                patch("garsync.cli.datetime") as mock_datetime,
            ):
                mock_datetime.now.return_value = datetime(2026, 2, 28, 12, 0, 0, tzinfo=UTC)

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
                patch("garsync.cli.datetime") as mock_datetime,
            ):
                mock_datetime.now.return_value = datetime(2026, 2, 28, 12, 0, 0, tzinfo=UTC)

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
            log_entries = IngestRunRepository(conn).get_all()
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
                patch("garsync.cli.datetime") as mock_datetime,
            ):
                mock_datetime.now.return_value = datetime(2026, 2, 28, 12, 0, 0, tzinfo=UTC)

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
                patch("garsync.cli.datetime") as mock_datetime,
            ):
                mock_datetime.now.return_value = datetime(2026, 2, 28, 12, 0, 0, tzinfo=UTC)

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


# --- The run: fetch outside, write inside (AC1, AC4, AC5) ---
#
# These drive `SyncService` directly rather than through the CLI: the properties are about the
# transaction and the ledger, and a CLI round-trip would freeze the clock but not the connection.


#: 12:00Z is 13:00 in Madrid on 1 March 2026 — midday, and two weeks clear of the DST change, so the
#: local day the daily window names is the same day no matter which side of the arithmetic reads it.
RUN_INSTANT = datetime(2026, 3, 1, 12, 0, 0, tzinfo=UTC)
RUN_DAY = date(2026, 3, 1)
LATER_INSTANT = datetime(2026, 3, 5, 12, 0, 0, tzinfo=UTC)


class _StubClient:
    """A `GarminClient` that answers from memory, and can look at the connection while it is called.

    `on_call` runs *inside* a fetch, which is the only moment where "no lock is held across the fetch"
    can be observed rather than asserted from the code's shape.
    """

    def __init__(
        self,
        activities: list[NormalizedActivity] | None = None,
        biometrics: DailyBiometrics | None = None,
        sleep: SleepData | None = None,
        on_call: object | None = None,
        fail: str | None = None,
    ) -> None:
        self._activities = activities or []
        self._biometrics = biometrics
        self._sleep = sleep
        self._on_call = on_call
        self._fail = fail
        self.calls: list[str] = []

    def _note(self, name: str) -> None:
        self.calls.append(name)
        if self._fail == name:
            raise RuntimeError(f"{name} refused")
        hook = self._on_call
        if hook is not None:
            assert callable(hook)
            hook()

    def fetch_activities(self, limit: int = 100) -> list[NormalizedActivity]:
        self._note("activities")
        return self._activities

    def fetch_biometrics(self, day: date) -> DailyBiometrics:
        self._note("biometrics")
        assert self._biometrics is not None
        return self._biometrics

    def fetch_sleep(self, day: date) -> SleepData:
        self._note("sleep")
        assert self._sleep is not None
        return self._sleep


def _database(tmp_path: Path) -> sqlite3.Connection:
    """A file database with the chain applied — a file, because AC5 needs a second connection."""
    conn = get_connection(str(tmp_path / "run.db"))
    init_db(conn)
    return conn


def _service(conn: sqlite3.Connection, client: object, now: datetime = RUN_INSTANT) -> SyncService:
    assert isinstance(client, _StubClient)
    return SyncService(client, conn, now=lambda: now)  # type: ignore[arg-type]


class TestNoLockAcrossTheFetch:
    """AC5 — `BEGIN IMMEDIATE` takes the write lock, so opening it before the fetch would hold it for
    every one of the ≈71 calls the daily window makes. The lock and the network must never overlap."""

    def test_the_fetch_observes_no_open_transaction(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mock_activity: NormalizedActivity
    ) -> None:
        monkeypatch.setenv("GARSYNC_TZ", "Europe/Madrid")
        conn = _database(tmp_path)
        seen: list[bool] = []
        client = _StubClient(
            activities=[mock_activity], on_call=lambda: seen.append(conn.in_transaction)
        )
        _service(conn, client).sync_range([RUN_DAY])

        assert seen, "the run fetched nothing, so the assertion measured nothing"
        assert set(seen) == {False}, "a fetch ran inside an open transaction"

    def test_a_second_writer_commits_while_the_run_is_fetching(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        mock_biometrics: DailyBiometrics,
        mock_sleep: SleepData,
    ) -> None:
        """The proof, not the shape: another connection writes during the fetch and is not blocked."""
        monkeypatch.setenv("GARSYNC_TZ", "Europe/Madrid")
        path = str(tmp_path / "run.db")
        conn = _database(tmp_path)
        outcome: list[str] = []

        def probe() -> None:
            other = get_connection(path)
            try:
                other.execute("PRAGMA busy_timeout=0")  # fail at once; waiting 5 s is not the point
                other.execute(
                    "INSERT INTO ingest_run (source, sync_type, rows_upserted) "
                    "VALUES ('probe', 'probe', 0)"
                )
                other.commit()
                outcome.append("committed")
            except sqlite3.OperationalError as error:
                outcome.append(f"locked: {error}")
            finally:
                other.close()

        client = _StubClient(biometrics=mock_biometrics, sleep=mock_sleep, on_call=probe)
        _service(conn, client).sync_range([RUN_DAY])

        assert outcome and set(outcome) == {"committed"}, outcome
        other = get_connection(path)
        try:
            count = other.execute(
                "SELECT COUNT(*) AS c FROM ingest_run WHERE source='probe'"
            ).fetchone()["c"]
        finally:
            other.close()
        assert count == len(outcome), "the concurrent write did not survive the run"


class TestAtomicRun:
    """AC1 — one run is one transaction: the data and its ledger row become visible together, or not
    at all, and the row that records the failure is the only thing a rollback cannot take back."""

    def test_a_write_failing_mid_run_leaves_zero_data_rows_and_one_error_row(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        mock_activity: NormalizedActivity,
        mock_biometrics: DailyBiometrics,
        mock_sleep: SleepData,
    ) -> None:
        monkeypatch.setenv("GARSYNC_TZ", "Europe/Madrid")
        conn = _database(tmp_path)
        second = NormalizedActivity(
            activity_id=101,
            activity_name="Second",
            activity_type="cycling",
            start_time=datetime(2026, 3, 1, 8, 0, tzinfo=UTC),
            duration_seconds=900.0,
            raw_data={"activityId": 101},
        )
        service = _service(
            conn,
            _StubClient(
                activities=[mock_activity, second],
                biometrics=mock_biometrics,
                sleep=mock_sleep,
            ),
        )

        original = service.activity_repo.upsert
        writes = {"n": 0}

        def fail_the_second_write(row: dict) -> int:
            writes["n"] += 1
            if writes["n"] == 2:
                raise RuntimeError("the database refused the second row")
            return original(row)

        service.activity_repo.upsert = fail_the_second_write  # type: ignore[method-assign]
        results = service.sync_range([RUN_DAY])

        assert writes["n"] == 2, "the injected failure never fired"
        assert ActivityRepository(conn).count() == 0, "a rolled-back run published a row"
        assert conn.in_transaction is False, "the rollback left the transaction open"
        runs = IngestRunRepository(conn).get_all()
        activities_rows = [r for r in runs if r["sync_type"] == "activities"]
        assert [r["status"] for r in activities_rows] == ["error"], (
            "a failed run must write exactly one error row and no success row"
        )
        assert results["errors"] == 1
        assert results["activities"] == 0

    def test_the_error_row_survives_the_rollback_it_records(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mock_activity: NormalizedActivity
    ) -> None:
        """The error row is committed *after* the rollback, in its own unit — so a second connection
        sees the failure even though the data it describes never existed."""
        monkeypatch.setenv("GARSYNC_TZ", "Europe/Madrid")
        path = str(tmp_path / "run.db")
        conn = get_connection(path)
        init_db(conn)
        service = _service(conn, _StubClient(activities=[mock_activity]))

        def refuse(row: dict) -> int:
            raise RuntimeError("every write is refused")

        service.activity_repo.upsert = refuse  # type: ignore[method-assign]
        service.sync_range([RUN_DAY])

        other = get_connection(path)
        try:
            rows = IngestRunRepository(other).get_all()
        finally:
            other.close()
        errors = [r for r in rows if r["status"] == "error" and r["sync_type"] == "activities"]
        assert len(errors) == 1
        assert errors[0]["rows_fetched"] == 1, "the run knew what it fetched, and said so"
        assert errors[0]["rows_upserted"] == 0

    def test_a_successful_run_commits_its_ledger_row_with_its_data(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        mock_activity: NormalizedActivity,
        mock_biometrics: DailyBiometrics,
        mock_sleep: SleepData,
    ) -> None:
        """At the instant the success row is written, a reader still sees neither it nor the data."""
        monkeypatch.setenv("GARSYNC_TZ", "Europe/Madrid")
        path = str(tmp_path / "run.db")
        conn = get_connection(path)
        init_db(conn)
        service = _service(
            conn,
            _StubClient(activities=[mock_activity], biometrics=mock_biometrics, sleep=mock_sleep),
        )
        original = service.ingest_run_repo.log
        during: list[tuple[int, int]] = []
        # The storage table each class writes: `sleep` the class is `sleep_sessions` the table.
        table_of = {
            "activities": "activities",
            "daily_metrics": "daily_metrics",
            "sleep": "sleep_sessions",
        }

        def probe_and_log(sync_type: str, *args: object, **kwargs: object) -> None:
            """Per class: at the instant its success row is written, neither it nor its data is visible.

            Keyed on the class because the three runs commit separately — a global count would see the
            previous run's committed rows and read them as a torn write.
            """
            reader = get_connection(path)
            try:
                during.append(
                    (
                        # The key is one of three literals this test writes, never caller input.
                        reader.execute(
                            f"SELECT COUNT(*) AS c FROM {table_of[sync_type]}"
                        ).fetchone()["c"],
                        reader.execute(
                            "SELECT COUNT(*) AS c FROM ingest_run WHERE sync_type = ?",
                            (sync_type,),
                        ).fetchone()["c"],
                    )
                )
            finally:
                reader.close()
            original(sync_type, *args, **kwargs)  # type: ignore[arg-type]

        service.ingest_run_repo.log = probe_and_log  # type: ignore[method-assign]
        service.sync_range([RUN_DAY])

        assert during, "the run never wrote a success row, so AC1 was not exercised"
        assert len(during) == 3, "one probe per class run"
        assert set(during) == {(0, 0)}, (
            "a reader saw part of a run: its data and its ledger row must commit together"
        )
        assert ActivityRepository(conn).count() == 1
        assert IngestRunRepository(conn).count() >= 1


class TestRunCursors:
    """AC4 at the only place it can be observed — what a run actually stores."""

    def test_the_daily_run_records_the_window_it_covered(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        mock_biometrics: DailyBiometrics,
        mock_sleep: SleepData,
    ) -> None:
        monkeypatch.setenv("GARSYNC_TZ", "Europe/Madrid")
        conn = _database(tmp_path)
        _service(conn, _StubClient(biometrics=mock_biometrics, sleep=mock_sleep)).sync_range(
            [RUN_DAY]
        )

        runs = IngestRunRepository(conn)
        assert runs.last_cursor("garmin", "daily_metrics") == RUN_DAY.isoformat()
        assert runs.last_cursor("garmin", "sleep") == RUN_DAY.isoformat()
        latest = runs.get_latest("daily_metrics")
        assert latest is not None
        assert latest["cursor_before"] == RUN_DAY.isoformat(), (
            "the pair is the window the run covered, not the watermark it started from"
        )

    def test_a_cursor_is_a_day_and_never_the_runs_wall_clock(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        mock_biometrics: DailyBiometrics,
        mock_sleep: SleepData,
    ) -> None:
        """`started_at` carries the clock; the cursor must not. A `HH:MM:SS` in either daily cursor
        means the run wrote its own instant, which is the reading D1 rules out."""
        monkeypatch.setenv("GARSYNC_TZ", "Europe/Madrid")
        conn = _database(tmp_path)
        _service(conn, _StubClient(biometrics=mock_biometrics, sleep=mock_sleep)).sync_range(
            [RUN_DAY]
        )

        for sync_type in ("daily_metrics", "sleep"):
            row = IngestRunRepository(conn).get_latest(sync_type)
            assert row is not None
            for column in ("cursor_before", "cursor_after"):
                value = row[column]
                if value is not None:
                    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", value), (
                        f"{sync_type}.{column}: {value}"
                    )
            assert "T" not in row["cursor_after"]
            assert "T" in row["started_at"], "started_at is the clock, and it should read like it"

    def test_a_second_run_over_an_unchanged_window_claims_coverage_without_claiming_changes(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        mock_biometrics: DailyBiometrics,
        mock_sleep: DailyBiometrics,
    ) -> None:
        """The two axes AC4 separates, in one run pair: the data did not change, the coverage did.

        A 1-day floor closes a 4-day gap one new unit per run, re-covering the cursor's own day as the
        seam (`MIN_CHUNK_UNITS`: a chunk of one unit would advance nothing). So the second run reports
        the seam day *and* the next one, advances the watermark by exactly one, and still claims zero
        changed rows — which is the property a record-value cursor cannot have, since a rest day would
        never move it.
        """
        monkeypatch.setenv("GARSYNC_TZ", "Europe/Madrid")
        conn = _database(tmp_path)
        client = _StubClient(biometrics=mock_biometrics, sleep=mock_sleep)
        _service(conn, client).sync_range([RUN_DAY])
        first = IngestRunRepository(conn).get_latest("daily_metrics")
        assert first is not None and first["cursor_after"] == RUN_DAY.isoformat()

        _service(conn, client, now=LATER_INSTANT).sync_range([date(2026, 3, 5)])
        second = IngestRunRepository(conn).get_latest("daily_metrics")
        assert second is not None
        assert second["cursor_after"] == "2026-03-02", (
            "a chunked run must advance by exactly one new unit at a one-day floor, not stall"
        )
        assert second["cursor_before"] == first["cursor_after"], "the window was not continuous"
        assert second["rows_upserted"] == 0, "a re-pull claimed changes it did not make"
        assert second["rows_fetched"] == 2, "the chunk fetched the seam day and one new day"

    def test_the_activities_run_claims_no_cursor(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mock_activity: NormalizedActivity
    ) -> None:
        """Q4: the fetch is `limit`-based, so no coverage claim would be true. SUB-003 owns it."""
        monkeypatch.setenv("GARSYNC_TZ", "Europe/Madrid")
        conn = _database(tmp_path)
        _service(conn, _StubClient(activities=[mock_activity])).sync_range([RUN_DAY])

        row = IngestRunRepository(conn).get_latest("activities")
        assert row is not None, "the activities run writes its ledger row, cursor or no cursor"
        assert row["cursor_after"] is None
        assert row["cursor_before"] is None
        assert row["rows_fetched"] == 1
        assert IngestRunRepository(conn).last_cursor("garmin", "activities") is None

    def test_a_failed_run_leaves_the_cursor_where_it_was(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        mock_biometrics: DailyBiometrics,
        mock_sleep: SleepData,
    ) -> None:
        monkeypatch.setenv("GARSYNC_TZ", "Europe/Madrid")
        conn = _database(tmp_path)
        _service(conn, _StubClient(biometrics=mock_biometrics, sleep=mock_sleep)).sync_range(
            [RUN_DAY]
        )

        broken = _StubClient(biometrics=mock_biometrics, sleep=mock_sleep, fail="biometrics")
        _service(conn, broken, now=LATER_INSTANT).sync_range([date(2026, 3, 5)])

        assert IngestRunRepository(conn).last_cursor("garmin", "daily_metrics") == "2026-03-01", (
            "a run that rolled back advanced the watermark"
        )
        failed = IngestRunRepository(conn).get_latest("daily_metrics")
        assert failed is not None and failed["status"] == "error"


class TestActivityRowTimestamp:
    """The UTC rule the migration exists for, on the ingest path rather than the migration itself."""

    def test_the_offset_is_read_from_the_payload_not_from_a_zone(
        self, mock_activity: NormalizedActivity
    ) -> None:
        """`startTimeGMT` is Garmin's absolute spelling; `start_time` is its *local* one.

        The measured history spans two zones (-420 and -480), so a configured default would have been
        hours wrong on some rows and no fixture would have caught it (ADR-009, `0002`'s pre-flight).
        """
        stamped = NormalizedActivity(
            activity_id=200,
            activity_name="Mountain",
            activity_type="hiking",
            start_time=datetime(2026, 2, 28, 7, 0, tzinfo=UTC),
            duration_seconds=3600.0,
            raw_data={
                "activityId": 200,
                "startTimeGMT": "2026-02-28 14:00:00",
                "startTimeLocal": "2026-02-28 07:00:00",
            },
        )
        row = activity_to_row(stamped)
        assert row["start_time"] == "2026-02-28T14:00:00Z"
        assert row["tz_offset_minutes"] == -420
        # The owner's zone would have said -60 (Madrid in February); the payload said -420. Reading
        # the row rather than the setting is the whole point of the column.
        assert row["tz_offset_minutes"] != -60
