"""SQLite connection management, and the one place a unit of work is opened."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager

#: How long a writer waits for the lock before giving up. pysqlite's own `timeout=5.0` already produces
#: this value (measured, lesson 029), so this line does not add a default: it states a choice, where a
#: reader of this file can see it, instead of leaving a driver default nobody looked up.
BUSY_TIMEOUT_MS = 5000


def get_connection(db_path: str) -> sqlite3.Connection:
    """Create a SQLite connection in WAL mode that leaves transactions to its caller.

    The connection runs with `isolation_level=None`, so the driver opens no implicit transaction and
    every statement outside an explicit `BEGIN` has already committed. That is what makes
    `transaction()` the only thing that can end a unit of work: with a driver-managed transaction, the
    same `commit()` a repository issues per row would end the transaction an ingest run opened, and the
    run would quietly become a sequence of independent commits (ADR-008 §2, lesson 028).

    Args:
        db_path: Path to the database file, or ":memory:" for in-memory.

    Returns:
        Configured sqlite3.Connection.
    """
    conn = sqlite3.connect(db_path, check_same_thread=False, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")
    return conn


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """One unit of work: `BEGIN IMMEDIATE`, then `COMMIT` — or `ROLLBACK` on any exception.

    `IMMEDIATE` takes the write lock at the start rather than at the first write, which is what makes
    a run's writes serialise deliberately instead of discovering the contention half-way through
    (ADR-008 §2, §8).

    A nested call **joins** the outer transaction instead of committing it: the block that knows the
    run's boundary owns the commit, and an inner failure propagates to whoever owns the transaction
    rather than being swallowed by a partial commit.
    """
    if conn.in_transaction:
        yield conn
        return
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.rollback()
        raise
    conn.commit()
