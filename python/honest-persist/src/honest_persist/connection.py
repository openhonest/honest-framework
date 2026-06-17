"""Boundary: open + close a SQLite connection. SERIALIZABLE isolation."""
from __future__ import annotations

import sqlite3


def connect(path: str = ":memory:") -> sqlite3.Connection:
    """Open a SQLite connection with foreign keys + row factory enabled."""
    conn = sqlite3.connect(path, isolation_level=None)  # autocommit; we control txn
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    # SQLite doesn't have SERIALIZABLE; BEGIN IMMEDIATE gives single-writer.
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def close_connection(conn: sqlite3.Connection) -> None:
    conn.close()
