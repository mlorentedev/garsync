"""v2 — provenance, UTC timestamps, the ingest ledger, and goals.

Four things happen, and the order matters:

1. **A pre-flight refusal.** Activities whose UTC value and offset cannot be read from their own
   payload stop the migration *before* anything is written, naming the offending ids. This project
   has no default zone: the real history spans two (Garmin timeZoneId 153 and 121, offsets -420 and
   -480), so a configured guess would be hours wrong and no test would catch it. `GARSYNC_TZ` is
   honoured only when an operator sets it explicitly.
2. **The ledger.** `ingest_run` is created and `sync_log`'s rows are copied into it as
   `source='legacy'` — the v1 column was the *data class*, so it is retained as `sync_type` and
   `source` carries provenance. The old table is left in place and inert.
3. **The renames.** `biometrics` → `daily_metrics` (the HRV string kept verbatim, its numeric
   siblings born NULL: v2 never invents a number the payload did not carry) and `sleep` →
   `sleep_sessions`.
4. **The rebuild of `activities`.** It needs new columns *and* a uniqueness constraint that did not
   exist, and `source`/`source_id` must be NOT NULL without leaving a database-level default behind
   — a `server_default='garmin'` would silently label a future scale row as Garmin, which is the
   one thing a provenance column exists to prevent. So the table is rebuilt explicitly.

Nothing here imports application code: a revision has to keep working after the module it would
import has changed shape.

Revision ID: 0002_v2
Revises: 0001_v1
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

import sqlalchemy as sa
from alembic import op

revision: str = "0002_v2"
down_revision: str = "0001_v1"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_TIMESTAMP = sa.text("(strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))")
_UTC_Z = "%Y-%m-%dT%H:%M:%SZ"
_MAX_REPORTED = 20

# Rows whose UTC value and offset cannot both be read from the payload. `json_valid` guards the
# malformed-payload case so it is reported as a row id rather than as a SQL error.
_UNREADABLE = sa.text(
    """
    SELECT activity_id, start_time
    FROM activities
    WHERE start_time IS NOT NULL
      AND (
        raw_data IS NULL
        OR NOT json_valid(raw_data)
        OR strftime('%Y-%m-%dT%H:%M:%SZ', json_extract(raw_data, '$.startTimeGMT')) IS NULL
        OR julianday(json_extract(raw_data, '$.startTimeLocal')) IS NULL
      )
    ORDER BY activity_id
    """
)


def _timestamps() -> list[sa.Column[Any]]:
    return [
        sa.Column("created_at", sa.Text(), nullable=False, server_default=_TIMESTAMP),
        sa.Column("updated_at", sa.Text(), nullable=False, server_default=_TIMESTAMP),
    ]


def _refuse_unreadable_rows(bind: sa.Connection) -> list[tuple[int, str | None]]:
    """Return the rows the payload cannot explain, or abort naming them.

    Aborting here — before the first write — is what makes the refusal cheap: the transaction rolls
    back and the v1 database is exactly as it was.
    """
    rows = [(row[0], row[1]) for row in bind.execute(_UNREADABLE)]
    if not rows:
        return []

    zone_name = os.environ.get("GARSYNC_TZ")
    if not zone_name:
        reported = ", ".join(str(activity_id) for activity_id, _ in rows[:_MAX_REPORTED])
        remainder = len(rows) - _MAX_REPORTED
        more = f" (and {remainder} more)" if remainder > 0 else ""
        raise RuntimeError(
            f"{len(rows)} activities carry a local start time but their payload does not carry "
            f"both a readable UTC value and an offset: activity_id {reported}{more}. Their UTC "
            "value cannot be derived, and this project has no default zone — the history spans at "
            "least two, so a guessed zone would be hours wrong and nothing would detect it. Set "
            "GARSYNC_TZ to the zone those rows were recorded in and run the migration again."
        )
    return rows


def _resolve_with_the_configured_zone(
    rows: list[tuple[int, str | None]],
) -> list[tuple[int, str, int]]:
    """The explicit-fallback path: a zone the operator named, applied to rows nothing else explains.

    An ambiguous local time (the DST fold) resolves to the first occurrence, which is what
    `fold=0` means. That ambiguity is exactly why the payload is read first and this is a fallback.
    """
    if not rows:
        return []
    zone = ZoneInfo(os.environ["GARSYNC_TZ"])  # raises on an unknown zone, by design
    resolved: list[tuple[int, str, int]] = []
    for activity_id, local in rows:
        if local is None:
            continue
        aware = datetime.fromisoformat(local).replace(tzinfo=zone)
        offset = aware.utcoffset()
        assert offset is not None  # a ZoneInfo-aware datetime always has one
        resolved.append(
            (activity_id, aware.astimezone(UTC).strftime(_UTC_Z), int(offset.total_seconds() // 60))
        )
    return resolved


def _copy_the_ledger(bind: sa.Connection) -> None:
    op.create_table(
        "ingest_run",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=True),
        # Provenance: 'legacy' for the rows v1 wrote, and the source name for every run from here on.
        sa.Column("source", sa.Text(), nullable=False),
        # The data class the run covered — what v1 called `sync_type`. A separate axis from source,
        # because a Garmin run of activities and a Garmin run of sleep are different runs.
        sa.Column("sync_type", sa.Text(), nullable=False),
        sa.Column("rows_upserted", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("status", sa.Text(), nullable=False, server_default="success"),
        sa.Column("error_message", sa.Text(), nullable=True),
        # SUB-002 owns the cursor contract; these are born NULL and stay NULL for version 1 rows.
        sa.Column("cursor_before", sa.Text(), nullable=True),
        sa.Column("cursor_after", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False, server_default=_TIMESTAMP),
        sqlite_autoincrement=True,
    )
    bind.execute(
        sa.text(
            """
            INSERT INTO ingest_run
                (id, source, sync_type, rows_upserted, status, error_message, created_at)
            SELECT id, 'legacy', sync_type, records_synced, status, error_message, created_at
            FROM sync_log
            """
        )
    )


def _rename_biometrics() -> None:
    op.rename_table("biometrics", "daily_metrics")
    with op.batch_alter_table("daily_metrics") as batch:
        # The status string keeps its meaning and its values; only its name stops lying about
        # being a balance number.
        batch.alter_column("hrv_balance", new_column_name="hrv_baseline_status")
        # Born NULL. A numeric HRV series is recovered by re-ingesting retained payloads, and where
        # that is impossible the gap is reported rather than filled with an estimate.
        batch.add_column(sa.Column("hrv_last_night_avg", sa.REAL(), nullable=True))
        batch.add_column(sa.Column("hrv_weekly_avg", sa.REAL(), nullable=True))
        batch.add_column(sa.Column("hrv_baseline_low", sa.REAL(), nullable=True))
        batch.add_column(sa.Column("hrv_baseline_high", sa.REAL(), nullable=True))


def _rename_sleep(bind: sa.Connection) -> None:
    op.rename_table("sleep", "sleep_sessions")
    with op.batch_alter_table("sleep_sessions") as batch:
        # Named with its unit to match `total_sleep_seconds` beside it (ADR-009: units at rest).
        # Stays NULL: with the watch off at night (SC-05) nothing in v2 consumes it.
        batch.add_column(sa.Column("sleep_need_seconds", sa.Integer(), nullable=True))
    _normalise_sleep_timestamps(bind)


def _normalise_sleep_timestamps(bind: sa.Connection) -> None:
    """v1 wrote sleep times as `+00:00`; the canonical at-rest form is `Z`, one format per column."""
    rows = bind.execute(
        sa.text(
            "SELECT date, sleep_start, sleep_end FROM sleep_sessions "
            "WHERE sleep_start IS NOT NULL OR sleep_end IS NOT NULL"
        )
    ).fetchall()
    for date, sleep_start, sleep_end in rows:
        bind.execute(
            sa.text(
                "UPDATE sleep_sessions SET sleep_start = :start, sleep_end = :end WHERE date = :date"
            ),
            {
                "start": _as_utc_z(sleep_start),
                "end": _as_utc_z(sleep_end),
                "date": date,
            },
        )


def _as_utc_z(value: str | None) -> str | None:
    """A naive value is read as UTC: v1 built every sleep timestamp from a GMT epoch."""
    if value is None:
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC).strftime(_UTC_Z)


def _rebuild_activities(bind: sa.Connection) -> None:
    op.create_table(
        "activities_v2",
        sa.Column("activity_id", sa.Integer(), primary_key=True, nullable=True),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("source_id", sa.Text(), nullable=False),
        sa.Column("activity_name", sa.Text(), nullable=True),
        sa.Column("activity_type", sa.Text(), nullable=True),
        # UTC at rest, with the offset that produced it beside it (ADR-008 §11).
        sa.Column("start_time", sa.Text(), nullable=True),
        sa.Column("tz_offset_minutes", sa.Integer(), nullable=True),
        sa.Column("duration_seconds", sa.REAL(), nullable=True),
        sa.Column("distance_meters", sa.REAL(), nullable=True),
        sa.Column("average_heart_rate", sa.Integer(), nullable=True),
        sa.Column("max_heart_rate", sa.Integer(), nullable=True),
        sa.Column("calories", sa.REAL(), nullable=True),
        # Garmin's own derived numbers, kept as a cross-check for the metric layer. They are
        # re-read from the retained payload without a refetch, and where the payload does not carry
        # one — `activityTrainingLoad` is absent from most list-endpoint responses — the column
        # stays NULL and the gap is counted rather than estimated.
        sa.Column("training_load", sa.REAL(), nullable=True),
        sa.Column("aerobic_te", sa.REAL(), nullable=True),
        sa.Column("anaerobic_te", sa.REAL(), nullable=True),
        sa.Column("normalized_power", sa.REAL(), nullable=True),
        sa.Column("avg_power", sa.REAL(), nullable=True),
        sa.Column("raw_data", sa.Text(), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("source", "source_id", name="uq_activities_source"),
    )
    bind.execute(
        sa.text(
            """
            INSERT INTO activities_v2
                (activity_id, source, source_id, activity_name, activity_type, start_time,
                 tz_offset_minutes, duration_seconds, distance_meters, average_heart_rate,
                 max_heart_rate, calories, training_load, aerobic_te, anaerobic_te,
                 normalized_power, avg_power, raw_data, created_at, updated_at)
            SELECT
                activity_id,
                'garmin',
                CAST(activity_id AS TEXT),
                activity_name,
                activity_type,
                strftime('%Y-%m-%dT%H:%M:%SZ', json_extract(raw_data, '$.startTimeGMT')),
                -- The offset is the difference between two spellings Garmin reports for *one*
                -- instant, so a DST fold cannot affect it: an ambiguous local wall time does not
                -- matter when its UTC twin is handed over beside it, and no zone is consulted. Where
                -- ambiguity would bite is the reverse direction — rebuilding a local calendar day
                -- from start_time and this column — which is why that rule is a decision of its own
                -- (SUB-005) rather than something this revision assumes.
                CAST(ROUND(
                    (julianday(json_extract(raw_data, '$.startTimeLocal'))
                     - julianday(json_extract(raw_data, '$.startTimeGMT'))) * 1440
                ) AS INTEGER),
                duration_seconds, distance_meters, average_heart_rate, max_heart_rate, calories,
                json_extract(raw_data, '$.activityTrainingLoad'),
                json_extract(raw_data, '$.aerobicTrainingEffect'),
                json_extract(raw_data, '$.anaerobicTrainingEffect'),
                json_extract(raw_data, '$.normPower'),
                json_extract(raw_data, '$.avgPower'),
                raw_data, created_at, updated_at
            FROM activities
            """
        )
    )
    op.drop_table("activities")
    op.rename_table("activities_v2", "activities")


def _add_goals() -> None:
    op.create_table(
        "goals",
        # NOT NULL, unlike the v1 rowid primary keys: SQLite lets a TEXT primary key be NULL, and a
        # goal with no start date is a goal nothing can be compared against.
        sa.Column("valid_from", sa.Text(), primary_key=True, nullable=False),
        sa.Column("goal_weight_kg", sa.REAL(), nullable=True),
        sa.Column("rate_band_low_kg_per_week", sa.REAL(), nullable=True),
        sa.Column("rate_band_high_kg_per_week", sa.REAL(), nullable=True),
        *_timestamps(),
    )


def _apply_the_fallback(bind: sa.Connection, resolved: list[tuple[int, str, int]]) -> None:
    for activity_id, start_time, offset in resolved:
        bind.execute(
            sa.text(
                "UPDATE activities SET start_time = :start, tz_offset_minutes = :offset "
                "WHERE activity_id = :activity_id"
            ),
            {"start": start_time, "offset": offset, "activity_id": activity_id},
        )


def upgrade() -> None:
    bind = op.get_bind()
    # Refuse, or collect the rows an explicitly configured zone has to resolve.
    stragglers = _refuse_unreadable_rows(bind)
    resolved = _resolve_with_the_configured_zone(stragglers)

    _copy_the_ledger(bind)
    _rename_biometrics()
    _rename_sleep(bind)
    _rebuild_activities(bind)
    _add_goals()
    _apply_the_fallback(bind, resolved)

    # Alembic's alembic_version is the version SSOT now; two of them was the reason this ticket
    # exists.
    op.drop_table("schema_version")


def downgrade() -> None:
    """Forward-only in production (design §4.1), but honest enough to be exercised by a test."""
    bind = op.get_bind()

    op.create_table(
        "activities_v1",
        sa.Column("activity_id", sa.Integer(), primary_key=True, nullable=True),
        sa.Column("activity_name", sa.Text(), nullable=True),
        sa.Column("activity_type", sa.Text(), nullable=True),
        sa.Column("start_time", sa.Text(), nullable=True),
        sa.Column("duration_seconds", sa.REAL(), nullable=True),
        sa.Column("distance_meters", sa.REAL(), nullable=True),
        sa.Column("average_heart_rate", sa.Integer(), nullable=True),
        sa.Column("max_heart_rate", sa.Integer(), nullable=True),
        sa.Column("calories", sa.REAL(), nullable=True),
        sa.Column("raw_data", sa.Text(), nullable=True),
        *_timestamps(),
    )
    bind.execute(
        sa.text(
            """
            INSERT INTO activities_v1
                (activity_id, activity_name, activity_type, start_time, duration_seconds,
                 distance_meters, average_heart_rate, max_heart_rate, calories, raw_data,
                 created_at, updated_at)
            SELECT activity_id, activity_name, activity_type,
                CASE
                    WHEN tz_offset_minutes IS NULL
                        THEN strftime('%Y-%m-%dT%H:%M:%S', start_time)
                    ELSE strftime('%Y-%m-%dT%H:%M:%S',
                                  datetime(start_time, printf('%d minutes', tz_offset_minutes)))
                END,
                duration_seconds, distance_meters, average_heart_rate, max_heart_rate, calories,
                raw_data, created_at, updated_at
            FROM activities
            """
        )
    )
    op.drop_table("activities")
    op.rename_table("activities_v1", "activities")

    with op.batch_alter_table("daily_metrics") as batch:
        batch.alter_column("hrv_baseline_status", new_column_name="hrv_balance")
        for column in (
            "hrv_last_night_avg",
            "hrv_weekly_avg",
            "hrv_baseline_low",
            "hrv_baseline_high",
        ):
            batch.drop_column(column)
    op.rename_table("daily_metrics", "biometrics")

    rows = bind.execute(
        sa.text(
            "SELECT date, sleep_start, sleep_end FROM sleep_sessions "
            "WHERE sleep_start IS NOT NULL OR sleep_end IS NOT NULL"
        )
    ).fetchall()
    for date, sleep_start, sleep_end in rows:
        bind.execute(
            sa.text(
                "UPDATE sleep_sessions SET sleep_start = :start, sleep_end = :end WHERE date = :date"
            ),
            {
                "start": _as_v1_timestamp(sleep_start),
                "end": _as_v1_timestamp(sleep_end),
                "date": date,
            },
        )
    with op.batch_alter_table("sleep_sessions") as batch:
        batch.drop_column("sleep_need_seconds")
    op.rename_table("sleep_sessions", "sleep")

    # `sync_log` kept its rows throughout, so only the v2 additions go.
    op.drop_table("goals")
    op.drop_table("ingest_run")
    op.create_table(
        "schema_version", sa.Column("version", sa.Integer(), primary_key=True, nullable=True)
    )
    bind.execute(sa.text("INSERT INTO schema_version (version) VALUES (1)"))


def _as_v1_timestamp(value: str | None) -> str | None:
    """Back to the `+00:00` spelling v1's client produced."""
    if value is None:
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC).isoformat()
