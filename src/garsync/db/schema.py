"""Schema management — the single entry point that runs the Alembic chain.

There is no DDL in this module. The schema is owned by the revisions in `migrations/`, and this file
exists for two things that nothing else can do for us:

**Handing Alembic the connection the caller already holds.** Alembic wants a
`sqlalchemy.engine.Connection`, and it has to be *this* one: a connection it opened for itself would
be a different database, and for the `:memory:` fixtures this suite builds it would be an empty one —
which is how a suite ends up green against nothing.

**Making the run atomic.** SQLite commits DDL implicitly *unless a transaction is already open*, and
in its legacy mode pysqlite never opens one for DDL. So a chain run without an explicit `BEGIN` is a
series of independent commits, and a revision that fails half-way leaves a database that is neither
v1 nor v2. The bridge below is what closes that hole; the seam tests measure it rather than trusting
this paragraph.

`init_db` converges three starting points, because the project has all three: an empty database, a v1
database created by the pre-Alembic DDL (its `schema_version` row is the fingerprint), and one already
on the chain.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.pool import StaticPool

from garsync.db.backup import snapshot
from garsync.db.connection import get_connection

MIGRATIONS_DIR = Path(__file__).parent / "migrations"

# The revision a v1 database is stamped at before it is upgraded: the baseline, which reproduces the
# v1 schema exactly (`TestAlembicSeam::test_the_baseline_reproduces_the_v1_schema`).
V1_BASELINE_REVISION = "0001_v1"

_ALEMBIC_TABLE = "alembic_version"


def _config(connection: object) -> Config:
    """An Alembic config carrying the caller's connection and deliberately no URL."""
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    config.attributes["connection"] = connection
    return config


def _bridged_engine(conn: sqlite3.Connection) -> Engine:
    """A SQLAlchemy engine that hands Alembic exactly the connection it was given.

    `StaticPool` returns the DBAPI connection it was handed rather than opening another, and
    `dispose(close=False)` returns it without closing it — so the caller keeps a live, usable
    connection afterwards.

    The `connect` listener removes the driver's implicit `BEGIN` (which pysqlite only ever emits for
    DML) and the `begin` listener issues `BEGIN` explicitly, so every statement a revision runs —
    including its DDL — lands inside one transaction. Without both, the migration is a series of
    autocommits wearing the appearance of a transaction.
    """
    engine = create_engine("sqlite://", creator=lambda: conn, poolclass=StaticPool)

    @event.listens_for(engine, "connect")
    def _take_the_implicit_begin_away(
        dbapi_connection: sqlite3.Connection, _record: object
    ) -> None:
        dbapi_connection.isolation_level = None

    @event.listens_for(engine, "begin")
    def _begin_explicitly(sa_connection: object) -> None:
        sa_connection.exec_driver_sql("BEGIN")  # type: ignore[attr-defined]

    return engine


def _run_alembic(conn: sqlite3.Connection, run: Callable[[Config], None]) -> None:
    """Run one Alembic command against `conn`, transactionally, and leave it as it was found."""
    original_isolation_level = conn.isolation_level
    engine = _bridged_engine(conn)
    try:
        with engine.connect() as sa_connection:
            run(_config(sa_connection))
    finally:
        engine.dispose(close=False)
        conn.isolation_level = original_isolation_level


def migrate(conn: sqlite3.Connection, revision: str = "head") -> None:
    """Upgrade `conn` to `revision`."""
    _run_alembic(conn, lambda config: command.upgrade(config, revision))


def downgrade(conn: sqlite3.Connection, revision: str) -> None:
    """Take `conn` back to `revision`. Production is forward-only (design §4.1)."""
    _run_alembic(conn, lambda config: command.downgrade(config, revision))


def _user_tables(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    return {_value(row) for row in rows} - {_ALEMBIC_TABLE}


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?", (name,)
    ).fetchone()
    return row is not None


def _value(row: object) -> str:
    """A column from a row, whether the connection has a Row factory or not."""
    return str(row[0])  # type: ignore[index]


def _revision(conn: sqlite3.Connection) -> str | None:
    if not _table_exists(conn, _ALEMBIC_TABLE):
        return None
    rows = conn.execute(f"SELECT version_num FROM {_ALEMBIC_TABLE}").fetchall()
    return _value(rows[0]) if rows else None


def _is_v1(conn: sqlite3.Connection) -> bool:
    """v1 identifies itself with `schema_version` — the table the chain is replacing."""
    if "schema_version" not in _user_tables(conn):
        return False
    rows = conn.execute("SELECT version FROM schema_version").fetchall()
    return bool(rows) and _value(rows[0]) == "1"


def _stamp_baseline(conn: sqlite3.Connection) -> None:
    """Record that this database already *is* the baseline, instead of recreating it."""
    _run_alembic(conn, lambda config: command.stamp(config, V1_BASELINE_REVISION))


def init_db(conn: sqlite3.Connection) -> None:
    """Bring `conn` up to the current revision. Idempotent — safe to call repeatedly."""
    if _revision(conn) is not None:
        migrate(conn)
        return

    if _is_v1(conn):
        # Stamp, then upgrade. Two transactions on purpose: should the upgrade fail, the database
        # is left correctly stamped at the baseline rather than claimed as something it is not.
        _stamp_baseline(conn)
        migrate(conn)
        return

    if not _user_tables(conn):
        migrate(conn)
        return

    raise RuntimeError(
        "Unrecognised database: it is neither empty, nor versioned, nor a v1 database with a "
        f"`schema_version` row (tables found: {', '.join(sorted(_user_tables(conn)))}). Refusing "
        "to guess which revision it is on — stamp it explicitly with `alembic stamp <revision>` "
        "once you have identified it."
    )


def head_revision() -> str:
    """The revision the chain ends at.

    A chain without a head is a chain without revisions — a broken checkout rather than a state to
    handle quietly.
    """
    head = ScriptDirectory.from_config(_config(None)).get_current_head()
    if head is None:
        raise RuntimeError(f"the migration chain at {MIGRATIONS_DIR} has no head revision")
    return head


def open_database(db_path: str) -> sqlite3.Connection:
    """Open a database file, snapshot it if a migration is pending, then migrate it.

    The snapshot happens here rather than inside `init_db`, because `init_db` is handed a connection
    and evidence of nothing else: whether a *file* is about to be rewritten is knowledge only this
    function has. A database already at head is opened without one — a backup of a no-op is noise.
    """
    conn = get_connection(db_path)
    try:
        path = Path(db_path)
        if path.exists() and _user_tables(conn) and _revision(conn) != head_revision():
            snapshot(conn, path)
        init_db(conn)
    except BaseException:
        conn.close()
        raise
    return conn


__all__ = [
    "MIGRATIONS_DIR",
    "V1_BASELINE_REVISION",
    "downgrade",
    "head_revision",
    "init_db",
    "migrate",
    "open_database",
]
