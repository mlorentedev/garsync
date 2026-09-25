"""UTC helpers for the ingest path.

The database stores UTC at rest with the offset that produced it beside it (ADR-008 §11), so the
instant a row is built from has to come from the payload that carries it: Garmin reports both the
local and the GMT spelling of the same moment, and their difference *is* the offset.

Nothing here consults a configured zone. The only configured zone in this project is `GARSYNC_TZ`,
and it exists for the calendar-day boundary of a daily rollup — not for deciding what an instant was.
A guess there would be hours wrong on a history spanning two zones, and nothing would detect it.
"""

from __future__ import annotations

from datetime import UTC, datetime

#: Garmin's spelling of `startTimeLocal` / `startTimeGMT`.
GARMIN_TIMESTAMP = "%Y-%m-%d %H:%M:%S"


def utc_z(value: datetime) -> str:
    """The canonical at-rest spelling: UTC, second resolution, `Z` suffixed."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_garmin_timestamp(value: object) -> datetime | None:
    """Garmin's `YYYY-MM-DD HH:MM:SS` to an aware UTC datetime, or None if it is not one."""
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    # Garmin's spelling carries no offset, which is the whole reason this helper exists: the value is
    # naive by construction, and UTC is attached on the next line rather than inferred from a string
    # that does not contain it.
    for parse in (lambda t: datetime.strptime(t, GARMIN_TIMESTAMP), datetime.fromisoformat):  # noqa: DTZ007
        try:
            return parse(text).replace(tzinfo=UTC)
        except ValueError:
            continue
    return None


def offset_minutes(local: object, gmt: object) -> int | None:
    """The offset the payload reports, in minutes east of UTC, or None if it does not report one."""
    local_time = parse_garmin_timestamp(local)
    gmt_time = parse_garmin_timestamp(gmt)
    if local_time is None or gmt_time is None:
        return None
    return int((local_time - gmt_time).total_seconds() // 60)
