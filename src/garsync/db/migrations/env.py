"""Alembic environment — driven by the caller's connection, never by a URL.

The connection is required. Alembic opening one from a URL would be a *second* connection, and for
SQLite `:memory:` a second connection is a second, empty database: the fixtures in this suite would
then assert against nothing while the whole suite stayed green. A run with no connection is a
configuration error and says so.
"""

from __future__ import annotations

from alembic import context


def run_migrations_offline() -> None:
    """Offline mode is not supported, and refusing is the point.

    `--sql` output cannot be reviewed the way this chain is reviewed: it issues its own SQL and is
    only ever run against a database somebody has already backed up (see `make db-backup`).
    """
    raise RuntimeError(
        "Offline mode is not supported. The garsync chain is run by "
        "`garsync.db.schema.init_db` on a live connection, so that the schema lands on the same "
        "database the application is about to use."
    )


def run_migrations_online() -> None:
    connection = context.config.attributes.get("connection")
    if connection is None:
        raise RuntimeError(
            "No connection was supplied to the migration chain. Pass the connection the "
            "application already holds via `config.attributes['connection']` — that is what "
            "`garsync.db.schema.init_db` does. Alembic is deliberately not given a URL here: a "
            "connection it opened itself would be a different database from the caller's."
        )
    context.configure(connection=connection, target_metadata=None)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
