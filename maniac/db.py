"""SQLite storage for users and scores.

A single shared connection is used (the game is single-process). Tables are
created on first use. Scores reference the chart by ``song_id/mode/difficulty``
strings rather than a foreign key so charts can be freely added/removed on disk
without breaking historical scores.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional

from . import config

_conn: Optional[sqlite3.Connection] = None


def get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(str(config.DB_PATH))
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA foreign_keys = ON")
        _init_schema(_conn)
    return _conn


def _init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            username      TEXT UNIQUE NOT NULL,
            display_name  TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            salt          TEXT NOT NULL,
            is_admin      INTEGER NOT NULL DEFAULT 0,
            created_at    TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS scores (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            song_id     TEXT NOT NULL,
            mode        TEXT NOT NULL,
            difficulty  TEXT NOT NULL,
            score       INTEGER NOT NULL,
            max_combo   INTEGER NOT NULL,
            accuracy    REAL NOT NULL,
            grade       TEXT NOT NULL,
            perfects    INTEGER NOT NULL DEFAULT 0,
            greats      INTEGER NOT NULL DEFAULT 0,
            goods       INTEGER NOT NULL DEFAULT 0,
            misses      INTEGER NOT NULL DEFAULT 0,
            played_at   TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_scores_chart
            ON scores(song_id, mode, difficulty, score DESC);
        CREATE INDEX IF NOT EXISTS idx_scores_user ON scores(user_id);
        """
    )
    conn.commit()


def close() -> None:
    global _conn
    if _conn is not None:
        _conn.close()
        _conn = None
