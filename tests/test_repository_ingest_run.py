"""Tests for IngestRunRepository — append-only ingest ledger."""

import sqlite3

import pytest

from garsync.db.repository import IngestRunRepository

pytestmark = pytest.mark.unit


class TestIngestRunRepository:
    def test_log_success(self, in_memory_db: sqlite3.Connection) -> None:
        repo = IngestRunRepository(in_memory_db)
        repo.log("activities", rows_upserted=10)

        row = repo.get_latest()
        assert row is not None
        assert row["sync_type"] == "activities"
        assert row["rows_upserted"] == 10
        assert row["status"] == "success"
        assert row["error_message"] is None

    def test_log_error(self, in_memory_db: sqlite3.Connection) -> None:
        repo = IngestRunRepository(in_memory_db)
        repo.log("biometrics", rows_upserted=0, status="error", error_message="API timeout")

        row = repo.get_latest()
        assert row is not None
        assert row["status"] == "error"
        assert row["error_message"] == "API timeout"

    def test_get_latest_by_type(self, in_memory_db: sqlite3.Connection) -> None:
        repo = IngestRunRepository(in_memory_db)
        repo.log("activities", rows_upserted=5)
        repo.log("biometrics", rows_upserted=3)
        repo.log("activities", rows_upserted=10)

        latest_activities = repo.get_latest(sync_type="activities")
        assert latest_activities is not None
        assert latest_activities["rows_upserted"] == 10

        latest_bio = repo.get_latest(sync_type="biometrics")
        assert latest_bio is not None
        assert latest_bio["rows_upserted"] == 3

    def test_get_latest_empty(self, in_memory_db: sqlite3.Connection) -> None:
        repo = IngestRunRepository(in_memory_db)
        assert repo.get_latest() is None

    def test_get_all(self, in_memory_db: sqlite3.Connection) -> None:
        repo = IngestRunRepository(in_memory_db)
        repo.log("activities", rows_upserted=5)
        repo.log("biometrics", rows_upserted=3)

        entries = repo.get_all()
        assert len(entries) == 2

    def test_count(self, in_memory_db: sqlite3.Connection) -> None:
        repo = IngestRunRepository(in_memory_db)
        assert repo.count() == 0
        repo.log("activities", rows_upserted=5)
        repo.log("sleep", rows_upserted=1)
        assert repo.count() == 2

    def test_append_only(self, in_memory_db: sqlite3.Connection) -> None:
        """Entries are never overwritten — each log() creates a new row."""
        repo = IngestRunRepository(in_memory_db)
        repo.log("activities", rows_upserted=5)
        repo.log("activities", rows_upserted=10)
        repo.log("activities", rows_upserted=15)

        entries = repo.get_all()
        assert len(entries) == 3
        counts = [e["rows_upserted"] for e in entries]
        assert counts == [15, 10, 5]  # DESC order


DAY_CURSOR = "2026-03-01"
PREVIOUS_DAY_CURSOR = "2026-02-28"


class TestCursors:
    """AC4 — the cursor is a coverage watermark, read by ledger `id`.

    Four properties, each of which a naive implementation gets wrong:

    * a run that fetched nothing still advances the cursor (coverage is a property of the window, not
      of the records found inside it — a rest day is covered too);
    * a failed run never advances it, **even if its row carries a cursor**, which is why the filter is
      on `status` and not on the column's presence;
    * the newest row wins by `id`, never by `created_at` (ADR-008 §8: `created_at`'s resolution can tie
      two logical states, so an ordering that reads it is a coin flip);
    * the axis is `(source, sync_type)`: another class's cursor, or another source's, is not this one's.
    """

    def test_a_run_that_fetched_nothing_still_advances_the_cursor(
        self, in_memory_db: sqlite3.Connection
    ) -> None:
        repo = IngestRunRepository(in_memory_db)
        repo.log("daily_metrics", 0, rows_fetched=0, cursor_before=None, cursor_after=DAY_CURSOR)
        assert repo.last_cursor("garmin", "daily_metrics") == DAY_CURSOR, (
            "an empty window was treated as not covered"
        )

    def test_a_failed_run_does_not_advance_the_cursor(
        self, in_memory_db: sqlite3.Connection
    ) -> None:
        repo = IngestRunRepository(in_memory_db)
        repo.log("daily_metrics", 0, rows_fetched=1, cursor_after=DAY_CURSOR)
        repo.log(
            "daily_metrics",
            0,
            "error",
            "rate limited",
            cursor_after=PREVIOUS_DAY_CURSOR,
        )
        assert repo.last_cursor("garmin", "daily_metrics") == DAY_CURSOR

    def test_an_error_row_carrying_a_cursor_is_ignored_not_trusted(
        self, in_memory_db: sqlite3.Connection
    ) -> None:
        """The failure above could be an accident of the writer; this one makes it a rule.

        A cursor written by a rolled-back run claims coverage that database never took, so `status`
        decides, whatever the cursor columns say.
        """
        repo = IngestRunRepository(in_memory_db)
        repo.log("sleep", 0, "error", "boom", cursor_after="2026-03-05")
        assert repo.last_cursor("garmin", "sleep") is None

    def test_the_newest_row_wins_by_id_not_by_created_at(
        self, in_memory_db: sqlite3.Connection
    ) -> None:
        """A later `created_at` with a lower `id` loses.

        Written as raw SQL on purpose: the clock is what this assertion is about, and a test that got
        its timestamps from `log()` could not produce the inversion (two inserts in one millisecond
        tie, and the tie is the bug).
        """
        in_memory_db.execute(
            "INSERT INTO ingest_run "
            "(source, sync_type, rows_upserted, status, cursor_after, created_at) "
            "VALUES ('garmin', 'stress', 0, 'success', ?, '2026-03-09T10:00:00.000Z')",
            (PREVIOUS_DAY_CURSOR,),
        )
        in_memory_db.execute(
            "INSERT INTO ingest_run "
            "(source, sync_type, rows_upserted, status, cursor_after, created_at) "
            "VALUES ('garmin', 'stress', 0, 'success', ?, '2026-01-02T03:04:05.000Z')",
            (DAY_CURSOR,),
        )
        repo = IngestRunRepository(in_memory_db)
        assert repo.last_cursor("garmin", "stress") == DAY_CURSOR, (
            "the cursor was read by timestamp, which is the ordering E1 saw lie"
        )

    def test_a_cursor_never_leaks_between_classes_or_sources(
        self, in_memory_db: sqlite3.Connection
    ) -> None:
        repo = IngestRunRepository(in_memory_db)
        repo.log("daily_metrics", 0, cursor_after=DAY_CURSOR)
        repo.log("sleep", 0, cursor_after=DAY_CURSOR, source="fitdays")

        assert repo.last_cursor("garmin", "sleep") is None
        assert repo.last_cursor("fitdays", "daily_metrics") is None
        assert repo.last_cursor("fitdays", "sleep") == DAY_CURSOR

    def test_a_legacy_row_is_not_a_cursor(self, in_memory_db: sqlite3.Connection) -> None:
        """`0002` copied v1's rows in with NULL cursors and `source='legacy'`.

        Reading them back as "no coverage recorded" is correct; reading them as coverage zero from
        1970 would erase the gap rule. This asserts the axis, not the era: a legacy row's absence of a
        cursor must not become somebody's watermark.
        """
        in_memory_db.execute(
            "INSERT INTO ingest_run (source, sync_type, rows_upserted, status, created_at) "
            "VALUES ('legacy', 'daily_metrics', 5, 'success', '2026-03-01T00:00:00.000Z')"
        )
        repo = IngestRunRepository(in_memory_db)
        assert repo.last_cursor("garmin", "daily_metrics") is None
        assert repo.last_cursor("legacy", "daily_metrics") is None
