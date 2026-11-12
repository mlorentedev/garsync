"""Idempotent re-ingestion — SUB-002, AC6.

ADR-008 §5: re-running an adapter over an already-ingested window yields zero new rows **and** zero
changed values. These tests prove it on a payload that is *narrower* than the one that produced the row,
because that is the case that loses data today — measured on the real payloads, a re-pull without
`activityTrainingLoad` wrote `training_load 7.5 → None` and `normalized_power 231.0 → None`.

Two rules are asserted here, and they are different rules:

* an identical (or narrower) re-pull executes **no UPDATE at all** — `changes()` is zero, so
  `updated_at` does not move either;
* absence must not reach the database as `NULL` over a known value, because a request can legitimately
  not supply a field (an empty endpoint among the four, a list payload without the derived numbers).
"""

import json
import sqlite3

import pytest

from garsync.db.repository import (
    DAILY_METRICS_PAYLOAD_COLUMNS,
    DERIVED_COLUMNS,
    SLEEP_PAYLOAD_COLUMNS,
    ActivityRepository,
    BiometricsRepository,
    IngestRunRepository,
    SleepRepository,
)
from garsync.ingest.payload import canonical_json


def snapshot(conn: sqlite3.Connection, table: str, key_column: str, key: object) -> dict:
    """Every column of one row, so an unexpected change cannot hide in a column nobody asserted."""
    row = conn.execute(f"SELECT * FROM {table} WHERE {key_column} = ?", (key,)).fetchone()
    return dict(row)


class TestNarrowerRepull:
    """Activities: the class where the loss was measured."""

    def test_an_identical_repull_changes_nothing(
        self, in_memory_db: sqlite3.Connection, sample_activity_row: dict
    ) -> None:
        repo = ActivityRepository(in_memory_db)
        repo.upsert(sample_activity_row)
        before = snapshot(
            in_memory_db, "activities", "activity_id", sample_activity_row["activity_id"]
        )
        assert repo.upsert(dict(sample_activity_row)) == 0, "a re-pull reported a change"
        after = snapshot(
            in_memory_db, "activities", "activity_id", sample_activity_row["activity_id"]
        )
        assert after == before, "updated_at moved on a re-pull that changed nothing"

    def test_a_narrower_repull_does_not_erase_a_known_value(
        self, in_memory_db: sqlite3.Connection, sample_activity_row: dict
    ) -> None:
        repo = ActivityRepository(in_memory_db)
        first = {**sample_activity_row, "training_load": 7.5, "normalized_power": 231.0}
        repo.upsert(first)
        narrower = {**first, "training_load": None, "normalized_power": None}
        assert repo.upsert(narrower) == 0
        stored = repo.get_by_id(first["activity_id"])
        assert stored is not None
        assert stored["training_load"] == 7.5
        assert stored["normalized_power"] == 231.0

    def test_a_real_change_still_lands(
        self, in_memory_db: sqlite3.Connection, sample_activity_row: dict
    ) -> None:
        repo = ActivityRepository(in_memory_db)
        repo.upsert(sample_activity_row)
        assert repo.upsert({**sample_activity_row, "calories": 999.0}) == 1, (
            "the guard swallowed it"
        )
        stored = repo.get_by_id(sample_activity_row["activity_id"])
        assert stored is not None
        assert stored["calories"] == 999.0

    def test_a_value_can_still_arrive_after_null(
        self, in_memory_db: sqlite3.Connection, sample_activity_row: dict
    ) -> None:
        """The carry rule protects a known value; it must not block the first one."""
        repo = ActivityRepository(in_memory_db)
        assert sample_activity_row["training_load"] is None
        assert repo.upsert({**sample_activity_row, "training_load": 7.5}) == 1
        stored = repo.get_by_id(sample_activity_row["activity_id"])
        assert stored is not None
        assert stored["training_load"] == 7.5

    def test_the_carry_set_is_deliberately_narrow_for_activities(
        self, in_memory_db: sqlite3.Connection, sample_activity_row: dict
    ) -> None:
        """Only the columns this request may legitimately omit are carried; the rest can still clear.

        `calories` is a core summary field the list endpoint always carries, so a `None` there is
        Garmin withdrawing a value and it lands. The five derived columns are the measured sparsity
        (`activityTrainingLoad` is absent from 98 of 100 payloads). If that ever changes, this set is
        where it changes — not by widening the rule to every column.
        """
        repo = ActivityRepository(in_memory_db)
        repo.upsert({**sample_activity_row, "calories": 350.0})
        assert repo.upsert({**sample_activity_row, "calories": None}) == 1
        stored = repo.get_by_id(sample_activity_row["activity_id"])
        assert stored is not None
        assert stored["calories"] is None

    def test_a_payload_rewritten_in_another_key_order_is_not_a_change(
        self, in_memory_db: sqlite3.Connection, sample_activity_row: dict
    ) -> None:
        """E6: two serialisations of one payload differ in text and length-equal. Canonical wins."""
        left, right = canonical_json({"b": 1, "a": 2}), canonical_json({"a": 2, "b": 1})
        assert left == right, "the canonical form still depends on key order"
        repo = ActivityRepository(in_memory_db)
        row = {**sample_activity_row, "raw_data": left}
        repo.upsert(row)
        assert repo.upsert({**row, "raw_data": right}) == 0


class TestNarrowerRepullDailyClasses:
    """The daily classes: one of four endpoints can come back empty and null a whole day."""

    def test_an_empty_endpoint_does_not_erase_a_days_values(
        self, in_memory_db: sqlite3.Connection, sample_biometrics_row: dict
    ) -> None:
        repo = BiometricsRepository(in_memory_db)
        repo.upsert(sample_biometrics_row)
        empty = {**{k: None for k in sample_biometrics_row}, "date": sample_biometrics_row["date"]}
        assert repo.upsert(empty) == 0
        stored = repo.get_by_date(sample_biometrics_row["date"])
        assert stored is not None
        assert stored["resting_heart_rate"] == 52
        assert stored["body_battery_highest"] == 95
        assert stored["stress_average"] == 28
        assert stored["hrv_baseline_status"] == "BALANCED"

    def test_an_empty_response_does_not_erase_a_nights_sleep(
        self, in_memory_db: sqlite3.Connection, sample_sleep_row: dict
    ) -> None:
        repo = SleepRepository(in_memory_db)
        repo.upsert(sample_sleep_row)
        empty = {**{k: None for k in sample_sleep_row}, "date": sample_sleep_row["date"]}
        assert repo.upsert(empty) == 0
        stored = repo.get_by_date(sample_sleep_row["date"])
        assert stored is not None
        assert stored["total_sleep_seconds"] == 27000
        assert stored["sleep_score"] == 82

    def test_a_real_daily_change_still_lands(
        self, in_memory_db: sqlite3.Connection, sample_biometrics_row: dict
    ) -> None:
        """The morning revision SC-02 exists for: Garmin revises the night's numbers hours later."""
        repo = BiometricsRepository(in_memory_db)
        repo.upsert(sample_biometrics_row)
        assert repo.upsert({**sample_biometrics_row, "resting_heart_rate": 55}) == 1
        stored = repo.get_by_date(sample_biometrics_row["date"])
        assert stored is not None
        assert stored["resting_heart_rate"] == 55


@pytest.mark.parametrize("column", DERIVED_COLUMNS)
def test_omitting_a_derived_activity_column_does_not_erase_it(
    in_memory_db: sqlite3.Connection, sample_activity_row: dict, column: str
) -> None:
    """The measured sparsity, one column at a time: the list payload often carries none of them."""
    repo = ActivityRepository(in_memory_db)
    seeded = {**sample_activity_row, **dict.fromkeys(DERIVED_COLUMNS, 1.5)}
    repo.upsert(seeded)
    assert repo.upsert({**seeded, column: None}) == 0
    stored = repo.get_by_id(sample_activity_row["activity_id"])
    assert stored is not None
    assert stored[column] == 1.5


@pytest.mark.parametrize("column", DAILY_METRICS_PAYLOAD_COLUMNS)
def test_omitting_one_daily_metric_does_not_erase_it(
    in_memory_db: sqlite3.Connection, sample_biometrics_row: dict, column: str
) -> None:
    """Driven by the same constant the upsert is built from, so a new column cannot slip through.

    A column added to the payload without a decision about absence fails here, instead of silently
    nulling a day on the next run of the 14-day window.
    """
    repo = BiometricsRepository(in_memory_db)
    repo.upsert(sample_biometrics_row)
    assert repo.upsert({**sample_biometrics_row, column: None}) == 0
    stored = repo.get_by_date(sample_biometrics_row["date"])
    assert stored is not None
    assert stored[column] == sample_biometrics_row[column]


@pytest.mark.parametrize("column", SLEEP_PAYLOAD_COLUMNS)
def test_omitting_one_sleep_field_does_not_erase_it(
    in_memory_db: sqlite3.Connection, sample_sleep_row: dict, column: str
) -> None:
    repo = SleepRepository(in_memory_db)
    repo.upsert(sample_sleep_row)
    assert repo.upsert({**sample_sleep_row, column: None}) == 0
    stored = repo.get_by_date(sample_sleep_row["date"])
    assert stored is not None
    assert stored[column] == sample_sleep_row[column]


#: The instants a synthetic run is pinned to. `started_at` is captured *before* the fetch and
#: `created_at` is the commit instant (the finish), so they must never be the same value, and
#: `cursor_after` is the coverage watermark, which sits behind the clock by the settle lag.
RUN_STARTED_AT = "2026-09-25T06:00:00.000Z"
WINDOW_END = "2026-09-25T05:15:00.000Z"
WINDOW_START = "2026-09-11T05:15:00.000Z"


class TestLedgerCounts:
    """AC7 — the ledger reports two different numbers, read back from the row it wrote.

    v1 recorded one count for two different facts (ADR-008 §5): `records_synced` was what the adapter
    returned, so a run that changed nothing still claimed to have synced 100 records. `rows_fetched`
    and `rows_upserted` are separate columns now, and the assertion is taken from the ledger row rather
    than from the caller's arithmetic, because the caller's arithmetic is the thing under test.
    """

    @staticmethod
    def _activity(sample: dict, n: int, **overrides: object) -> dict:
        """A distinct activity, so a batch of them does not collide on (source, source_id)."""
        return {**sample, "activity_id": 900 + n, "source_id": str(900 + n), **overrides}

    def test_a_run_with_one_changed_row_and_several_unchanged_ones_counts_one(
        self, in_memory_db: sqlite3.Connection, sample_activity_row: dict
    ) -> None:
        repo = ActivityRepository(in_memory_db)
        ledger = IngestRunRepository(in_memory_db)
        stored = [self._activity(sample_activity_row, n) for n in range(4)]
        for row in stored:
            repo.upsert(row)

        # The re-pull: three identical, one revised. Garmin does revise a finished activity's calories.
        fetched = [*stored[:3], {**stored[3], "calories": 600.0}]
        changed = sum(repo.upsert(row) for row in fetched)
        ledger.log("activities", changed, rows_fetched=len(fetched), started_at=RUN_STARTED_AT)

        row = ledger.get_latest("activities")
        assert row is not None
        assert row["rows_upserted"] == 1, "the ledger counted re-fetched rows as changed ones"
        assert row["rows_fetched"] == 4, "the ledger lost what the adapter actually returned"
        assert row["started_at"] == RUN_STARTED_AT

    def test_the_first_pass_over_pre_existing_rows_may_canonicalise_and_the_second_is_zero(
        self, in_memory_db: sqlite3.Connection, sample_activity_row: dict
    ) -> None:
        """The declared landing cost of canonical `raw_data`, measured in the ledger (AC7).

        Rows written before the canonical spelling existed differ in *text* from the rows the first
        SUB-002 run writes, so pass 1 legitimately reports changes. Pass 2 is the one that proves
        idempotency, and the ledger has to be able to tell those two passes apart.
        """
        repo = ActivityRepository(in_memory_db)
        ledger = IngestRunRepository(in_memory_db)
        payload = {"activityId": 903, "source": "test", "b": 1, "a": 2}
        # Pre-canonical spelling: `json.dumps` default separators and insertion order.
        stored = [
            self._activity(sample_activity_row, n, raw_data=json.dumps(payload)) for n in range(3)
        ]
        for row in stored:
            repo.upsert(row)

        canonical = [{**row, "raw_data": canonical_json(payload)} for row in stored]
        counts = []
        for pass_number, expected in (("first", 3), ("second", 0)):
            changed = sum(repo.upsert(row) for row in canonical)
            assert changed == expected, f"the {pass_number} pass reported {changed} changes"
            ledger.log(
                "activities", changed, rows_fetched=len(canonical), started_at=RUN_STARTED_AT
            )
            counts.append(changed)
        assert counts == [3, 0], "the canonicalisation cost is not a one-off landing"

        rows = ledger.get_all(limit=2)  # newest first: the ledger is append-only
        assert len(rows) == 2, "two passes must leave two rows, or they cannot be compared"
        assert (rows[0]["rows_upserted"], rows[1]["rows_upserted"]) == (0, 3), (
            "the second pass must report zero while the first reports the landing cost"
        )
        assert rows[0]["rows_fetched"] == rows[1]["rows_fetched"] == 3

    def test_a_caller_that_did_not_capture_started_at_leaves_it_null(
        self, in_memory_db: sqlite3.Connection
    ) -> None:
        """`started_at` has no server default, and that is the point (AC12).

        A `CURRENT_TIMESTAMP` default would stamp the ledger row's *insert* instant — the end of the
        run — into the column that means the beginning of it, and every duration read off the ledger
        would be the write's own latency. Omitting it says "this run did not measure its start", which
        is what the pre-SUB-002 callers genuinely are.
        """
        ledger = IngestRunRepository(in_memory_db)
        ledger.log("activities", rows_upserted=0)
        row = ledger.get_latest("activities")
        assert row is not None
        assert row["started_at"] is None, "started_at arrived from a default, not from the run"
        assert row["created_at"] is not None, "the commit instant is still recorded"
        assert row["rows_fetched"] == 0

    def test_the_covered_window_is_written_with_the_row(
        self, in_memory_db: sqlite3.Connection
    ) -> None:
        """The cursor columns exist since `0002` and were never written; the ledger owns them here.

        Which row *is* the cursor for a class — `status='success'`, ordered by `id` — is block 5's
        assertion; this one only proves the write lands and that a run reporting nothing can still
        declare the window it covered (AC9's "asked, nothing yet").
        """
        ledger = IngestRunRepository(in_memory_db)
        ledger.log(
            "biometrics",
            0,
            rows_fetched=0,
            started_at=RUN_STARTED_AT,
            cursor_before=WINDOW_START,
            cursor_after=WINDOW_END,
        )
        row = ledger.get_latest("biometrics")
        assert row is not None
        assert (row["rows_fetched"], row["rows_upserted"]) == (0, 0)
        assert row["cursor_before"] == WINDOW_START
        assert row["cursor_after"] == WINDOW_END
        assert row["status"] == "success"
