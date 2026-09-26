"""The coverage window of one ingest run — SUB-002, AC3 and AC4.

The window is the unit ADR-008 §13 and SC-02 are written in: every run re-derives a trailing span
rather than "today", because Garmin revises overnight metrics during the morning and a scale can
upload hours late.
"""

from dataclasses import FrozenInstanceError
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from garsync.ingest.window import (
    MIN_CHUNK_UNITS,
    TRAILING_DAYS,
    Window,
    resolve_window,
)

MADRID = ZoneInfo("Europe/Madrid")
NEW_YORK = ZoneInfo("America/New_York")

#: The daily classes cost four biometrics calls plus one sleep call per day fetched.
CALLS_PER_DAY = 5
#: The activity list is one call per run, whatever the span (SUB-003 makes it windowed).
ACTIVITY_LIST_CALLS = 1

#: The instants under test: a morning wellness run, and the later activities cadence.
MORNING = datetime(2026, 9, 25, 5, 0, tzinfo=UTC)  # 07:00 in Europe/Madrid
ACTIVITIES_NOW = datetime(2026, 9, 25, 7, 0, tzinfo=UTC)


def test_the_window_table() -> None:
    """One row per decision the window makes; `expect` is (start, end, covered_through, units)."""
    cases = [
        # The first activities run: a 14-day span of minutes, and coverage that stops 45 minutes
        # short of now — the settle window — so a 07:00 run does not claim 07:00.
        (
            "activities",
            ACTIVITIES_NOW,
            None,
            None,
            (
                "2026-09-11T06:16:00Z",
                "2026-09-25T06:16:00Z",
                "2026-09-25T06:15:00Z",
                TRAILING_DAYS * 24 * 60,
            ),
        ),
        # The 07:00 daily run covers *today*: that is the run that ingests last night's sleep, which
        # Garmin keys to the wake date (Q6).
        (
            "daily_metrics",
            MORNING,
            None,
            MADRID,
            ("2026-09-12", "2026-09-26", "2026-09-25", TRAILING_DAYS),
        ),
        ("sleep", MORNING, None, MADRID, ("2026-09-12", "2026-09-26", "2026-09-25", TRAILING_DAYS)),
        (
            "stress",
            MORNING,
            None,
            MADRID,
            ("2026-09-12", "2026-09-26", "2026-09-25", TRAILING_DAYS),
        ),
        # A cursor 30 days back starts the window there and caps it at the trailing span, so the gap
        # is closed in chunks and no single run becomes a 30-day burst of calls.
        (
            "daily_metrics",
            MORNING,
            "2026-08-25",
            MADRID,
            ("2026-08-25", "2026-09-08", "2026-09-07", TRAILING_DAYS),
        ),
        # A cursor already inside the floor changes nothing: the floor wins, which is what re-derives
        # the trailing window on every run.
        (
            "daily_metrics",
            MORNING,
            "2026-09-20",
            MADRID,
            ("2026-09-12", "2026-09-26", "2026-09-25", TRAILING_DAYS),
        ),
    ]
    for sync_type, now, cursor, tz, (start, end, covered, units) in cases:
        window = resolve_window(sync_type, now, cursor, tz=tz)
        assert (window.start, window.end, window.covered_through, window.units) == (
            start,
            end,
            covered,
            units,
        ), (sync_type, cursor)
        assert window.sync_type == sync_type


def test_the_window_is_half_open_and_the_cursor_names_the_last_covered_unit() -> None:
    """`end` is exclusive and `covered_through` is its predecessor — the cursor's spelling."""
    window = resolve_window("daily_metrics", MORNING, None, tz=MADRID)
    assert date.fromisoformat(window.covered_through) == date.fromisoformat(window.end) - timedelta(
        days=1
    )
    assert window.units == (date.fromisoformat(window.end) - date.fromisoformat(window.start)).days


def test_a_second_run_in_the_same_unit_rederives_the_same_window() -> None:
    """Re-derivation, not incrementality: the run that catches a morning revision is this one.

    There is deliberately no "nothing to do" case — the trailing floor always leaves something to
    cover, and a window that changed nothing is a no-op at the write layer instead (ADR-008 §5).
    """
    first = resolve_window("activities", ACTIVITIES_NOW, None)
    again = resolve_window("activities", ACTIVITIES_NOW, first.covered_through)
    assert again.start < again.end
    assert (again.start, again.end, again.covered_through) == (
        first.start,
        first.end,
        first.covered_through,
    )


def test_a_cursor_in_the_future_is_ignored_rather_than_covered_backwards() -> None:
    """A clock skew, or a hand-edited cursor, must not produce a negative span."""
    window = resolve_window("activities", ACTIVITIES_NOW, "2026-09-25T23:00:00Z")
    assert window.start < window.end
    assert window.start == "2026-09-11T06:16:00Z", "the floor is used when the cursor is nonsense"


def test_a_morning_run_does_not_claim_the_current_instant() -> None:
    """Failure mode the tests must kill: a run that claims what the settle window excludes."""
    window = resolve_window("activities", ACTIVITIES_NOW, None)
    covered = datetime.fromisoformat(window.covered_through)
    assert covered <= ACTIVITIES_NOW - timedelta(minutes=45)


def test_a_long_gap_is_closed_in_chunks_without_a_hole() -> None:
    """Every chunk is bounded, each one advances the cursor, and the gap ends up covered."""
    cursor = "2026-08-01"
    chunks: list[tuple[str, str]] = []
    while True:
        window = resolve_window("daily_metrics", MORNING, cursor, tz=MADRID)
        if window.covered_through == cursor:  # converged: the floor window now repeats
            break
        assert window.units <= TRAILING_DAYS, window
        assert window.covered_through > cursor, (cursor, window)
        chunks.append((window.start, window.covered_through))
        cursor = window.covered_through
        assert len(chunks) < 10, "the chunking must converge, not loop"
    assert len(chunks) == 5, chunks
    covered: set[date] = set()
    for start, through in chunks:
        day = date.fromisoformat(start)
        while day <= date.fromisoformat(through):
            covered.add(day)
            day += timedelta(days=1)
    expected = {date(2026, 8, 1) + timedelta(days=i) for i in range(56)}
    assert expected <= covered, sorted(expected - covered)
    assert chunks[-1][1] == "2026-09-25"


@pytest.mark.parametrize(
    "now",
    [
        datetime(2026, 11, 1, 16, 30, tzinfo=UTC),  # 12:30 EDT — before the fold
        datetime(2026, 11, 2, 4, 30, tzinfo=UTC),  # 23:30 EST — after it, same local day
    ],
)
def test_a_dst_fold_does_not_move_the_local_day(now: datetime) -> None:
    """The local day is the unit, so an hour that happens twice cannot shift it."""
    window = resolve_window("daily_metrics", now, None, tz=NEW_YORK)
    assert window.covered_through == "2026-11-01"


def test_the_daily_window_costs_one_call_per_day_plus_the_list() -> None:
    """The arithmetic D1 and ADR-008 §8 rest on: a bounded call count per run."""
    window = resolve_window("daily_metrics", MORNING, None, tz=MADRID)
    assert window.units * CALLS_PER_DAY + ACTIVITY_LIST_CALLS == 71


def test_the_daily_classes_refuse_to_guess_a_zone(monkeypatch: pytest.MonkeyPatch) -> None:
    """`GARSYNC_TZ` is set on purpose, never defaulted in code (the SUB-001 rule, kept)."""
    monkeypatch.delenv("GARSYNC_TZ", raising=False)
    with pytest.raises(RuntimeError, match="GARSYNC_TZ"):
        resolve_window("daily_metrics", MORNING, None)


def test_the_configured_zone_is_used_when_it_is_set(monkeypatch: pytest.MonkeyPatch) -> None:
    """The same instant in two zones is two different local days — the setting is load-bearing."""
    monkeypatch.setenv("GARSYNC_TZ", "America/New_York")
    utc_window = resolve_window("daily_metrics", datetime(2026, 9, 25, 2, 0, tzinfo=UTC), None)
    madrid_window = resolve_window(
        "daily_metrics", datetime(2026, 9, 25, 2, 0, tzinfo=UTC), None, tz=MADRID
    )
    assert utc_window.covered_through == "2026-09-24", "02:00 UTC is still the 24th in New York"
    assert madrid_window.covered_through == "2026-09-25", "…and already the 25th in Madrid"


def test_an_unknown_sync_type_is_named_in_the_error() -> None:
    with pytest.raises(ValueError, match="weight"):
        resolve_window("weight", MORNING, None)


def test_a_naive_instant_is_refused() -> None:
    """An instant without a zone cannot be truncated to a local day — say so instead of guessing."""
    with pytest.raises(ValueError, match="timezone"):
        # The naive instant IS the subject of this test: ruff must not be talked out of seeing it.
        resolve_window(
            "daily_metrics",
            datetime(2026, 9, 25, 7, 0),  # noqa: DTZ001
            None,
            tz=MADRID,
        )


def test_a_trailing_window_without_units_is_refused() -> None:
    """`trailing_days=0` would make the window empty; it is a caller bug, not a mode."""
    with pytest.raises(ValueError, match="trailing_days"):
        resolve_window("daily_metrics", MORNING, None, trailing_days=0, tz=MADRID)


def test_the_window_is_immutable() -> None:
    window = resolve_window("activities", ACTIVITIES_NOW, None)
    assert isinstance(window, Window)
    with pytest.raises(FrozenInstanceError):
        window.start = "2026-01-01"  # type: ignore[misc]


def test_a_one_unit_floor_could_otherwise_stall_forever(monkeypatch: pytest.MonkeyPatch) -> None:
    """The chunking's degenerate case, found by driving it from a run (SUB-002 block 5).

    A gap-closing chunk re-covers the cursor's own unit — that re-cover is how a morning revision
    lands — so a chunk of exactly one unit covers a day it already had and reports the *same*
    `cursor_after`. Repeated, the watermark never moves: the ledger would say "covered through D"
    forever while today's data went unfetched, and every run would look successful.

    `--days 1` reaches this arithmetic directly, so the invariant is asserted where it is cheap: a
    chunked window advances by at least one unit.
    """
    monkeypatch.setenv("GARSYNC_TZ", "Europe/Madrid")
    cursor = "2026-03-01"
    window = resolve_window(
        "daily_metrics",
        datetime(2026, 3, 5, 12, 0, tzinfo=UTC),
        cursor,
        trailing_days=1,
        tz=MADRID,
    )

    assert window.start == cursor, "the chunk still starts at the seam it re-covers"
    assert window.covered_through > cursor, "a run that covers nothing new is not a chunk"
    assert window.days() == [date(2026, 3, 1), date(2026, 3, 2)]
    assert window.units == 2


def test_the_ratified_fourteen_day_bound_is_unchanged_by_the_floor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The stall fix must not silently widen the ratified ≈71-call budget.

    At the default floor the clamp is inactive: a 30-day gap is still closed in 14-day chunks, so the
    arithmetic in `test_the_daily_window_costs_one_call_per_day_plus_the_list` keeps its meaning.
    """
    monkeypatch.setenv("GARSYNC_TZ", "Europe/Madrid")
    window = resolve_window(
        "daily_metrics",
        datetime(2026, 3, 5, 12, 0, tzinfo=UTC),
        "2026-02-01",
        tz=MADRID,
    )
    assert window.units == 14


def test_a_minute_resolved_class_refuses_to_enumerate_days(monkeypatch: pytest.MonkeyPatch) -> None:
    """`Window.days()` is the fetch list, and activities have no honest one (Q4).

    Returning a day list for a `limit`-based fetch would let the run claim coverage through the
    arithmetic of a helper — the defect this whole block exists to prevent, wearing a friendly face.
    """
    window = resolve_window("activities", datetime(2026, 3, 5, 12, 0, tzinfo=UTC), None)
    assert window is not None
    with pytest.raises(ValueError, match="not window-complete until SUB-003"):
        window.days()


@pytest.mark.parametrize("trailing", [1, 2, 3, TRAILING_DAYS])
def test_every_floor_value_closes_the_gap_without_stalling(trailing: int) -> None:
    """A bound the caller can lower needs a floor, or it stops being a bound.

    `test_a_long_gap_is_closed_in_chunks_without_a_hole` already asserts "each chunk advances the
    cursor" — at 14, the only value the floor could have when it was written, and a property of one
    input is not a property of the function. Since SUB-002 the floor is caller-supplied (`--days N`),
    so `N = 1` is an input now, and at one unit the chunk re-covers the cursor's own day and advances
    nothing (lesson 033). Same loop, four floors, no stall allowed.
    """
    cursor = "2026-08-01"
    steps = 0
    while True:
        window = resolve_window("daily_metrics", MORNING, cursor, trailing_days=trailing, tz=MADRID)
        if window.covered_through == cursor:  # converged: the floor window now repeats
            break
        assert window.covered_through > cursor, (trailing, cursor, window)
        assert window.units <= max(trailing, MIN_CHUNK_UNITS), window
        cursor = window.covered_through
        steps += 1
        assert steps <= 60, f"trailing_days={trailing} did not converge"
    assert cursor == "2026-09-25", f"trailing_days={trailing} stopped short"
