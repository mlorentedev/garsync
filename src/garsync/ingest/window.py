"""The coverage window one ingest run is responsible for.

ADR-008 §13 and SC-02 are written in terms of a *trailing window* rather than "today", because
Garmin revises overnight metrics during the morning and a scale can upload hours late. This module
decides where that window begins and ends, per data class.

Two ideas do the work:

* **`settle`** — how long after an instant its data is worth asking for. Garmin publishes activities
  ~10-30 minutes after the device syncs (research/02 §4), so an activities run does not claim coverage
  for the last 45 minutes. The daily classes are keyed to a local calendar day, so their boundary is
  the day itself.
* **`granularity`** — the unit the class is spelled in. Activities are minute-resolved UTC
  (`2026-09-25T06:15:00Z`, whose lexicographic order equals its chronological order, which is why the
  ledger can store the cursor as an opaque monotone `TEXT`); the daily classes are local days
  (`2026-09-25`).

The window is **half-open**, `[start, end)`, and `covered_through` is `end` minus one unit: the cursor
names the last unit actually covered. A run therefore always has something to cover — the trailing
floor guarantees it — so "we already had this window" is not a case the caller has to handle, and a
second run inside the same minute simply re-derives the same 14 units (which is the point: that is how
a morning revision lands). `window_start = min(previous cursor, end - trailing_days)`, exactly as
ratified; the cursor's own unit is re-covered rather than skipped, and only a gap longer than the floor
pushes `start` backwards, where `end` is capped at `start + trailing_days` so a run's call count stays
bounded. This module *owns* the meaning of the cursor's spelling; the ledger only stores and orders it.

The daily window includes **today** (SUB-002 §Q6): the 07:00 run exists to ingest last night's sleep,
which Garmin keys to the wake date, and the end-of-day run refreshes the same day. The cursor is a
*coverage* claim — what has been asked for — never a claim that the values are final.

Nothing here decides which calendar day a **row** belongs to: that is issue #115, and the boundary is
that no consumer may derive an attribution from a cursor.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from enum import StrEnum
from typing import Final
from zoneinfo import ZoneInfo

from garsync.timeutil import utc_z

#: The configured zone whose calendar day the daily classes are keyed to (ADR-008 §11). Set on
#: purpose, never defaulted in code: a guessed zone is hours wrong and nothing detects it.
GARSYNC_TZ_VAR: Final = "GARSYNC_TZ"

#: SC-02(1)'s initial trailing window. A run never covers more than this span, so a long gap is
#: closed over several runs instead of in one unbounded burst of calls (ADR-008 §8).
TRAILING_DAYS: Final = 14

#: The smallest span a gap-closing chunk may take. A chunk **re-covers the cursor's own unit** (that is
#: how a morning revision lands), so a one-unit chunk covers a day it already had and advances the
#: watermark by nothing — the run repeats forever, each time reporting the same `cursor_after`, and the
#: gap never closes. Measured with `--days 1` over a four-day-old cursor (SUB-002 block 5):
#: frozen at the cursor's day. Two units is the minimum that makes progress: the seam plus one new day.
#: At the ratified 14 the bound is unchanged, so the ≈71-call arithmetic keeps its meaning.
MIN_CHUNK_UNITS: Final = 2


class Granularity(StrEnum):
    """The unit a class is spelled in."""

    MINUTE = "minute"
    DAY = "day"


@dataclass(frozen=True)
class SyncClass:
    """The coverage policy of one data class: when its data settles, in what unit, and whether a run
    of it may claim coverage at all."""

    sync_type: str
    settle: timedelta
    granularity: Granularity
    #: Whether a successful run of this class may write `cursor_after`. This is the Q4 exception, and
    #: it lives in the table rather than in an `if` at the call site: activities are fetched by
    #: `limit`, so a cursor would claim a window the run never took (SUB-003 owns the date-range
    #: fetch, and when it lands this flag flipping is the whole change).
    claims_cursor: bool = True


#: Activities: published minutes after the sync, minute-resolved, so the last 45 minutes are not
#: claimed. The daily classes: a local day is the unit, so the boundary is the day itself. Weight is
#: absent on purpose — its cursor is the FitDays cloud's own `sync_time`, owned by SCALE-001.
CLASSES: Final[dict[str, SyncClass]] = {
    "activities": SyncClass("activities", timedelta(minutes=45), Granularity.MINUTE, False),
    "daily_metrics": SyncClass("daily_metrics", timedelta(0), Granularity.DAY),
    "sleep": SyncClass("sleep", timedelta(0), Granularity.DAY),
    "stress": SyncClass("stress", timedelta(0), Granularity.DAY),
}


@dataclass(frozen=True)
class Window:
    """What one run must cover. `end` is exclusive; `covered_through` is what the cursor stores."""

    sync_type: str
    start: str
    end: str
    covered_through: str
    units: int

    def days(self) -> list[date]:
        """The local calendar days this window covers, oldest first — the fetch list for a day class.

        A minute-resolved class raises rather than returning an approximation: inventing a day list for
        activities would hand the run a coverage claim in the shape of a helper, which is the Q4 defect
        with a friendly face. The list is exactly `units` long, so the ≈71-call arithmetic in the class
        table and the number of requests a run makes cannot drift apart.
        """
        sync_class = CLASSES[self.sync_type]
        if sync_class.granularity is not Granularity.DAY:
            raise ValueError(
                f"{self.sync_type} is resolved by minute, not by day; its fetch is not window-complete "
                "until SUB-003"
            )
        first = date.fromisoformat(self.start)
        return [first + timedelta(days=offset) for offset in range(self.units)]


def resolve_window(
    sync_type: str,
    now: datetime,
    last_cursor: str | None,
    *,
    trailing_days: int = TRAILING_DAYS,
    tz: ZoneInfo | None = None,
) -> Window:
    """The window `sync_type` must cover at `now`.

    `last_cursor` is the class's previous `covered_through`; it only moves the window's **left** edge,
    and only when it is older than the trailing floor — which is what makes a resumable backfill and
    the daily re-derivation the same code path. The right edge is `now` settled and truncated, so a
    run never claims coverage for data that has not been published yet.
    """
    if now.tzinfo is None:
        raise ValueError(
            "`now` must carry a timezone; an instant without one cannot be a local day"
        )
    if trailing_days < 1:
        raise ValueError(f"trailing_days must be at least one unit, got {trailing_days}")
    sync_class = CLASSES.get(sync_type)
    if sync_class is None:
        raise ValueError(
            f"unknown sync_type {sync_type!r}; known classes: {', '.join(sorted(CLASSES))}"
        )
    if sync_class.granularity is Granularity.DAY:
        return _day_window(sync_class, now, last_cursor, trailing_days, tz or _configured_zone())
    return _minute_window(sync_class, now, last_cursor, trailing_days)


def _day_window(
    sync_class: SyncClass,
    now: datetime,
    last_cursor: str | None,
    trailing_days: int,
    zone: ZoneInfo,
) -> Window:
    """A window whose unit is the local calendar day: today is claimable, its predecessor is covered."""
    end_day = (now.astimezone(zone) - sync_class.settle).date() + timedelta(days=1)
    floor = end_day - timedelta(days=trailing_days)
    if last_cursor is None:
        start_day = floor
    else:
        start_day = min(date.fromisoformat(last_cursor), floor)
    end_effective = min(end_day, start_day + timedelta(days=_chunk_units(trailing_days)))
    return Window(
        sync_type=sync_class.sync_type,
        start=start_day.isoformat(),
        end=end_effective.isoformat(),
        covered_through=(end_effective - timedelta(days=1)).isoformat(),
        units=(end_effective - start_day).days,
    )


def _minute_window(
    sync_class: SyncClass,
    now: datetime,
    last_cursor: str | None,
    trailing_days: int,
) -> Window:
    """A window whose unit is the UTC minute, settled by `sync_class.settle`."""
    end = _truncate_to_minute(now - sync_class.settle) + timedelta(minutes=1)
    floor = end - timedelta(days=trailing_days)
    if last_cursor is None:
        start = floor
    else:
        start = min(_parse_minute(last_cursor), floor)
    end_effective = min(end, start + timedelta(days=_chunk_units(trailing_days)))
    return Window(
        sync_type=sync_class.sync_type,
        start=utc_z(start),
        end=utc_z(end_effective),
        covered_through=utc_z(end_effective - timedelta(minutes=1)),
        units=int((end_effective - start).total_seconds() // 60),
    )


def _chunk_units(trailing_days: int) -> int:
    """How many units a run's span may hold: the caller's floor, but never less than two.

    One unit is not a chunk, it is a stall — see `MIN_CHUNK_UNITS`. The clamp belongs here, in the one
    function both granularities call, because a per-window clamp is two places for the same arithmetic
    to disagree (`lesson-026`'s shape, and the drift `check-lessons` exists to catch).
    """
    return max(trailing_days, MIN_CHUNK_UNITS)


def _truncate_to_minute(instant: datetime) -> datetime:
    return instant.astimezone(UTC).replace(second=0, microsecond=0)


def _parse_minute(cursor: str) -> datetime:
    """A stored activities cursor back to a UTC datetime, truncated to its minute.

    A cursor that cannot be parsed is raised rather than ignored: this module is the only writer of
    that column, so an unparseable value means it was edited by hand, and silently re-covering the
    floor would hide the one event worth knowing about.
    """
    return _truncate_to_minute(datetime.fromisoformat(cursor))


def _configured_zone() -> ZoneInfo:
    name = os.environ.get(GARSYNC_TZ_VAR)
    if not name:
        raise RuntimeError(
            f"{GARSYNC_TZ_VAR} is not set: the daily classes are keyed to a local calendar day, and "
            "a guessed zone would be silently wrong (ADR-008 §11). Set it in the environment."
        )
    return ZoneInfo(name)
