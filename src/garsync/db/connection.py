"""SQLite connection management with WAL mode and Row factory."""

import sqlite3


def get_connection(db_path: str) -> sqlite3.Connection:
    """Create a SQLite connection with WAL mode and Row factory.

    Args:
        db_path: Path to the database file, or ":memory:" for in-memory.

    Returns:
        Configured sqlite3.Connection.
    """
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn
