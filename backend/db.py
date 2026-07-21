"""
db.py - Central SQLite connection and table initialization.
"""

import os
import sqlite3
from datetime import datetime
from typing import Any

from config import DATABASE_PATH
from migrations import run_migrations


def _adapt_param(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _adapt_params(params):
    if params is None:
        return None
    if isinstance(params, dict):
        return {key: _adapt_param(value) for key, value in params.items()}
    return tuple(_adapt_param(value) for value in params)


def get_conn():
    """Return a fresh SQLite connection with dict-style rows."""
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def execute(query: str, params=None, fetch: str = None):
    """
    Run one query and optionally return results.
    fetch = None        -> execute only
    fetch = 'one'       -> one dict or None
    fetch = 'all'       -> list of dicts
    fetch = 'returning' -> one dict or None
    """
    sqlite_query = query.replace("%s", "?")
    conn = get_conn()
    try:
        with conn:
            cur = conn.execute(sqlite_query, _adapt_params(params) or ())
            if fetch in {"one", "returning"}:
                row = cur.fetchone()
                return dict(row) if row else None
            if fetch == "all":
                return [dict(row) for row in cur.fetchall()]
            return None
    finally:
        conn.close()


def init_all_tables():
    """Create application tables if they do not exist."""
    conn = get_conn()
    try:
        with conn:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    email         TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    is_verified   INTEGER NOT NULL DEFAULT 0,
                    is_approved   INTEGER NOT NULL DEFAULT 0,
                    is_admin      INTEGER NOT NULL DEFAULT 0,
                    chat_count    INTEGER NOT NULL DEFAULT 0,
                    created_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS otps (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    email      TEXT NOT NULL,
                    otp        TEXT NOT NULL,
                    purpose    TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    used       INTEGER NOT NULL DEFAULT 0
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS workspaces (
                    workspace_id TEXT PRIMARY KEY,
                    user_id      TEXT NOT NULL,
                    name         TEXT NOT NULL,
                    description  TEXT NOT NULL DEFAULT '',
                    created_at   TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at   TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_workspaces_user
                ON workspaces(user_id, updated_at)
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS threads (
                    thread_id    TEXT PRIMARY KEY,
                    user_id      TEXT NOT NULL DEFAULT '',
                    title        TEXT NOT NULL DEFAULT 'New Chat',
                    workspace_id TEXT,
                    created_at   TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at   TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_threads_user
                ON threads(user_id)
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    thread_id  TEXT NOT NULL REFERENCES threads(thread_id) ON DELETE CASCADE,
                    role       TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
                    content    TEXT NOT NULL,
                    metadata   TEXT NOT NULL DEFAULT '{}',
                    status     TEXT NOT NULL DEFAULT 'complete',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    doc_id            TEXT PRIMARY KEY,
                    thread_id         TEXT NOT NULL,
                    workspace_id      TEXT,
                    filename          TEXT NOT NULL,
                    file_type         TEXT NOT NULL,
                    chunk_count       INTEGER NOT NULL DEFAULT 0,
                    status            TEXT NOT NULL DEFAULT 'indexed',
                    error             TEXT,
                    extracted_preview TEXT,
                    uploaded_at       TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at        TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS document_chunks (
                    doc_id      TEXT NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
                    chunk_index INTEGER NOT NULL,
                    page        INTEGER,
                    content     TEXT NOT NULL,
                    created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (doc_id, chunk_index)
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS thread_shares (
                    thread_id  TEXT PRIMARY KEY REFERENCES threads(thread_id) ON DELETE CASCADE,
                    user_id    TEXT NOT NULL,
                    token      TEXT UNIQUE NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    revoked_at TEXT
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS analytics_events (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id    TEXT,
                    event_type TEXT NOT NULL,
                    reason     TEXT,
                    metadata   TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_analytics_events_type_time
                ON analytics_events(event_type, created_at)
            """)
            run_migrations(conn)
    finally:
        conn.close()
    print("SQLite tables initialized.")
