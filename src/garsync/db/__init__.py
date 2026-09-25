"""Database package for garsync — SQLite persistence layer."""

from garsync.db.connection import get_connection
from garsync.db.repository import (
    ActivityRepository,
    BiometricsRepository,
    IngestRunRepository,
    SleepRepository,
)
from garsync.db.schema import init_db, migrate, open_database

__all__ = [
    "ActivityRepository",
    "BiometricsRepository",
    "IngestRunRepository",
    "SleepRepository",
    "get_connection",
    "init_db",
    "migrate",
    "open_database",
]
