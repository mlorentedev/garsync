"""Tests for db/connection.py — connection manager."""

import sqlite3
import tempfile
from pathlib import Path

from garsync.db.connection import get_connection


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
