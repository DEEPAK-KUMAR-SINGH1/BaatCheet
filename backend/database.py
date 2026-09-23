"""
database.py - Thread, message, workspace, and sharing helpers using Supabase (Postgres).
"""

import glob
import json
import os
import secrets
import shutil

from fastapi import HTTPException

from db import execute

BASE_DIR = os.path.dirname(__file__)
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")
CHROMA_BASE = os.path.join(BASE_DIR, "chroma_store")


def _json_dumps(value) -> str:
    return json.dumps(value or {}, ensure_ascii=False)


def _json_loads(value):
    if not value:
        return {}
    if isinstance(value, dict):
        return value
    try:
        return json.loads(value)
    except Exception:
        return {}


def _hydrate_message(row):
    if not row:
        return row
    row["metadata"] = _json_loads(row.get("metadata"))
    return row


def _hydrate_messages(rows):
    return [_hydrate_message(row) for row in rows or []]


def create_thread(
    thread_id: str,
    user_id: str,
    title: str = "New Chat",
    workspace_id: str | None = None,
):
    execute(
        """
        INSERT INTO threads (thread_id, user_id, title, workspace_id)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT(thread_id) DO NOTHING
        """,
        (thread_id, user_id, title, workspace_id),
    )


def verify_thread_owner(thread_id: str, user_id: str):
    row = execute(
        "SELECT 1 FROM threads WHERE thread_id=%s AND user_id=%s",
        (thread_id, user_id),
        fetch="one",
    )
    if not row:
        raise HTTPException(status_code=403, detail="Access denied: not your thread")


def get_threads_for_user(user_id: str):
    return execute(
        """
        SELECT thread_id, title, workspace_id, created_at, updated_at
        FROM threads WHERE user_id=%s
        ORDER BY updated_at DESC
        """,
        (user_id,),
        fetch="all",
    )


def update_thread_title(thread_id: str, title: str):
    execute(
        "UPDATE threads SET title=%s, updated_at=CURRENT_TIMESTAMP WHERE thread_id=%s",
        (title, thread_id),
    )


def update_thread_timestamp(thread_id: str):
    execute(
        "UPDATE threads SET updated_at=CURRENT_TIMESTAMP WHERE thread_id=%s",
        (thread_id,),
    )


def get_thread(thread_id: str):
    return execute(
        "SELECT * FROM threads WHERE thread_id=%s",
        (thread_id,),
        fetch="one",
    )


def get_thread_workspace_id(thread_id: str):
    row = get_thread(thread_id)
    return row.get("workspace_id") if row else None


def update_thread_workspace(thread_id: str, workspace_id: str | None):
    execute(
        """
        UPDATE threads
        SET workspace_id=%s, updated_at=CURRENT_TIMESTAMP
        WHERE thread_id=%s
        """,
        (workspace_id, thread_id),
    )


def delete_thread(thread_id: str):
    thread = get_thread(thread_id)
    workspace_id = thread.get("workspace_id") if thread else None
    delete_owned_workspace = bool(workspace_id and workspace_id == thread_id)
    docs = []
    if delete_owned_workspace:
        docs = execute(
            "SELECT doc_id FROM documents WHERE workspace_id=%s",
            (workspace_id,),
            fetch="all",
        )
    execute("DELETE FROM threads WHERE thread_id=%s", (thread_id,))

    if not delete_owned_workspace:
        return

    execute("DELETE FROM documents WHERE workspace_id=%s", (workspace_id,))
    execute("DELETE FROM workspaces WHERE workspace_id=%s", (workspace_id,))

    vector_dir = os.path.join(CHROMA_BASE, workspace_id)

    try:
        if os.path.exists(vector_dir):
            shutil.rmtree(vector_dir)
        for doc in docs or []:
            for path in glob.glob(os.path.join(UPLOADS_DIR, f"{doc['doc_id']}.*")):
                if os.path.isfile(path):
                    os.remove(path)
    except Exception:
        # Thread deletion should still complete even if local file cleanup fails.
        pass


def save_message(
    thread_id: str,
    role: str,
    content: str,
    metadata: dict | None = None,
    status: str = "complete",
):
    row = execute(
        """
        INSERT INTO messages (thread_id, role, content, metadata, status)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id, role, content, metadata, status, created_at
        """,
        (thread_id, role, content, _json_dumps(metadata), status),
        fetch="returning",
    )
    return _hydrate_message(row)


def get_thread_messages(thread_id: str):
    rows = execute(
        """
        SELECT id, role, content, metadata, status, created_at
        FROM messages
        WHERE thread_id=%s
        ORDER BY id ASC
        """,
        (thread_id,),
        fetch="all",
    )
    return _hydrate_messages(rows)


def get_thread_messages_full(thread_id: str):
    rows = execute(
        """
        SELECT id, role, content, metadata, status, created_at
        FROM messages
        WHERE thread_id=%s
        ORDER BY id ASC
        """,
        (thread_id,),
        fetch="all",
    )
    return _hydrate_messages(rows)


def get_message(thread_id: str, message_id: int):
    row = execute(
        """
        SELECT id, role, content, metadata, status, created_at
        FROM messages
        WHERE thread_id=%s AND id=%s
        """,
        (thread_id, message_id),
        fetch="one",
    )
    return _hydrate_message(row)


def get_last_user_message(thread_id: str):
    row = execute(
        """
        SELECT id, role, content, metadata, status, created_at
        FROM messages
        WHERE thread_id=%s AND role='user'
        ORDER BY id DESC
        LIMIT 1
        """,
        (thread_id,),
        fetch="one",
    )
    return _hydrate_message(row)


def update_user_message_and_prune(thread_id: str, message_id: int, content: str):
    row = get_message(thread_id, message_id)
    if not row or row["role"] != "user":
        raise HTTPException(404, "User message not found")
    latest = get_last_user_message(thread_id)
    if not latest or latest["id"] != message_id:
        raise HTTPException(400, "Only the latest user message can be edited")
    execute(
        """
        UPDATE messages
        SET content=%s, metadata='{}', status='complete'
        WHERE thread_id=%s AND id=%s
        """,
        (content, thread_id, message_id),
    )
    execute(
        "DELETE FROM messages WHERE thread_id=%s AND id>%s",
        (thread_id, message_id),
    )
    update_thread_timestamp(thread_id)
    return get_thread_messages_full(thread_id)


def delete_messages_after(thread_id: str, message_id: int):
    execute(
        "DELETE FROM messages WHERE thread_id=%s AND id>%s",
        (thread_id, message_id),
    )


def create_workspace(user_id: str, name: str = "New Workspace", workspace_id: str | None = None):
    has_explicit_id = bool(workspace_id)
    workspace_id = workspace_id or secrets.token_urlsafe(16)
    if has_explicit_id:
        execute(
            """
            INSERT INTO workspaces (workspace_id, user_id, name)
            VALUES (%s, %s, %s)
            ON CONFLICT(workspace_id) DO NOTHING
            """,
            (workspace_id, user_id, name),
        )
        workspace = get_workspace(workspace_id)
        if workspace and workspace["user_id"] == user_id:
            return workspace
        raise HTTPException(status_code=409, detail="Workspace ID already exists")

    execute(
        """
        INSERT INTO workspaces (workspace_id, user_id, name)
        VALUES (%s, %s, %s)
        """,
        (workspace_id, user_id, name),
    )
    return get_workspace(workspace_id)


def get_workspace(workspace_id: str):
    return execute(
        "SELECT * FROM workspaces WHERE workspace_id=%s",
        (workspace_id,),
        fetch="one",
    )


def verify_workspace_owner(workspace_id: str, user_id: str):
    row = execute(
        "SELECT 1 FROM workspaces WHERE workspace_id=%s AND user_id=%s",
        (workspace_id, user_id),
        fetch="one",
    )
    if not row:
        raise HTTPException(status_code=403, detail="Access denied: not your workspace")


def list_workspaces_for_user(user_id: str):
    return execute(
        """
        SELECT w.*,
               COUNT(DISTINCT d.doc_id) AS document_count,
               COUNT(DISTINCT t.thread_id) AS thread_count
        FROM workspaces w
        LEFT JOIN documents d ON d.workspace_id = w.workspace_id
        LEFT JOIN threads t ON t.workspace_id = w.workspace_id
        WHERE w.user_id=%s
        GROUP BY w.workspace_id
        ORDER BY w.updated_at DESC
        """,
        (user_id,),
        fetch="all",
    )


def update_workspace(workspace_id: str, name: str, description: str | None = None):
    execute(
        """
        UPDATE workspaces
        SET name=%s,
            description=COALESCE(%s, description),
            updated_at=CURRENT_TIMESTAMP
        WHERE workspace_id=%s
        """,
        (name, description, workspace_id),
    )
    return get_workspace(workspace_id)


def delete_workspace(workspace_id: str):
    docs = execute(
        "SELECT doc_id FROM documents WHERE workspace_id=%s",
        (workspace_id,),
        fetch="all",
    )
    execute("UPDATE threads SET workspace_id=NULL WHERE workspace_id=%s", (workspace_id,))
    execute("DELETE FROM documents WHERE workspace_id=%s", (workspace_id,))
    execute("DELETE FROM workspaces WHERE workspace_id=%s", (workspace_id,))

    vector_dir = os.path.join(CHROMA_BASE, workspace_id)
    try:
        if os.path.exists(vector_dir):
            shutil.rmtree(vector_dir)
        for doc in docs or []:
            for path in glob.glob(os.path.join(UPLOADS_DIR, f"{doc['doc_id']}.*")):
                if os.path.isfile(path):
                    os.remove(path)
    except Exception:
        pass


def save_document_record(
    doc_id: str,
    thread_id: str,
    workspace_id: str,
    filename: str,
    file_type: str,
    status: str = "processing",
    chunk_count: int = 0,
    error: str | None = None,
    extracted_preview: str | None = None,
):
    execute(
        """
        INSERT INTO documents (
            doc_id, thread_id, workspace_id, filename, file_type,
            chunk_count, status, error, extracted_preview
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            doc_id, thread_id, workspace_id, filename, file_type,
            chunk_count, status, error, extracted_preview,
        ),
    )
    return get_document(doc_id)


def update_document_status(
    doc_id: str,
    status: str,
    chunk_count: int | None = None,
    error: str | None = None,
    extracted_preview: str | None = None,
):
    execute(
        """
        UPDATE documents
        SET status=%s,
            chunk_count=COALESCE(%s, chunk_count),
            error=%s,
            extracted_preview=COALESCE(%s, extracted_preview),
            updated_at=CURRENT_TIMESTAMP
        WHERE doc_id=%s
        """,
        (status, chunk_count, error, extracted_preview, doc_id),
    )
    return get_document(doc_id)


def get_document(doc_id: str):
    return execute("SELECT * FROM documents WHERE doc_id=%s", (doc_id,), fetch="one")


def get_workspace_documents(workspace_id: str):
    return execute(
        "SELECT * FROM documents WHERE workspace_id=%s ORDER BY uploaded_at ASC",
        (workspace_id,),
        fetch="all",
    )


def delete_document_record(doc_id: str):
    execute("DELETE FROM documents WHERE doc_id=%s", (doc_id,))


def list_admin_threads(limit: int = 50):
    limit = max(1, min(int(limit or 50), 200))
    return execute(
        """
        SELECT
            t.thread_id,
            t.user_id,
            t.title,
            t.workspace_id,
            t.created_at,
            t.updated_at,
            COUNT(m.id) AS message_count,
            SUM(CASE WHEN m.role='user' THEN 1 ELSE 0 END) AS user_messages,
            MAX(m.created_at) AS last_message_at
        FROM threads t
        LEFT JOIN messages m ON m.thread_id = t.thread_id
        GROUP BY t.thread_id
        ORDER BY COALESCE(MAX(m.created_at), t.updated_at, t.created_at) DESC
        LIMIT %s
        """,
        (limit,),
        fetch="all",
    )


def list_admin_documents(limit: int = 50):
    limit = max(1, min(int(limit or 50), 200))
    return execute(
        """
        SELECT
            d.doc_id,
            d.thread_id,
            d.workspace_id,
            d.filename,
            d.file_type,
            d.chunk_count,
            d.status,
            d.error,
            d.uploaded_at,
            d.updated_at,
            t.user_id,
            t.title AS thread_title,
            w.name AS workspace_name
        FROM documents d
        LEFT JOIN threads t ON t.thread_id = d.thread_id
        LEFT JOIN workspaces w ON w.workspace_id = d.workspace_id
        ORDER BY d.uploaded_at DESC
        LIMIT %s
        """,
        (limit,),
        fetch="all",
    )


def replace_document_chunks(doc_id: str, chunks: list[dict]):
    execute("DELETE FROM document_chunks WHERE doc_id=%s", (doc_id,))
    for chunk in chunks:
        execute(
            """
            INSERT INTO document_chunks (doc_id, chunk_index, page, content)
            VALUES (%s, %s, %s, %s)
            """,
            (
                doc_id,
                chunk["chunk_index"],
                chunk.get("page"),
                chunk["content"],
            ),
        )


def get_document_chunk(doc_id: str, chunk_index: int):
    return execute(
        """
        SELECT dc.*, d.filename, d.workspace_id
        FROM document_chunks dc
        JOIN documents d ON d.doc_id = dc.doc_id
        WHERE dc.doc_id=%s AND dc.chunk_index=%s
        """,
        (doc_id, chunk_index),
        fetch="one",
    )


def search_user_threads(user_id: str, query: str, limit: int = 30):
    like = f"%{query}%"
    return execute(
        """
        SELECT t.thread_id,
               t.title,
               t.updated_at,
               'thread' AS match_type,
               t.title AS snippet
        FROM threads t
        WHERE t.user_id=%s AND t.title LIKE %s
        UNION ALL
        SELECT t.thread_id,
               t.title,
               m.created_at AS updated_at,
               'message' AS match_type,
               substr(m.content, 1, 240) AS snippet
        FROM messages m
        JOIN threads t ON t.thread_id = m.thread_id
        WHERE t.user_id=%s AND m.content LIKE %s
        UNION ALL
        SELECT t.thread_id,
               t.title,
               d.uploaded_at AS updated_at,
               'document' AS match_type,
               d.filename AS snippet
        FROM documents d
        JOIN threads t ON t.thread_id = d.thread_id
        WHERE t.user_id=%s AND d.filename LIKE %s
        ORDER BY updated_at DESC
        LIMIT %s
        """,
        (user_id, like, user_id, like, user_id, like, limit),
        fetch="all",
    )


def create_or_refresh_share(thread_id: str, user_id: str):
    token = secrets.token_urlsafe(24)
    execute(
        """
        INSERT INTO thread_shares (thread_id, user_id, token)
        VALUES (%s, %s, %s)
        ON CONFLICT(thread_id) DO UPDATE SET
            token=excluded.token,
            revoked_at=NULL,
            created_at=CURRENT_TIMESTAMP
        """,
        (thread_id, user_id, token),
    )
    return get_share_for_thread(thread_id, user_id)


def get_share_for_thread(thread_id: str, user_id: str):
    return execute(
        """
        SELECT * FROM thread_shares
        WHERE thread_id=%s AND user_id=%s AND revoked_at IS NULL
        """,
        (thread_id, user_id),
        fetch="one",
    )


def revoke_share(thread_id: str, user_id: str):
    execute(
        """
        UPDATE thread_shares
        SET revoked_at=CURRENT_TIMESTAMP
        WHERE thread_id=%s AND user_id=%s
        """,
        (thread_id, user_id),
    )


def get_public_share(token: str):
    share = execute(
        """
        SELECT s.*, t.title
        FROM thread_shares s
        JOIN threads t ON t.thread_id = s.thread_id
        WHERE s.token=%s AND s.revoked_at IS NULL
        """,
        (token,),
        fetch="one",
    )
    if not share:
        return None
    share["messages"] = [
        {
            "role": msg["role"],
            "content": msg["content"],
            "status": msg["status"],
            "created_at": msg["created_at"],
        }
        for msg in get_thread_messages_full(share["thread_id"])
    ]
    return share


def record_event(user_id: str | None, event_type: str, reason: str | None = None, metadata: dict | None = None):
    execute(
        """
        INSERT INTO analytics_events (user_id, event_type, reason, metadata)
        VALUES (%s, %s, %s, %s)
        """,
        (user_id, event_type, reason, _json_dumps(metadata)),
    )


def get_admin_analytics(days: int = 30):
    days = max(1, min(days, 365))
    daily_active = execute(
        """
        SELECT date(m.created_at) AS day, COUNT(DISTINCT t.user_id) AS users
        FROM messages m
        JOIN threads t ON t.thread_id = m.thread_id
        WHERE m.created_at >= NOW() - (%s || ' days')::interval
        GROUP BY date(m.created_at)
        ORDER BY day DESC
        """,
        (days,),
        fetch="all",
    )
    chats_per_user = execute(
        """
        SELECT t.user_id AS email, COUNT(*) AS chats
        FROM messages m
        JOIN threads t ON t.thread_id = m.thread_id
        WHERE m.role='user' AND m.created_at >= NOW() - (%s || ' days')::interval
        GROUP BY t.user_id
        ORDER BY chats DESC, email ASC
        LIMIT 20
        """,
        (days,),
        fetch="all",
    )
    documents_uploaded = execute(
        """
        SELECT date(uploaded_at) AS day, COUNT(*) AS documents
        FROM documents
        WHERE uploaded_at >= NOW() - (%s || ' days')::interval
        GROUP BY date(uploaded_at)
        ORDER BY day DESC
        """,
        (days,),
        fetch="all",
    )
    approval_queue = execute(
        """
        SELECT email,
               created_at,
               CAST(EXTRACT(EPOCH FROM (NOW() - created_at)) / 3600 AS INTEGER) AS age_hours
        FROM users
        WHERE is_admin=0 AND is_approved=0
        ORDER BY created_at ASC
        LIMIT 50
        """,
        fetch="all",
    )
    top_failures = execute(
        """
        SELECT COALESCE(reason, 'unknown') AS reason, COUNT(*) AS count
        FROM analytics_events
        WHERE event_type='failure'
          AND created_at >= NOW() - (%s || ' days')::interval
        GROUP BY COALESCE(reason, 'unknown')
        ORDER BY count DESC, reason ASC
        LIMIT 10
        """,
        (days,),
        fetch="all",
    )
    totals = execute(
        """
        SELECT
            (SELECT COUNT(*) FROM users WHERE is_admin=0) AS users,
            (SELECT COUNT(*) FROM threads) AS threads,
            (SELECT COUNT(*) FROM messages WHERE role='user') AS chats,
            (SELECT COUNT(*) FROM documents) AS documents,
            (SELECT COUNT(*) FROM documents WHERE status='failed') AS failed_documents
        """,
        fetch="one",
    )
    return {
        "daily_active_users": daily_active,
        "chats_per_user": chats_per_user,
        "documents_uploaded": documents_uploaded,
        "approval_queue": approval_queue,
        "top_failure_reasons": top_failures,
        "totals": totals or {},
    }


def init_db():
    from auth import ensure_admin_exists
    from db import init_all_tables

    init_all_tables()
    ensure_admin_exists()
