"""DDL definitions and schema migration for garsync SQLite database."""

import sqlite3

CURRENT_VERSION = 1

_SCHEMA_V1 = """
CREATE TABLE IF NOT EXISTS activities (
    activity_id   INTEGER PRIMARY KEY,
    activity_name TEXT,
    activity_type TEXT,
    start_time    TEXT,
    duration_seconds REAL,
    distance_meters  REAL,
    average_heart_rate INTEGER,
    max_heart_rate     INTEGER,
    calories      REAL,
    raw_data      TEXT,
    created_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS biometrics (
    date               TEXT PRIMARY KEY,
    resting_heart_rate INTEGER,
    hrv_balance        TEXT,
    body_battery_highest INTEGER,
    body_battery_lowest  INTEGER,
    stress_average     INTEGER,
    raw_data           TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS sleep (
    date                TEXT PRIMARY KEY,
    sleep_start         TEXT,
    sleep_end           TEXT,
    total_sleep_seconds INTEGER,
    deep_sleep_seconds  INTEGER,
    light_sleep_seconds INTEGER,
    rem_sleep_seconds   INTEGER,
    awake_sleep_seconds INTEGER,
    sleep_score         INTEGER,
    raw_data            TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS sync_log (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    sync_type      TEXT NOT NULL,
    records_synced INTEGER NOT NULL DEFAULT 0,
    status         TEXT NOT NULL DEFAULT 'success',
    error_message  TEXT,
    created_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);
"""


def _get_version(conn: sqlite3.Connection) -> int | None:
    """Get current schema version, or None if table doesn't exist."""
    try:
        cursor = conn.execute("SELECT version FROM schema_version")
        row = cursor.fetchone()
        return row["version"] if row else None
    except sqlite3.OperationalError:
        return None


def init_db(conn: sqlite3.Connection) -> None:
    """Initialize database schema. Idempotent — safe to call repeatedly."""
    current = _get_version(conn)
    if current == CURRENT_VERSION:
        return

    conn.executescript(_SCHEMA_V1)

    if current is None:
        conn.execute(
            "INSERT OR REPLACE INTO schema_version (version) VALUES (?)",
            (CURRENT_VERSION,),
        )
        conn.commit()
