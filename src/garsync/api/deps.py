"""FastAPI dependency injection for database and repositories."""

import sqlite3

from fastapi import Request

from garsync.db.repository import (
    ActivityRepository,
    BiometricsRepository,
    IngestRunRepository,
    SleepRepository,
)


def get_db(request: Request) -> sqlite3.Connection:
    """Get the SQLite connection from app state."""
    conn: sqlite3.Connection = request.app.state.db
    return conn


def get_activity_repo(request: Request) -> ActivityRepository:
    """Factory for ActivityRepository."""
    return ActivityRepository(get_db(request))


def get_biometrics_repo(request: Request) -> BiometricsRepository:
    """Factory for BiometricsRepository."""
    return BiometricsRepository(get_db(request))


def get_sleep_repo(request: Request) -> SleepRepository:
    """Factory for SleepRepository."""
    return SleepRepository(get_db(request))


def get_ingest_run_repo(request: Request) -> IngestRunRepository:
    """Factory for IngestRunRepository."""
    return IngestRunRepository(get_db(request))
