"""Tests for the ingest path's UTC helpers.

These decide what an instant *was*, so the cases that matter are the ones the real payload set
contains — the two offsets it spans, and a value that is not a timestamp at all.
"""

from datetime import UTC, datetime, timedelta, timezone

import pytest

from garsync.timeutil import GARMIN_TIMESTAMP, offset_minutes, parse_garmin_timestamp, utc_z

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        # The naive value is the case under test: every naive value in this system came from a GMT
        # source, so `utc_z` reads it as UTC rather than refusing it.
        (datetime(2026, 1, 10, 21, 48, 59), "2026-01-10T21:48:59Z"),  # noqa: DTZ001
        # Aware input is converted, not relabelled.
        (datetime(2026, 1, 11, 4, 48, 59, tzinfo=UTC), "2026-01-11T04:48:59Z"),
        (
            datetime(2026, 1, 11, 5, 48, 59, tzinfo=timezone(timedelta(hours=1))),
            "2026-01-11T04:48:59Z",
        ),  # Sub-second precision is dropped rather than rounded into the next second.
        (datetime(2026, 1, 11, 4, 48, 59, 999999, tzinfo=UTC), "2026-01-11T04:48:59Z"),
    ],
)
def test_utc_z_is_the_canonical_spelling(value: datetime, expected: str) -> None:
    assert utc_z(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2026-01-11 04:48:59", datetime(2026, 1, 11, 4, 48, 59, tzinfo=UTC)),
        ("  2026-01-11 04:48:59  ", datetime(2026, 1, 11, 4, 48, 59, tzinfo=UTC)),
        # The ISO spelling Garmin's newer endpoints use, accepted by the fallback parser.
        ("2026-01-11T04:48:59", datetime(2026, 1, 11, 4, 48, 59, tzinfo=UTC)),
        # An explicit offset is converted, never relabelled: `+05:00` is 23:48:59Z the day before, and
        # `replace(tzinfo=UTC)` would have called it 04:48:59Z five hours wrong.
        ("2026-01-11T04:48:59+05:00", datetime(2026, 1, 10, 23, 48, 59, tzinfo=UTC)),
        ("2026-01-11T04:48:59Z", datetime(2026, 1, 11, 4, 48, 59, tzinfo=UTC)),
    ],
)
def test_parse_garmin_timestamp_reads_both_spellings(value: object, expected: datetime) -> None:
    assert parse_garmin_timestamp(value) == expected


@pytest.mark.parametrize("value", [None, "", "   ", "not a timestamp", 1768106939000, [], {}])
def test_unreadable_values_are_none_rather_than_an_error(value: object) -> None:
    """A payload the parser cannot read must produce a gap, never a guess and never a crash."""
    assert parse_garmin_timestamp(value) is None


@pytest.mark.parametrize(
    ("local", "gmt", "expected"),
    [
        # The two offsets the real database contains, hand-computed from the payload pair.
        ("2026-01-10 21:48:59", "2026-01-11 04:48:59", -420),
        ("2026-02-01 09:00:00", "2026-02-01 17:00:00", -480),
        # The DST fold: the local string alone is ambiguous, and the GMT value settles it.
        ("2026-11-01 01:30:00", "2026-11-01 07:30:00", -360),
        # East of UTC, so the sign is exercised in both directions.
        ("2026-06-01 12:00:00", "2026-06-01 10:00:00", 120),
        # Half-hour zones exist and must not be rounded to the nearest hour.
        ("2026-06-01 12:30:00", "2026-06-01 11:00:00", 90),
    ],
)
def test_the_offset_is_read_from_the_payload(local: str, gmt: str, expected: int) -> None:
    assert offset_minutes(local, gmt) == expected


@pytest.mark.parametrize(
    ("local", "gmt"),
    [(None, "2026-01-11 04:48:59"), ("2026-01-10 21:48:59", None), (None, None), ("x", "y")],
)
def test_a_half_measured_pair_yields_no_offset(local: object, gmt: object) -> None:
    """Half an answer is not an answer: the offset is None so the column stays NULL."""
    assert offset_minutes(local, gmt) is None


def test_the_declared_format_is_the_one_garmin_sends() -> None:
    """A guard on the constant: the parser and the migration's SQL have to agree on the shape."""
    assert datetime.strptime("2026-01-11 04:48:59", GARMIN_TIMESTAMP).hour == 4  # noqa: DTZ007
