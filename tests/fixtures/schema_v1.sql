-- v1 schema, frozen 2026-09-24 for the SUB-001 migration test.
--
-- This is a copy, not an import: the migration's *from* state must be buildable after the code
-- that created it is gone, so the test cannot depend on `_SCHEMA_V1` still existing. Verified
-- byte-for-byte against `src/garsync/db/schema.py` at revision 636a7ad.

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
