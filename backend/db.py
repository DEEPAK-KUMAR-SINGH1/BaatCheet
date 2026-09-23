"""
db.py - Central Supabase (Postgres) connection pool and table initialization.
"""

from datetime import datetime
from typing import Any

import psycopg2
import psycopg2.pool
from psycopg2.extras import RealDictCursor

from config import DATABASE_URL

_pool: psycopg2.pool.ThreadedConnectionPool | None = None


def _get_pool() -> psycopg2.pool.ThreadedConnectionPool:
    global _pool
    if _pool is None:
        _pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=10,
            dsn=DATABASE_URL,
        )
    return _pool


def _adapt_param(value: Any) -> Any:
    # psycopg2 adapts datetime objects natively; leave everything else as-is.
    return value


def _adapt_params(params):
    if params is None:
        return None
    if isinstance(params, dict):
        return {key: _adapt_param(value) for key, value in params.items()}
    return tuple(_adapt_param(value) for value in params)


def execute(query: str, params=None, fetch: str = None):
    """
    Run one query and optionally return results.
    fetch = None        -> execute only
    fetch = 'one'       -> one dict or None
    fetch = 'all'       -> list of dicts
    fetch = 'returning' -> one dict or None

    Query text already uses %s placeholders (psycopg2's native style), so
    no rewriting is needed here.
    """
    pool = _get_pool()
    conn = pool.getconn()
    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, _adapt_params(params) or None)
                if fetch in {"one", "returning"}:
                    row = cur.fetchone()
                    return dict(row) if row else None
                if fetch == "all":
                    return [dict(row) for row in cur.fetchall()]
                return None
    finally:
        pool.putconn(conn)


def init_all_tables():
    """Create application tables in Supabase if they do not exist yet."""
    ddl_statements = [
        """
        CREATE TABLE IF NOT EXISTS users (
            id            BIGSERIAL PRIMARY KEY,
            email         TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            is_verified   INTEGER NOT NULL DEFAULT 0,
            is_approved   INTEGER NOT NULL DEFAULT 0,
            is_admin      INTEGER NOT NULL DEFAULT 0,
            chat_count    INTEGER NOT NULL DEFAULT 0,
            created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS otps (
            id         BIGSERIAL PRIMARY KEY,
            email      TEXT NOT NULL,
            otp        TEXT NOT NULL,
            purpose    TEXT NOT NULL,
            expires_at TIMESTAMPTZ NOT NULL,
            used       INTEGER NOT NULL DEFAULT 0
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS workspaces (
            workspace_id TEXT PRIMARY KEY,
            user_id      TEXT NOT NULL,
            name         TEXT NOT NULL,
            description  TEXT NOT NULL DEFAULT '',
            created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_workspaces_user ON workspaces(user_id, updated_at)",
        """
        CREATE TABLE IF NOT EXISTS threads (
            thread_id    TEXT PRIMARY KEY,
            user_id      TEXT NOT NULL DEFAULT '',
            title        TEXT NOT NULL DEFAULT 'New Chat',
            workspace_id TEXT,
            created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_threads_user ON threads(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_threads_workspace ON threads(workspace_id)",
        """
        CREATE TABLE IF NOT EXISTS messages (
            id         BIGSERIAL PRIMARY KEY,
            thread_id  TEXT NOT NULL REFERENCES threads(thread_id) ON DELETE CASCADE,
            role       TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
            content    TEXT NOT NULL,
            metadata   TEXT NOT NULL DEFAULT '{}',
            status     TEXT NOT NULL DEFAULT 'complete',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """,
        """
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
            uploaded_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_documents_workspace ON documents(workspace_id, uploaded_at)",
        """
        CREATE TABLE IF NOT EXISTS document_chunks (
            doc_id      TEXT NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
            chunk_index INTEGER NOT NULL,
            page        INTEGER,
            content     TEXT NOT NULL,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (doc_id, chunk_index)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS thread_shares (
            thread_id  TEXT PRIMARY KEY REFERENCES threads(thread_id) ON DELETE CASCADE,
            user_id    TEXT NOT NULL,
            token      TEXT UNIQUE NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            revoked_at TIMESTAMPTZ
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS analytics_events (
            id         BIGSERIAL PRIMARY KEY,
            user_id    TEXT,
            event_type TEXT NOT NULL,
            reason     TEXT,
            metadata   TEXT NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_analytics_events_type_time ON analytics_events(event_type, created_at)",
    ]

    pool = _get_pool()
    conn = pool.getconn()
    try:
        with conn:
            with conn.cursor() as cur:
                for statement in ddl_statements:
                    cur.execute(statement)
    finally:
        pool.putconn(conn)
    print("Supabase (Postgres) tables initialized.")
