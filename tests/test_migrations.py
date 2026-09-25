"""Tests for the Alembic migration chain — the seam, the v1→v2 transformation, and the rehearsal.

The v1 *from* state is built from `tests/fixtures/schema_v1.sql`, a frozen copy of the DDL that
created it. Importing the real DDL would make the test depend on the code the migration exists to
replace, and a migration whose "before" moves with its "after" proves nothing.
"""

import hashlib
import json
import shutil
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from garsync.db.backup import snapshot, snapshot_path
from garsync.db.connection import get_connection
from garsync.db.schema import V1_BASELINE_REVISION, downgrade, init_db, migrate, open_database

pytestmark = pytest.mark.unit

V1_FIXTURE = Path(__file__).parent / "fixtures" / "schema_v1.sql"
REAL_DATABASE = Path(__file__).parents[1] / "data" / "garsync.db"

# Hand-computed expectations. The offsets are the two the real database actually contains (Garmin
# timeZoneId 153 → -420 and 121 → -480), plus a DST fold where the local string alone is ambiguous
# and only the payload's GMT value can settle it.
SUMMER = {  # local -420
    "activity_id": 1,
    "local": "2026-01-10 21:48:59",
    "gmt": "2026-01-11 04:48:59",
    "offset_minutes": -420,
    "utc": "2026-01-11T04:48:59Z",
}
PACIFIC = {  # local -480
    "activity_id": 2,
    "local": "2026-02-01 09:00:00",
    "gmt": "2026-02-01 17:00:00",
    "offset_minutes": -480,
    "utc": "2026-02-01T17:00:00Z",
}
DST_FOLD = {  # 2026-11-01 01:30 local is ambiguous; the GMT value decides it (-360, not -420)
    "activity_id": 3,
    "local": "2026-11-01 01:30:00",
    "gmt": "2026-11-01 07:30:00",
    "offset_minutes": -360,
    "utc": "2026-11-01T07:30:00Z",
}
CASES = (SUMMER, PACIFIC, DST_FOLD)

DERIVED_COLUMNS = ("training_load", "aerobic_te", "anaerobic_te", "normalized_power", "avg_power")

V1_ACTIVITIES_TABLE = "activities"
V1_BIOMETRICS_TABLE = "biometrics"
V1_SLEEP_TABLE = "sleep"
V1_SYNC_LOG_TABLE = "sync_log"
V2_TABLES = {
    "activities",
    "daily_metrics",
    "sleep_sessions",
    "ingest_run",
    "goals",
    "alembic_version",
}


def epoch_ms(gmt: str) -> int:
    """Epoch milliseconds for a `YYYY-MM-DD HH:MM:SS` UTC string, as Garmin reports it."""
    parsed = datetime.strptime(gmt, "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)
    return int(parsed.timestamp() * 1000)


def activity_payload(case: dict, **extra: object) -> dict:
    """A Garmin activity payload carrying the fields the migration reads."""
    payload: dict[str, object] = {
        "activityId": case["activity_id"],
        "activityName": f"Run {case['activity_id']}",
        "activityType": "running",
        "startTimeLocal": case["local"],
        "startTimeGMT": case["gmt"],
        "beginTimestamp": epoch_ms(str(case["gmt"])),
        "duration": 1800.0,
        "distance": 5000.0,
        "averageHR": 145,
        "maxHR": 172,
        "calories": 350.0,
        "aerobicTrainingEffect": 3.2,
        "anaerobicTrainingEffect": 0.8,
    }
    payload.update(extra)
    return payload


def build_v1_database(path: Path) -> sqlite3.Connection:
    """Create a v1 database at `path` from the frozen fixture DDL.

    The version row is written because that is what a v1 database created by `init_db` actually
    holds — `schema_version` is how `init_db` recognises it, and a fixture without the row would be
    a database this project has never produced.
    """
    conn = get_connection(str(path))
    conn.executescript(V1_FIXTURE.read_text())
    conn.execute("INSERT INTO schema_version (version) VALUES (1)")
    conn.commit()
    return conn


def seed_v1_activity(conn: sqlite3.Connection, case: dict, **extra: object) -> None:
    payload = activity_payload(case, **extra)
    conn.execute(
        """
        INSERT INTO activities (activity_id, activity_name, activity_type, start_time,
                                duration_seconds, distance_meters, average_heart_rate,
                                max_heart_rate, calories, raw_data)
        VALUES (?, ?, 'running', ?, 1800.0, 5000.0, 145, 172, 350.0, ?)
        """,
        (case["activity_id"], f"Run {case['activity_id']}", case["local"], json.dumps(payload)),
    )
    conn.commit()


def seed_v1_rows(conn: sqlite3.Connection, cases: tuple[dict, ...] = CASES) -> None:
    """Populate a v1 database with the rows the migration is expected to transform."""
    for case in cases:
        seed_v1_activity(conn, case)
    conn.execute(
        """
        INSERT INTO biometrics (date, resting_heart_rate, hrv_balance, body_battery_highest,
                                body_battery_lowest, stress_average, raw_data)
        VALUES ('2026-02-28', 52, 'BALANCED', 95, 22, 28, ?)
        """,
        (json.dumps({"hrv": [{"hrvSummary": {"baselineStatus": "BALANCED"}}]}),),
    )
    conn.execute(
        """
        INSERT INTO sleep (date, sleep_start, sleep_end, total_sleep_seconds, deep_sleep_seconds,
                           light_sleep_seconds, rem_sleep_seconds, awake_sleep_seconds,
                           sleep_score, raw_data)
        VALUES ('2026-02-28', '2026-02-27T23:15:00+00:00', '2026-02-28T06:45:00+00:00',
                27000, 7200, 10800, 5400, 3600, 82, '{}')
        """
    )
    for sync_type in ("activities", "biometrics", "sleep"):
        conn.execute(
            "INSERT INTO sync_log (sync_type, records_synced, status, error_message) "
            "VALUES (?, ?, 'success', NULL)",
            (sync_type, 3),
        )
    conn.commit()


@pytest.fixture()
def v1_db(tmp_path: Path) -> sqlite3.Connection:
    """A populated v1 database, migrated to v2 by `init_db`."""
    conn = build_v1_database(tmp_path / "v1.db")
    seed_v1_rows(conn)
    init_db(conn)
    yield conn
    conn.close()


def schema_shape(conn: sqlite3.Connection) -> dict[str, dict[str, object]]:
    """The comparable *structure* of a database — what SQLite guarantees, not how it is spelled.

    Declared types, NOT NULL, defaults, primary keys and the columns each index covers. The SQL text
    is deliberately excluded: a table rename rewrites it, so comparing text would compare
    formatting rather than structure. `alembic_version` is excluded too — it is the chain's own
    bookkeeping, and it is asserted separately.
    """
    shape: dict[str, dict[str, object]] = {}
    for table in sorted(table_names(conn) - {"alembic_version"}):
        columns = [
            (row["name"], (row["type"] or "").upper(), row["notnull"], row["dflt_value"], row["pk"])
            for row in conn.execute(f"PRAGMA table_info({table})")
        ]
        indexes = sorted(
            sorted(row["name"] for row in conn.execute(f"PRAGMA index_info({index['name']})"))
            for index in conn.execute(f"PRAGMA index_list({table})")
        )
        foreign_keys = [tuple(row) for row in conn.execute(f"PRAGMA foreign_key_list({table})")]
        shape[table] = {"columns": columns, "indexes": indexes, "foreign_keys": foreign_keys}
    return shape


def primary_key(conn: sqlite3.Connection, table: str) -> list[str]:
    return [row["name"] for row in conn.execute(f"PRAGMA table_info({table})") if row["pk"]]


def table_names(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    return {row["name"] for row in rows}


def columns_of(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}


class TestAlembicSeam:
    """AC1 — Alembic is the only schema creator, and it runs on the caller's connection."""

    def test_init_db_leaves_the_schema_on_the_callers_connection(
        self, in_memory_db: sqlite3.Connection
    ) -> None:
        """A `:memory:` connection must receive the schema itself.

        Alembic's own URL would open a *second* in-memory database, so a chain that fails to use
        the caller's connection yields zero tables here while every other test still passes.
        """
        assert V2_TABLES.issubset(table_names(in_memory_db))

    def test_alembic_version_is_at_head(self, in_memory_db: sqlite3.Connection) -> None:
        head = in_memory_db.execute("SELECT version_num FROM alembic_version").fetchone()
        assert head is not None
        assert head["version_num"]

    def test_schema_version_table_is_gone(self, in_memory_db: sqlite3.Connection) -> None:
        """`schema_version` was the pre-Alembic SSOT; two version tables is one too many."""
        assert "schema_version" not in table_names(in_memory_db)

    def test_fresh_and_migrated_databases_are_identical(
        self, tmp_path: Path, in_memory_db: sqlite3.Connection
    ) -> None:
        migrated = build_v1_database(tmp_path / "legacy.db")
        seed_v1_rows(migrated)
        init_db(migrated)
        try:
            assert schema_shape(migrated) == schema_shape(in_memory_db)
        finally:
            migrated.close()

    def test_the_baseline_reproduces_the_v1_schema(self, tmp_path: Path) -> None:
        """The property that makes `alembic stamp 0001_v1` a fact rather than a hope.

        If the baseline disagreed with what is on disk, stamping a v1 database would record a
        revision it is not on, and the next revision would transform a schema nobody has.
        """
        legacy = build_v1_database(tmp_path / "legacy.db")
        fresh = get_connection(str(tmp_path / "fresh.db"))
        try:
            migrate(fresh, V1_BASELINE_REVISION)
            assert schema_shape(fresh) == schema_shape(legacy)
        finally:
            legacy.close()
            fresh.close()

    def test_ddl_is_only_transactional_inside_an_explicit_transaction(self, tmp_path: Path) -> None:
        """Why `schema.py` takes the `BEGIN` away from the driver and issues it itself.

        In its default mode pysqlite opens a transaction for DML and not for DDL, so a `CREATE`
        outside an explicit `BEGIN` is committed the moment it runs — which is how a revision that
        fails half-way leaves a database that is neither v1 nor v2.
        """
        conn = get_connection(str(tmp_path / "ddl.db"))
        try:
            conn.execute("CREATE TABLE outside (x INTEGER)")
            conn.rollback()
            assert "outside" in table_names(conn)

            conn.execute("BEGIN")
            conn.execute("CREATE TABLE inside (x INTEGER)")
            conn.rollback()
            assert "inside" not in table_names(conn)
        finally:
            conn.close()

    def test_init_db_leaves_the_connection_as_it_found_it(self, tmp_path: Path) -> None:
        """The bridge borrows the caller's connection; it does not quietly re-configure it."""
        conn = build_v1_database(tmp_path / "borrowed.db")
        seed_v1_rows(conn)
        before = conn.isolation_level
        init_db(conn)
        assert conn.isolation_level == before
        assert conn.in_transaction is False
        assert conn.execute("SELECT COUNT(*) FROM activities").fetchone()[0] == len(CASES)
        conn.close()

    def test_an_unrecognised_database_is_refused(self, tmp_path: Path) -> None:
        """Guessing which revision an unknown database is on is how a migration eats a database."""
        conn = get_connection(str(tmp_path / "unknown.db"))
        conn.execute("CREATE TABLE something_else (x INTEGER)")
        conn.commit()
        with pytest.raises(RuntimeError, match="something_else"):
            init_db(conn)
        conn.close()

    def test_upgrading_twice_changes_nothing(self, tmp_path: Path) -> None:
        conn = build_v1_database(tmp_path / "twice.db")
        seed_v1_rows(conn)
        init_db(conn)
        before = schema_shape(conn)
        counts = {
            table: conn.execute(f"SELECT COUNT(*) AS c FROM {table}").fetchone()["c"]
            for table in V2_TABLES
            if table != "alembic_version"
        }
        init_db(conn)
        assert schema_shape(conn) == before
        for table, count in counts.items():
            assert conn.execute(f"SELECT COUNT(*) AS c FROM {table}").fetchone()["c"] == count
        conn.close()

    def test_v2_declares_no_foreign_keys(self, in_memory_db: sqlite3.Connection) -> None:
        """The rebuild mechanics assume it.

        Neither v1 nor v2 declares a foreign key, which is what makes a table recreate safe
        without `PRAGMA foreign_keys=OFF` (a pragma that is silently ineffective inside a
        transaction, and therefore worse than absent). If a foreign key ever arrives, this test
        fails and the migration mechanics have to be revisited deliberately.
        """
        declared = {}
        for table in table_names(in_memory_db):
            keys = in_memory_db.execute(f"PRAGMA foreign_key_list({table})").fetchall()
            if keys:
                declared[table] = [dict(key) for key in keys]
        assert declared == {}


class TestRowPreservation:
    """AC2 — no row is lost, and the legacy table is inert rather than dropped."""

    def test_row_counts_survive(self, v1_db: sqlite3.Connection) -> None:
        assert v1_db.execute("SELECT COUNT(*) AS c FROM activities").fetchone()["c"] == len(CASES)
        assert v1_db.execute("SELECT COUNT(*) AS c FROM daily_metrics").fetchone()["c"] == 1
        assert v1_db.execute("SELECT COUNT(*) AS c FROM sleep_sessions").fetchone()["c"] == 1

    def test_untouched_columns_survive_verbatim(self, v1_db: sqlite3.Connection) -> None:
        row = v1_db.execute(
            "SELECT activity_name, duration_seconds, distance_meters, average_heart_rate, "
            "max_heart_rate, calories FROM activities WHERE activity_id = ?",
            (SUMMER["activity_id"],),
        ).fetchone()
        assert (row["activity_name"], row["duration_seconds"], row["distance_meters"]) == (
            "Run 1",
            1800.0,
            5000.0,
        )
        assert (row["average_heart_rate"], row["max_heart_rate"], row["calories"]) == (
            145,
            172,
            350.0,
        )

    def test_legacy_runs_are_copied_and_flagged(self, v1_db: sqlite3.Connection) -> None:
        runs = v1_db.execute("SELECT * FROM ingest_run ORDER BY id").fetchall()
        assert len(runs) == 3
        assert {run["source"] for run in runs} == {"legacy"}
        assert {run["sync_type"] for run in runs} == {"activities", "biometrics", "sleep"}
        assert all(run["cursor_before"] is None for run in runs)
        assert all(run["rows_upserted"] == 3 for run in runs)

    def test_the_legacy_table_still_holds_its_rows(self, v1_db: sqlite3.Connection) -> None:
        assert v1_db.execute("SELECT COUNT(*) AS c FROM sync_log").fetchone()["c"] == 3

    def test_sync_log_rows_are_not_duplicated_into_ingest_run(self, tmp_path: Path) -> None:
        conn = build_v1_database(tmp_path / "copy.db")
        seed_v1_rows(conn)
        init_db(conn)
        init_db(conn)
        assert conn.execute("SELECT COUNT(*) AS c FROM ingest_run").fetchone()["c"] == 3
        conn.close()

    def test_the_renamed_tables_keep_their_primary_key(self, v1_db: sqlite3.Connection) -> None:
        """A batch recreate that quietly loses a primary key is a schema nobody asked for."""
        assert primary_key(v1_db, "daily_metrics") == ["date"]
        assert primary_key(v1_db, "sleep_sessions") == ["date"]
        assert primary_key(v1_db, "ingest_run") == ["id"]


class TestTimezoneNormalisation:
    """AC3 — UTC at rest, with the offset read per row from the payload and no assumed zone."""

    @pytest.mark.parametrize("case", CASES, ids=[str(c["gmt"]) for c in CASES])
    def test_start_time_and_offset_match_hand_computed_values(
        self, v1_db: sqlite3.Connection, case: dict
    ) -> None:
        row = v1_db.execute(
            "SELECT start_time, tz_offset_minutes FROM activities WHERE activity_id = ?",
            (case["activity_id"],),
        ).fetchone()
        assert row["start_time"] == case["utc"]
        assert row["tz_offset_minutes"] == case["offset_minutes"]

    def test_the_original_local_string_survives_in_raw_data(
        self, v1_db: sqlite3.Connection
    ) -> None:
        raw = v1_db.execute(
            "SELECT raw_data FROM activities WHERE activity_id = ?", (SUMMER["activity_id"],)
        ).fetchone()["raw_data"]
        assert json.loads(raw)["startTimeLocal"] == SUMMER["local"]

    def test_utc_strings_sort_chronologically(self, v1_db: sqlite3.Connection) -> None:
        """The stored form has to order as text, because rollups compare it as text."""
        times = [
            row["start_time"]
            for row in v1_db.execute("SELECT start_time FROM activities ORDER BY start_time")
        ]
        assert times == sorted(times)

    def test_sleep_timestamps_are_normalised(self, v1_db: sqlite3.Connection) -> None:
        row = v1_db.execute("SELECT sleep_start, sleep_end FROM sleep_sessions").fetchone()
        assert row["sleep_start"] == "2026-02-27T23:15:00Z"
        assert row["sleep_end"] == "2026-02-28T06:45:00Z"

    def test_a_payload_without_an_offset_aborts_and_names_the_row(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No default zone exists, so an unreadable offset must stop the migration, not guess."""
        monkeypatch.delenv("GARSYNC_TZ", raising=False)
        conn = build_v1_database(tmp_path / "no-offset.db")
        payload = activity_payload(SUMMER)
        del payload["startTimeGMT"]
        conn.execute(
            "INSERT INTO activities (activity_id, activity_name, start_time, raw_data) "
            "VALUES (?, 'No offset', '2026-01-10 21:48:59', ?)",
            (99, json.dumps(payload)),
        )
        conn.commit()
        with pytest.raises(RuntimeError, match="99"):
            init_db(conn)
        # The revision is transactional: a refused migration leaves the v1 database intact.
        assert "daily_metrics" not in table_names(conn)
        conn.close()

    def test_an_explicitly_configured_zone_resolves_the_straggler(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`GARSYNC_TZ` is a fallback the operator sets on purpose, never a default in the code."""
        monkeypatch.setenv("GARSYNC_TZ", "Europe/Madrid")
        conn = build_v1_database(tmp_path / "fallback.db")
        payload = activity_payload(SUMMER)
        del payload["startTimeGMT"]
        del payload["beginTimestamp"]
        conn.execute(
            "INSERT INTO activities (activity_id, activity_name, start_time, raw_data) "
            "VALUES (?, 'No offset', '2026-01-10 21:48:59', ?)",
            (7, json.dumps(payload)),
        )
        conn.commit()
        init_db(conn)
        row = conn.execute(
            "SELECT start_time, tz_offset_minutes FROM activities WHERE activity_id = 7"
        ).fetchone()
        assert row["start_time"] == "2026-01-10T20:48:59Z"  # Madrid in January is +60
        assert row["tz_offset_minutes"] == 60
        conn.close()


class TestProvenanceAndGaps:
    """AC4 — provenance is explicit, and a value the payload never held stays NULL."""

    def test_every_activity_carries_its_source(self, v1_db: sqlite3.Connection) -> None:
        sources = [row["source"] for row in v1_db.execute("SELECT DISTINCT source FROM activities")]
        assert sources == ["garmin"]

    def test_activity_id_is_still_the_primary_key(self, v1_db: sqlite3.Connection) -> None:
        primary = [
            row["name"] for row in v1_db.execute("PRAGMA table_info(activities)") if row["pk"]
        ]
        assert primary == ["activity_id"]

    def test_source_and_source_id_are_unique_together(self, v1_db: sqlite3.Connection) -> None:
        with pytest.raises(sqlite3.IntegrityError):
            v1_db.execute(
                "INSERT INTO activities (activity_id, source, source_id, activity_name) "
                "VALUES (?, 'garmin', ?, 'Duplicate')",
                (999, str(SUMMER["activity_id"])),
            )

    def test_source_id_is_the_garmin_identifier(self, v1_db: sqlite3.Connection) -> None:
        row = v1_db.execute(
            "SELECT source_id FROM activities WHERE activity_id = ?", (SUMMER["activity_id"],)
        ).fetchone()
        assert row["source_id"] == str(SUMMER["activity_id"])

    def test_the_hrv_string_is_kept_verbatim_and_the_numbers_stay_null(
        self, v1_db: sqlite3.Connection
    ) -> None:
        row = v1_db.execute(
            "SELECT hrv_baseline_status, hrv_last_night_avg, hrv_weekly_avg, hrv_baseline_low, "
            "hrv_baseline_high FROM daily_metrics"
        ).fetchone()
        assert row["hrv_baseline_status"] == "BALANCED"
        assert (
            row["hrv_last_night_avg"],
            row["hrv_weekly_avg"],
            row["hrv_baseline_low"],
            row["hrv_baseline_high"],
        ) == (None, None, None, None)

    def test_derived_columns_come_from_the_payload(self, v1_db: sqlite3.Connection) -> None:
        row = v1_db.execute(
            "SELECT aerobic_te, anaerobic_te, training_load, normalized_power, avg_power "
            "FROM activities WHERE activity_id = ?",
            (SUMMER["activity_id"],),
        ).fetchone()
        assert row["aerobic_te"] == pytest.approx(3.2)
        assert row["anaerobic_te"] == pytest.approx(0.8)
        # The list endpoint does not carry these for most activities; NULL is a reported gap.
        assert row["training_load"] is None
        assert row["normalized_power"] is None
        assert row["avg_power"] is None

    def test_a_backfilled_derived_column_is_reported_as_present(self, tmp_path: Path) -> None:
        conn = build_v1_database(tmp_path / "derived.db")
        seed_v1_rows(conn)
        conn.execute(
            "UPDATE activities SET raw_data = ? WHERE activity_id = ?",
            (
                json.dumps(activity_payload(SUMMER, activityTrainingLoad=88.5)),
                SUMMER["activity_id"],
            ),
        )
        conn.commit()
        init_db(conn)
        row = conn.execute(
            "SELECT training_load FROM activities WHERE activity_id = ?",
            (SUMMER["activity_id"],),
        ).fetchone()
        assert row["training_load"] == pytest.approx(88.5)
        conn.close()

    def test_the_gap_count_is_queryable(self, v1_db: sqlite3.Connection) -> None:
        from garsync.db.repository import ActivityRepository

        gaps = ActivityRepository(v1_db).derived_gap_counts()
        # None of these three payloads carries a training load, and `activityTrainingLoad` is absent
        # from the list endpoint's response for most activities anyway (2 of 100 on the real data).
        assert gaps["training_load"] == len(CASES)
        assert gaps["aerobic_te"] == 0


class TestGoalsAndNoSpeculativeTables:
    """AC5 — `goals` exists, and nothing else was invented along the way."""

    def test_goals_is_keyed_by_valid_from(self, in_memory_db: sqlite3.Connection) -> None:
        primary = [
            row["name"] for row in in_memory_db.execute("PRAGMA table_info(goals)") if row["pk"]
        ]
        assert primary == ["valid_from"]

    def test_goals_carries_the_band_the_body_screen_needs(
        self, in_memory_db: sqlite3.Connection
    ) -> None:
        assert {
            "goal_weight_kg",
            "rate_band_low_kg_per_week",
            "rate_band_high_kg_per_week",
        }.issubset(columns_of(in_memory_db, "goals"))

    def test_a_goal_without_a_start_date_is_refused(self, in_memory_db: sqlite3.Connection) -> None:
        """SQLite lets a TEXT primary key be NULL unless it is told otherwise, and a goal with no
        start date is a goal nothing can be compared against."""
        with pytest.raises(sqlite3.IntegrityError):
            in_memory_db.execute("INSERT INTO goals (valid_from) VALUES (NULL)")

    def test_no_deferred_table_was_created(self, in_memory_db: sqlite3.Connection) -> None:
        forbidden = {
            "activity_streams",
            "raw_payload",
            "metric_registry",
            "nutrition_entries",
            "derived_daily",
            "targets",
            "recommendation_log",
            "weight_measurements",
            "body_composition",
            "auth_audit",
        }
        assert table_names(in_memory_db) & forbidden == set()


class TestTheDowngrade:
    """Forward-only in production (design §4.1) — and honest enough to be exercised here, because an
    untested downgrade is a downgrade that does not work."""

    def test_it_returns_the_v1_shape(self, tmp_path: Path) -> None:
        conn = build_v1_database(tmp_path / "roundtrip.db")
        seed_v1_rows(conn)
        original = schema_shape(conn)
        init_db(conn)
        downgrade(conn, V1_BASELINE_REVISION)
        try:
            assert schema_shape(conn) == original
        finally:
            conn.close()

    def test_it_reconstructs_the_local_start_time(self, tmp_path: Path) -> None:
        """The offset column is what makes the transformation reversible, so removing it has to
        reconstruct what v1 held rather than leave a UTC string wearing a local field's name."""
        conn = build_v1_database(tmp_path / "local.db")
        seed_v1_rows(conn)
        init_db(conn)
        downgrade(conn, V1_BASELINE_REVISION)
        try:
            times = [
                row["start_time"]
                for row in conn.execute("SELECT start_time FROM activities ORDER BY activity_id")
            ]
            assert times == [case["local"].replace(" ", "T") for case in CASES]
        finally:
            conn.close()

    def test_it_keeps_the_rows_and_the_rows_s_own_records(self, tmp_path: Path) -> None:
        conn = build_v1_database(tmp_path / "keep.db")
        seed_v1_rows(conn)
        init_db(conn)
        downgrade(conn, V1_BASELINE_REVISION)
        try:
            assert conn.execute("SELECT COUNT(*) AS c FROM activities").fetchone()["c"] == len(
                CASES
            )
            # `sync_log` kept its own rows throughout, so a downgrade has nothing to restore there.
            assert conn.execute("SELECT COUNT(*) AS c FROM sync_log").fetchone()["c"] == 3
            assert conn.execute("SELECT version FROM schema_version").fetchone()["version"] == 1
        finally:
            conn.close()


class TestTheSnapshotBeforeTheMigration:
    """AC6 — the rule ADR-009 states as an instruction, executed by the code that rewrites the file."""

    def test_a_pending_migration_snapshots_the_file_first(self, tmp_path: Path) -> None:
        db_path = tmp_path / "garsync.db"
        seed_conn = build_v1_database(db_path)
        seed_v1_rows(seed_conn)
        seed_conn.close()

        conn = open_database(str(db_path))
        try:
            snapshots = sorted((tmp_path / "backups").glob("*.db"))
            assert len(snapshots) == 1
            # The snapshot is the database *before* the migration — otherwise it is not a backup, it
            # is a second copy of the thing that may have gone wrong.
            snapshotted = get_connection(str(snapshots[0]))
            try:
                assert "biometrics" in table_names(snapshotted)
                assert "daily_metrics" not in table_names(snapshotted)
            finally:
                snapshotted.close()
            assert "daily_metrics" in table_names(conn)
        finally:
            conn.close()

    def test_a_database_already_at_head_is_not_snapshotted(self, tmp_path: Path) -> None:
        """A backup of a no-op is noise, and noise is how a backups directory stops being read."""
        db_path = tmp_path / "current.db"
        setup_conn = get_connection(str(db_path))
        init_db(setup_conn)
        setup_conn.close()

        conn = open_database(str(db_path))
        conn.close()
        assert not (tmp_path / "backups").exists()

    def test_a_snapshot_refuses_to_overwrite_an_earlier_one(self, tmp_path: Path) -> None:
        db_path = tmp_path / "collide.db"
        conn = get_connection(str(db_path))
        init_db(conn)
        taken_at = datetime(2026, 9, 24, 12, 0, 0, tzinfo=UTC)
        target = snapshot_path(db_path, taken_at)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"an earlier snapshot")
        try:
            with pytest.raises(FileExistsError):
                snapshot(conn, db_path, taken_at)
            assert target.read_bytes() == b"an earlier snapshot"
        finally:
            conn.close()


@pytest.mark.integration
class TestRealDatabaseRehearsal:
    """AC6 — the migration is exercised against a copy, and the original is never the subject."""

    @pytest.fixture()
    def rehearsal_copy(self, tmp_path: Path) -> Path:
        if not REAL_DATABASE.exists():
            pytest.skip(f"{REAL_DATABASE} is absent — nothing to rehearse against")
        copy = tmp_path / "rehearsal.db"
        shutil.copy2(REAL_DATABASE, copy)
        return copy

    def test_the_original_is_untouched(self, rehearsal_copy: Path) -> None:
        before = hashlib.sha256(REAL_DATABASE.read_bytes()).hexdigest()
        conn = get_connection(str(rehearsal_copy))
        init_db(conn)
        conn.close()
        assert hashlib.sha256(REAL_DATABASE.read_bytes()).hexdigest() == before

    def test_real_rows_survive_the_upgrade(self, rehearsal_copy: Path) -> None:
        source = get_connection(str(rehearsal_copy))
        counts = {
            table: source.execute(f"SELECT COUNT(*) AS c FROM {table}").fetchone()["c"]
            for table in ("activities", "biometrics", "sleep", "sync_log")
        }
        source.close()

        conn = get_connection(str(rehearsal_copy))
        init_db(conn)
        try:
            assert (
                conn.execute("SELECT COUNT(*) AS c FROM activities").fetchone()["c"]
                == (counts["activities"])
            )
            assert (
                conn.execute("SELECT COUNT(*) AS c FROM daily_metrics").fetchone()["c"]
                == (counts["biometrics"])
            )
            assert (
                conn.execute("SELECT COUNT(*) AS c FROM sleep_sessions").fetchone()["c"]
                == (counts["sleep"])
            )
            assert (
                conn.execute("SELECT COUNT(*) AS c FROM ingest_run").fetchone()["c"]
                == (counts["sync_log"])
            )
        finally:
            conn.close()

    def test_every_real_activity_gets_a_utc_start_and_its_offset(
        self, rehearsal_copy: Path
    ) -> None:
        conn = get_connection(str(rehearsal_copy))
        init_db(conn)
        try:
            unnormalised = conn.execute(
                "SELECT COUNT(*) AS c FROM activities WHERE start_time IS NOT NULL "
                "AND start_time NOT LIKE '%Z'"
            ).fetchone()["c"]
            without_offset = conn.execute(
                "SELECT COUNT(*) AS c FROM activities WHERE tz_offset_minutes IS NULL"
            ).fetchone()["c"]
            offsets = {
                row["off"]
                for row in conn.execute("SELECT DISTINCT tz_offset_minutes AS off FROM activities")
            }
            assert unnormalised == 0
            assert without_offset == 0
            # Measured before the migration: -420 on 95 rows and -480 on 5 — read, not assumed.
            assert offsets <= {-420, -480}
        finally:
            conn.close()

    def test_the_rehearsal_reports_the_gaps_it_inherits(self, rehearsal_copy: Path) -> None:
        """`activityTrainingLoad` is absent from most list-endpoint payloads, so the metric
        layer has to inherit a measured gap rather than discover it after MET-001 is built."""
        conn = get_connection(str(rehearsal_copy))
        init_db(conn)
        try:
            from garsync.db.repository import ActivityRepository

            gaps = ActivityRepository(conn).derived_gap_counts()
            assert gaps["aerobic_te"] == 0
            assert gaps["training_load"] > 0
            assert gaps["training_load"] > gaps["aerobic_te"]
        finally:
            conn.close()
