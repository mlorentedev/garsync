"""Pre-migration snapshots of the database file.

ADR-009 §4.1 requires a backup before the migration runs. Written as an instruction, that is a rule
nobody executes at the moment it matters — so it is a function the upgrade path calls, and a target
an operator can run by hand (`make db-backup`).

`VACUUM INTO` rather than a file copy: it writes a consistent snapshot of a live database, including
anything still in the write-ahead log, and it cannot produce the torn file that `cp` produces when a
writer is mid-commit. A checkpoint is deliberately *not* issued first — `VACUUM INTO` already reads
through the connection, so a checkpoint would only add a write to a database this code is otherwise
only reading.
"""

from __future__ import annotations

import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path

#: Snapshots live beside the database, inside the directory that is already gitignored.
BACKUP_DIRNAME = "backups"


def snapshot_path(db_path: Path, taken_at: datetime | None = None) -> Path:
    """Where a snapshot taken now would go. UTC, so the names sort as they were written."""
    stamp = (taken_at or datetime.now(UTC)).strftime("%Y%m%dT%H%M%SZ")
    return db_path.parent / BACKUP_DIRNAME / f"{db_path.stem}-{stamp}.db"


def snapshot(conn: sqlite3.Connection, db_path: Path, taken_at: datetime | None = None) -> Path:
    """Write a snapshot of `conn`'s database next to `db_path` and return where it landed.

    Refuses to overwrite: a second snapshot in the same second is a name collision, and silently
    replacing the earlier one is exactly the outcome a backup exists to prevent.
    """
    target = snapshot_path(db_path, taken_at)
    if target.exists():
        raise FileExistsError(f"refusing to overwrite an existing snapshot: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    conn.commit()  # `VACUUM INTO` cannot run inside a transaction
    conn.execute("VACUUM INTO ?", (str(target),))
    return target


def main(argv: list[str] | None = None) -> int:
    """`python -m garsync.db.backup [db_path]` — the same snapshot, on demand."""
    from garsync.db.connection import get_connection

    args = sys.argv[1:] if argv is None else argv
    db_path = Path(args[0] if args else "data/garsync.db")
    if not db_path.exists():
        print(f"db-backup: no database at {db_path}", file=sys.stderr)
        return 1
    conn = get_connection(str(db_path))
    try:
        written = snapshot(conn, db_path)
    finally:
        conn.close()
    print(written)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
