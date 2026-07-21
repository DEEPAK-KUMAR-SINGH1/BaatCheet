"""
migrations.py - Small SQLite schema migrations for local development.
"""


def _table_exists(cur, table_name: str) -> bool:
    row = cur.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone()
    return row is not None


def _column_exists(cur, table_name: str, column_name: str) -> bool:
    if not _table_exists(cur, table_name):
        return False
    rows = cur.execute(f"PRAGMA table_info({table_name})").fetchall()
    return any(row[1] == column_name for row in rows)


def _has_document_thread_fk(cur) -> bool:
    rows = cur.execute("PRAGMA foreign_key_list(documents)").fetchall()
    return any(row[2] == "threads" and row[3] == "thread_id" for row in rows)


def _run_once(cur, migration_id: str, fn):
    cur.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            id         TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    if cur.execute(
        "SELECT 1 FROM schema_migrations WHERE id=?",
        (migration_id,),
    ).fetchone():
        return
    fn(cur)
    cur.execute("INSERT INTO schema_migrations (id) VALUES (?)", (migration_id,))


def _add_documents_thread_fk(cur):
    if not _table_exists(cur, "documents") or _has_document_thread_fk(cur):
        return
    if _column_exists(cur, "documents", "workspace_id") and _column_exists(cur, "documents", "status"):
        return

    cur.execute("ALTER TABLE documents RENAME TO documents_old")
    cur.execute("""
        CREATE TABLE documents (
            doc_id            TEXT PRIMARY KEY,
            thread_id         TEXT NOT NULL REFERENCES threads(thread_id) ON DELETE CASCADE,
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
        INSERT INTO documents (
            doc_id, thread_id, workspace_id, filename, file_type, chunk_count,
            status, uploaded_at, updated_at
        )
        SELECT d.doc_id, d.thread_id, d.thread_id, d.filename, d.file_type,
               d.chunk_count, 'indexed', d.uploaded_at, d.uploaded_at
        FROM documents_old d
        WHERE EXISTS (
            SELECT 1 FROM threads t WHERE t.thread_id = d.thread_id
        )
    """)
    cur.execute("DROP TABLE documents_old")


def _add_v1_chat_upgrade_schema(cur):
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

    if not _column_exists(cur, "threads", "workspace_id"):
        cur.execute("ALTER TABLE threads ADD COLUMN workspace_id TEXT")
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_threads_workspace
        ON threads(workspace_id)
    """)

    if not _column_exists(cur, "messages", "metadata"):
        cur.execute("ALTER TABLE messages ADD COLUMN metadata TEXT NOT NULL DEFAULT '{}'")
    if not _column_exists(cur, "messages", "status"):
        cur.execute("ALTER TABLE messages ADD COLUMN status TEXT NOT NULL DEFAULT 'complete'")

    if not _column_exists(cur, "documents", "workspace_id"):
        cur.execute("ALTER TABLE documents ADD COLUMN workspace_id TEXT")
    if not _column_exists(cur, "documents", "status"):
        cur.execute("ALTER TABLE documents ADD COLUMN status TEXT NOT NULL DEFAULT 'indexed'")
    if not _column_exists(cur, "documents", "error"):
        cur.execute("ALTER TABLE documents ADD COLUMN error TEXT")
    if not _column_exists(cur, "documents", "extracted_preview"):
        cur.execute("ALTER TABLE documents ADD COLUMN extracted_preview TEXT")
    if not _column_exists(cur, "documents", "updated_at"):
        cur.execute("ALTER TABLE documents ADD COLUMN updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP")

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_documents_workspace
        ON documents(workspace_id, uploaded_at)
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

    # Backfill every legacy thread that already has documents into a same-id
    # workspace. This keeps existing Chroma directories usable without reindexing.
    cur.execute("""
        INSERT OR IGNORE INTO workspaces (workspace_id, user_id, name, created_at, updated_at)
        SELECT d.thread_id,
               t.user_id,
               COALESCE(NULLIF(t.title, ''), 'Imported documents'),
               MIN(d.uploaded_at),
               MAX(d.uploaded_at)
        FROM documents d
        JOIN threads t ON t.thread_id = d.thread_id
        WHERE d.workspace_id IS NULL OR d.workspace_id = '' OR d.workspace_id = d.thread_id
        GROUP BY d.thread_id, t.user_id, t.title
    """)
    cur.execute("""
        UPDATE documents
        SET workspace_id = thread_id
        WHERE workspace_id IS NULL OR workspace_id = ''
    """)
    cur.execute("""
        UPDATE threads
        SET workspace_id = thread_id
        WHERE workspace_id IS NULL
          AND EXISTS (
              SELECT 1 FROM documents d WHERE d.thread_id = threads.thread_id
          )
    """)


def _documents_have_thread_fk(cur) -> bool:
    if not _table_exists(cur, "documents"):
        return False
    rows = cur.execute("PRAGMA foreign_key_list(documents)").fetchall()
    return any(row[2] == "threads" and row[3] == "thread_id" for row in rows)


def _remove_documents_thread_fk(cur):
    if not _documents_have_thread_fk(cur):
        return

    cur.execute("ALTER TABLE documents RENAME TO documents_old")
    cur.execute("""
        CREATE TABLE documents (
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
        INSERT INTO documents (
            doc_id, thread_id, workspace_id, filename, file_type, chunk_count,
            status, error, extracted_preview, uploaded_at, updated_at
        )
        SELECT doc_id, thread_id, workspace_id, filename, file_type, chunk_count,
               status, error, extracted_preview, uploaded_at, updated_at
        FROM documents_old
    """)
    cur.execute("DROP TABLE documents_old")
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_documents_workspace
        ON documents(workspace_id, uploaded_at)
    """)


def _document_chunks_has_bad_fk(cur) -> bool:
    if not _table_exists(cur, "document_chunks"):
        return False
    rows = cur.execute("PRAGMA foreign_key_list(document_chunks)").fetchall()
    return any(row[2] != "documents" for row in rows)


def _rebuild_document_chunks_fk(cur):
    if not _document_chunks_has_bad_fk(cur):
        return

    cur.execute("ALTER TABLE document_chunks RENAME TO document_chunks_old")
    cur.execute("""
        CREATE TABLE document_chunks (
            doc_id      TEXT NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
            chunk_index INTEGER NOT NULL,
            page        INTEGER,
            content     TEXT NOT NULL,
            created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (doc_id, chunk_index)
        )
    """)
    cur.execute("""
        INSERT OR IGNORE INTO document_chunks (doc_id, chunk_index, page, content, created_at)
        SELECT doc_id, chunk_index, page, content, created_at
        FROM document_chunks_old
        WHERE EXISTS (
            SELECT 1 FROM documents d WHERE d.doc_id = document_chunks_old.doc_id
        )
    """)
    cur.execute("DROP TABLE document_chunks_old")


def run_migrations(conn):
    with conn:
        cur = conn.cursor()
        _run_once(cur, "001_documents_thread_fk", _add_documents_thread_fk)
        _run_once(cur, "002_v1_chat_upgrade", _add_v1_chat_upgrade_schema)
        _run_once(cur, "003_documents_independent_workspaces", _remove_documents_thread_fk)

        # Safety net for local/dev SQLite DBs that may have had an interrupted
        # startup or were restored from an older tracked chatbot.db file. These
        # functions are idempotent, so re-running them keeps startup safe.
        _add_v1_chat_upgrade_schema(cur)
        _remove_documents_thread_fk(cur)
        _rebuild_document_chunks_fk(cur)
