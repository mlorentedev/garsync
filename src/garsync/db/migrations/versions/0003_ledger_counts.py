"""0003 — the ledger learns to count twice, and to remember when the run began.

Two additive columns on `ingest_run`, no table rebuild:

* **`rows_fetched`** — what the adapter returned. `rows_upserted` already existed but recorded the
  same number (v1's `records_synced` was copied into it), which is why a run that changed nothing
  could claim to have synced 100 records. ADR-008 §5's "zero changed values" is only auditable once
  the two counts are separate columns; `0` is also a *meaningful* value — "asked, nothing arrived"
  (AC9) — so it is NOT NULL with a 0 default rather than NULL.
* **`started_at`** — captured by the run *before* it fetches. It deliberately gets **no server
  default**: `CURRENT_TIMESTAMP` would stamp the row's insert instant, which is the run's *finish*
  (that is what `created_at` already is), and every duration read off the ledger would then be the
  write's own latency. NULL means "this run did not measure its start", which is true of every row
  written before SUB-002 and of the legacy rows `0002` copied out of `sync_log`.

Nothing here imports application code, and nothing here rewrites a row: a database at `0002` keeps
its ledger rows verbatim and gains two columns whose values for those rows are honest about being
unmeasured.

Revision ID: 0003_ledger_counts
Revises: 0002_v2
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_ledger_counts"
down_revision: str = "0002_v2"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ingest_run",
        sa.Column("rows_fetched", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )
    # Nullable and default-less, on purpose — see the module docstring.
    op.add_column("ingest_run", sa.Column("started_at", sa.Text(), nullable=True))


def downgrade() -> None:
    # Plain drops, not a batch rebuild: SQLite ≥ 3.35 removes a column in place, and a batch here
    # would recreate the table to take two columns out of it (the trap `0002` documents for adds).
    op.drop_column("ingest_run", "started_at")
    op.drop_column("ingest_run", "rows_fetched")
