"""
migrations.py - Small SQLite schema migrations for local development.
"""


def _has_document_thread_fk(cur) -> bool:
    rows = cur.execute("PRAGMA foreign_key_list(documents)").fetchall()
    return any(row[2] == "threads" and row[3] == "thread_id" for row in rows)


def _documents_table_exists(cur) -> bool:
    row = cur.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='documents'"
    ).fetchone()
    return row is not None


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
    if not _documents_table_exists(cur) or _has_document_thread_fk(cur):
        return

    cur.execute("ALTER TABLE documents RENAME TO documents_old")
    cur.execute("""
        CREATE TABLE documents (
            doc_id      TEXT PRIMARY KEY,
            thread_id   TEXT NOT NULL REFERENCES threads(thread_id) ON DELETE CASCADE,
            filename    TEXT NOT NULL,
            file_type   TEXT NOT NULL,
            chunk_count INTEGER NOT NULL DEFAULT 0,
            uploaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("""
        INSERT INTO documents (doc_id, thread_id, filename, file_type, chunk_count, uploaded_at)
        SELECT d.doc_id, d.thread_id, d.filename, d.file_type, d.chunk_count, d.uploaded_at
        FROM documents_old d
        WHERE EXISTS (
            SELECT 1 FROM threads t WHERE t.thread_id = d.thread_id
        )
    """)
    cur.execute("DROP TABLE documents_old")


def run_migrations(conn):
    with conn:
        cur = conn.cursor()
        _run_once(cur, "001_documents_thread_fk", _add_documents_thread_fk)
