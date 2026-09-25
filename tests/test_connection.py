"""Tests for db/connection.py — connection manager."""

import sqlite3
import tempfile
from pathlib import Path

import pytest

from garsync.db.connection import BUSY_TIMEOUT_MS, get_connection

pytestmark = pytest.mark.unit


class TestGetConnection:
    def test_returns_connection(self) -> None:
        conn = get_connection(":memory:")
        assert isinstance(conn, sqlite3.Connection)
        conn.close()

    def test_row_factory_set(self) -> None:
        conn = get_connection(":memory:")
        conn.execute("CREATE TABLE t (a INT, b TEXT)")
        conn.execute("INSERT INTO t VALUES (1, 'x')")
        row = conn.execute("SELECT * FROM t").fetchone()
        assert row["a"] == 1
        assert row["b"] == "x"
        conn.close()

    def test_wal_mode_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = str(Path(tmp) / "test.db")
            conn = get_connection(db_path)
            mode = conn.execute("PRAGMA journal_mode").fetchone()
            assert mode[0] == "wal"
            conn.close()

    def test_foreign_keys_enabled(self) -> None:
        conn = get_connection(":memory:")
        fk = conn.execute("PRAGMA foreign_keys").fetchone()
        assert fk[0] == 1
        conn.close()

    def test_the_driver_leaves_transactions_to_the_caller(self) -> None:
        """A unit of work is opened by the layer that knows what one is — never by the driver.

        With an isolation level the driver starts a transaction behind the caller's back, and the
        same `commit()` that ends it also ends a transaction a *run* had opened (lesson 028).
        """
        conn = get_connection(":memory:")
        assert conn.isolation_level is None
        assert conn.in_transaction is False
        conn.close()

    def test_the_busy_timeout_is_stated_explicitly(self) -> None:
        """Already 5000 through pysqlite's `timeout=5.0`; stated so it is a decision (lesson 029)."""
        conn = get_connection(":memory:")
        assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == BUSY_TIMEOUT_MS
        conn.close()

    def test_file_based_connection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = str(Path(tmp) / "test.db")
            conn = get_connection(db_path)
            conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY)")
            conn.execute("INSERT INTO test VALUES (1)")
            conn.commit()
            conn.close()

            conn2 = get_connection(db_path)
            row = conn2.execute("SELECT id FROM test").fetchone()
            assert row["id"] == 1
            conn2.close()
