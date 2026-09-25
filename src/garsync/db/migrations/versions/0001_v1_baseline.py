"""v1 baseline — the schema exactly as it existed before Alembic.

This revision is not a migration; it is the *starting point*, and it exists so that an existing v1
database can be stamped rather than recreated. Everything depends on it being faithful: if it
disagrees with what is on disk, `alembic stamp 0001_v1` records a lie and the next revision
transforms a schema nobody has. `TestAlembicSeam::test_the_baseline_reproduces_the_v1_schema` holds
it against the frozen DDL in `tests/fixtures/schema_v1.sql`.

Two details are load-bearing and easy to get wrong:

* `activity_id`/`date`/`id` are primary keys with ``nullable=True``. SQLAlchemy otherwise renders
  ``INTEGER NOT NULL`` where v1 wrote ``INTEGER PRIMARY KEY`` — a different table, since a rowid
  alias accepts an omitted value and a NOT NULL column does not.
* ``server_default=sa.text(...)`` is the expression form. Passed as a plain string it is quoted and
  becomes a *literal*, so `created_at` would default to the text of a function call.

Revision ID: 0001_v1
Revises:
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

revision: str = "0001_v1"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_TIMESTAMP = sa.text("(strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))")


def _timestamps() -> list[sa.Column[Any]]:
    return [
        sa.Column("created_at", sa.Text(), nullable=False, server_default=_TIMESTAMP),
        sa.Column("updated_at", sa.Text(), nullable=False, server_default=_TIMESTAMP),
    ]


def upgrade() -> None:
    op.create_table(
        "activities",
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
    op.create_table(
        "biometrics",
        sa.Column("date", sa.Text(), primary_key=True, nullable=True),
        sa.Column("resting_heart_rate", sa.Integer(), nullable=True),
        sa.Column("hrv_balance", sa.Text(), nullable=True),
        sa.Column("body_battery_highest", sa.Integer(), nullable=True),
        sa.Column("body_battery_lowest", sa.Integer(), nullable=True),
        sa.Column("stress_average", sa.Integer(), nullable=True),
        sa.Column("raw_data", sa.Text(), nullable=True),
        *_timestamps(),
    )
    op.create_table(
        "sleep",
        sa.Column("date", sa.Text(), primary_key=True, nullable=True),
        sa.Column("sleep_start", sa.Text(), nullable=True),
        sa.Column("sleep_end", sa.Text(), nullable=True),
        sa.Column("total_sleep_seconds", sa.Integer(), nullable=True),
        sa.Column("deep_sleep_seconds", sa.Integer(), nullable=True),
        sa.Column("light_sleep_seconds", sa.Integer(), nullable=True),
        sa.Column("rem_sleep_seconds", sa.Integer(), nullable=True),
        sa.Column("awake_sleep_seconds", sa.Integer(), nullable=True),
        sa.Column("sleep_score", sa.Integer(), nullable=True),
        sa.Column("raw_data", sa.Text(), nullable=True),
        *_timestamps(),
    )
    op.create_table(
        "sync_log",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=True),
        sa.Column("sync_type", sa.Text(), nullable=False),
        sa.Column("records_synced", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("status", sa.Text(), nullable=False, server_default="success"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False, server_default=_TIMESTAMP),
        sqlite_autoincrement=True,
    )
    op.create_table(
        "schema_version",
        sa.Column("version", sa.Integer(), primary_key=True, nullable=True),
    )


def downgrade() -> None:
    op.drop_table("schema_version")
    op.drop_table("sync_log")
    op.drop_table("sleep")
    op.drop_table("biometrics")
    op.drop_table("activities")
