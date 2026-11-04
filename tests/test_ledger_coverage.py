"""AC9 — SC-02(3)'s two questions, answered from committed rows and nothing else.

The register's clause (3) is that the UI and the digest must tell *"not uploaded yet"* apart from *"no
data"*, and the alert threshold must sit above the normal lateness so a routine late upload never pages.
Before SUB-002 neither question had an answer: v1's ledger recorded that a sync ran, not what it covered,
so "we asked and Garmin had nothing" and "we never asked" were the same database state.

The three states are what these tests hold apart:

| Day D | Committed evidence | Answer |
|---|---|---|
| inside a covered window, the covering run fetched 0 rows, no class row | `ingest_run` | **not uploaded yet** |
| inside a covered window, a covering run fetched rows, no row for D | `ingest_run` + class table | **no data for D** |
| outside every covered window | nothing | **never asked** — which is not an answer about the data |

`rows_fetched=0` is the datum that separates the first two, and it is why AC7's honest count had to land
first: with the legacy `rows_upserted` holding the fetched count, the two questions collapse into one.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from datetime import date

import pytest

from garsync.db.connection import get_connection
from garsync.db.repository import IngestRunRepository
from garsync.db.schema import init_db

START = date(2026, 3, 1)
END = date(2026, 3, 7)
DAY_RANGE = (START, END)


@pytest.fixture()
def conn(tmp_path: object) -> Iterator[sqlite3.Connection]:
    database = get_connection(str(tmp_path / "ledger.db"))  # type: ignore[operator]
    init_db(database)
    try:
        yield database
    finally:
        database.close()


def _run(
    repo: IngestRunRepository,
    before: str,
    after: str,
    *,
    fetched: int = 0,
    status: str = "success",
    source: str = "garmin",
    sync_type: str = "daily_metrics",
) -> None:
    """One successful (or failed) run over one covered window."""
    repo.log(
        sync_type,
        rows_upserted=1 if fetched else 0,
        status=status,
        source=source,
        rows_fetched=fetched,
        cursor_before=before,
        cursor_after=after,
    )


def _metric(conn: sqlite3.Connection, day: str) -> None:
    conn.execute("INSERT INTO daily_metrics (date) VALUES (?)", (day,))
    conn.commit()


class TestThreeStates:
    def test_a_covered_day_whose_run_fetched_nothing_is_not_uploaded_yet(
        self, conn: sqlite3.Connection
    ) -> None:
        """The weigh-in the scale has not sent: we asked over the window, zero records came back."""
        repo = IngestRunRepository(conn)
        _run(repo, "2026-03-01", "2026-03-04", fetched=0)

        assert repo.days_not_uploaded_yet("daily_metrics", *DAY_RANGE) == [
            "2026-03-01",
            "2026-03-02",
            "2026-03-03",
            "2026-03-04",
        ]
        assert repo.days_with_no_data("daily_metrics", *DAY_RANGE) == []

    def test_a_covered_day_absent_from_a_window_that_did_return_rows_has_no_data(
        self, conn: sqlite3.Connection
    ) -> None:
        """A rest day inside a window that produced data is a different fact from a late upload."""
        repo = IngestRunRepository(conn)
        _run(repo, "2026-03-01", "2026-03-04", fetched=3)
        for day in ("2026-03-01", "2026-03-03", "2026-03-04"):
            _metric(conn, day)

        assert repo.days_with_no_data("daily_metrics", *DAY_RANGE) == ["2026-03-02"]
        assert repo.days_not_uploaded_yet("daily_metrics", *DAY_RANGE) == []

    def test_a_day_outside_every_covered_window_is_never_asked(
        self, conn: sqlite3.Connection
    ) -> None:
        """The third state must not be reportable as either answer.

        This is the assertion the alert depends on: a gap in coverage is a bug in the runner, while the
        two ledger answers are facts about the body. Conflating them pages on a holiday.
        """
        repo = IngestRunRepository(conn)
        _run(repo, "2026-03-01", "2026-03-04", fetched=1)
        _metric(conn, "2026-03-01")

        assert repo.covered_days("daily_metrics", *DAY_RANGE) == {
            f"2026-03-{day:02d}" for day in range(1, 5)
        }
        assert repo.days_not_uploaded_yet("daily_metrics", *DAY_RANGE) == []
        assert repo.days_with_no_data("daily_metrics", *DAY_RANGE) == [
            "2026-03-02",
            "2026-03-03",
            "2026-03-04",
        ]
        for day in ("2026-03-05", "2026-03-06", "2026-03-07"):
            assert day not in repo.covered_days("daily_metrics", *DAY_RANGE)
            assert day not in repo.days_not_uploaded_yet("daily_metrics", *DAY_RANGE)
            assert day not in repo.days_with_no_data("daily_metrics", *DAY_RANGE)


class TestWhatMayCoverADay:
    def test_an_error_row_never_covers_a_day(self, conn: sqlite3.Connection) -> None:
        """A run whose data rolled back cannot claim the window it meant to cover (AC1's mirror)."""
        repo = IngestRunRepository(conn)
        _run(repo, "2026-03-01", "2026-03-04", fetched=2, status="error")
        _metric(conn, "2026-03-01")

        assert repo.covered_days("daily_metrics", *DAY_RANGE) == set()
        assert repo.days_not_uploaded_yet("daily_metrics", *DAY_RANGE) == []
        assert repo.days_with_no_data("daily_metrics", *DAY_RANGE) == []

    def test_a_legacy_row_never_covers_a_day(self, conn: sqlite3.Connection) -> None:
        """`source='legacy'` is provenance without measurement, and `rows_fetched=0` there is a default.

        Decision 9: every row copied out of v1 reads `rows_fetched=0` because nobody counted. If those
        rows counted as coverage, the whole migrated history would report "not uploaded yet" and the
        honest 0 of a real empty window would be indistinguishable from it.
        """
        repo = IngestRunRepository(conn)
        repo.log("daily_metrics", rows_upserted=1, source="legacy")

        assert repo.covered_days("daily_metrics", *DAY_RANGE) == set()
        assert repo.days_not_uploaded_yet("daily_metrics", *DAY_RANGE) == []
        assert repo.days_with_no_data("daily_metrics", *DAY_RANGE) == []

    def test_a_class_that_claims_no_cursor_cannot_be_asked_about_days(
        self, conn: sqlite3.Connection
    ) -> None:
        """Activities (Q4): a success row with NULL cursors says the run happened, nothing more.

        Answering "never asked" would be wrong (it was asked) and answering "no data" would be worse: the
        fetch is `limit`-based, so the run never took the window the question assumes. SUB-003 owns the
        date-range fetch, and when it lands this refusal is what turns into an answer.
        """
        repo = IngestRunRepository(conn)
        repo.log("activities", rows_upserted=4, rows_fetched=4, status="success")

        with pytest.raises(ValueError, match="window-complete until SUB-003"):
            repo.covered_days("activities", *DAY_RANGE)

    def test_overlapping_windows_are_answered_as_the_union_of_what_was_asked(
        self, conn: sqlite3.Connection
    ) -> None:
        """A re-cover that found data moves the day out of "not uploaded yet".

        The morning revision is the whole reason the window overlaps its own cursor (ADR-008 §5), so the
        answer must read every covering run, not the newest one: the first run asked and got nothing,
        the second asked and got the day.
        """
        repo = IngestRunRepository(conn)
        _run(repo, "2026-03-01", "2026-03-02", fetched=0)
        assert repo.days_not_uploaded_yet("daily_metrics", *DAY_RANGE) == [
            "2026-03-01",
            "2026-03-02",
        ]

        _run(repo, "2026-03-02", "2026-03-03", fetched=1)
        _metric(conn, "2026-03-03")

        assert repo.days_not_uploaded_yet("daily_metrics", *DAY_RANGE) == ["2026-03-01"]
        assert repo.days_with_no_data("daily_metrics", *DAY_RANGE) == ["2026-03-02"]


class TestTheWindowIsClampedToTheQuestion:
    def test_a_window_wider_than_the_question_contributes_only_the_days_asked(
        self, conn: sqlite3.Connection
    ) -> None:
        """A run that covered the month answers a question about one week with one week of days.

        Both edges matter: an unclamped left edge would report days before the question as never asked,
        and an unclamped right edge would report days the question has no business claiming.
        """
        repo = IngestRunRepository(conn)
        _run(repo, "2026-02-20", "2026-03-10", fetched=1)
        for day in ("2026-03-01", "2026-03-07"):
            _metric(conn, day)

        covered = repo.covered_days("daily_metrics", *DAY_RANGE)
        assert covered == {f"2026-03-{d:02d}" for d in range(1, 8)}
        assert "2026-02-28" not in covered and "2026-03-08" not in covered
        assert repo.days_with_no_data("daily_metrics", *DAY_RANGE) == [
            "2026-03-02",
            "2026-03-03",
            "2026-03-04",
            "2026-03-05",
            "2026-03-06",
        ]


class TestTheQuestionsThatMayNotBeAsked:
    def test_a_class_with_no_day_table_refuses_the_question(self, conn: sqlite3.Connection) -> None:
        """`stress` is windowed but has no storage yet; `activities` is minute-resolved.

        Returning an empty list here would be the worst possible answer: it would read as "the ledger
        asked about every day and found nothing", which is a claim about the body, not about the code.
        """
        with pytest.raises(ValueError, match="no day-keyed table"):
            IngestRunRepository(conn).days_not_uploaded_yet("stress", *DAY_RANGE)

    def test_an_unknown_class_is_refused_by_name(self, conn: sqlite3.Connection) -> None:
        """A typo must not read as "no coverage yet".

        The three refusals above are about classes that exist; this one is about the caller, and it is the
        likelier bug of the two — `scale_sleep` is what a future reader might write for SCALE-001's class,
        and an empty answer there would be indistinguishable from a source that never reported.
        """
        with pytest.raises(ValueError, match="is not a coverage class"):
            IngestRunRepository(conn).days_not_uploaded_yet("scale_sleep", *DAY_RANGE)

    def test_the_class_table_map_cannot_drift_from_the_class_table(self) -> None:
        """Every day-granularity class that claims a cursor is either queryable or refuses loudly.

        `CLASSES` is where a coverage class is declared; this map is where its rows live. Two places for
        related facts is a drift risk (`lesson-026`), so the pair is asserted instead of trusted: a new
        day class must either join the map or be an explicit refusal.
        """
        from garsync.db.repository import DAY_KEYED_TABLES
        from garsync.ingest.window import CLASSES, Granularity

        queryable = set(DAY_KEYED_TABLES)
        assert queryable == {"daily_metrics", "sleep"}
        for sync_type in DAY_KEYED_TABLES:
            assert sync_type in CLASSES, f"{sync_type} is not a coverage class"
            assert CLASSES[sync_type].granularity is Granularity.DAY
        day_classes = {
            name for name, spec in CLASSES.items() if spec.granularity is Granularity.DAY
        }
        assert day_classes - queryable == {"stress"}, (
            "a class became queryable or a new one appeared; decide which, do not let the map choose"
        )


class TestNoPayloadStore:
    def test_raw_payload_is_not_created_before_its_first_writer(
        self, conn: sqlite3.Connection
    ) -> None:
        """SUB-001's deferred-table posture, asserted again here because *this* spec is where the
        temptation arrives: the ledger now records what arrived, which is one step from storing it.
        """
        tables = {
            row["name"]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        assert "raw_payload" not in tables
