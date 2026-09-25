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

import sqlite3

import pytest

from garsync.db.repository import (
    DAILY_METRICS_PAYLOAD_COLUMNS,
    DERIVED_COLUMNS,
    SLEEP_PAYLOAD_COLUMNS,
    ActivityRepository,
    BiometricsRepository,
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
