"""
database.py - Thread and message helpers using local SQLite.
"""

import glob
import os
import shutil

from fastapi import HTTPException

from db import execute

BASE_DIR = os.path.dirname(__file__)
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")
CHROMA_BASE = os.path.join(BASE_DIR, "chroma_store")


def create_thread(thread_id: str, user_id: str, title: str = "New Chat"):
    execute(
        """
        INSERT INTO threads (thread_id, user_id, title)
        VALUES (%s, %s, %s)
        ON CONFLICT(thread_id) DO NOTHING
        """,
        (thread_id, user_id, title),
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
        SELECT thread_id, title, created_at, updated_at
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


def delete_thread(thread_id: str):
    docs = execute(
        "SELECT doc_id FROM documents WHERE thread_id=%s",
        (thread_id,),
        fetch="all",
    )
    execute("DELETE FROM threads WHERE thread_id=%s", (thread_id,))
    execute("DELETE FROM documents WHERE thread_id=%s", (thread_id,))

    vector_dir = os.path.join(CHROMA_BASE, thread_id)

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


def save_message(thread_id: str, role: str, content: str):
    execute(
        "INSERT INTO messages (thread_id, role, content) VALUES (%s, %s, %s)",
        (thread_id, role, content),
    )


def get_thread_messages(thread_id: str):
    return execute(
        "SELECT role, content, created_at FROM messages WHERE thread_id=%s ORDER BY id ASC",
        (thread_id,),
        fetch="all",
    )


def init_db():
    from auth import ensure_admin_exists
    from db import init_all_tables

    init_all_tables()
    ensure_admin_exists()
