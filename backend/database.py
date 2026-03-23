import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), 'chatbot.db')

def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Create tables if not exist"""
    conn = get_conn()
    cursor = conn.cursor()

    # Threads table — har conversation ka record
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS threads (
            thread_id   TEXT PRIMARY KEY,
            title       TEXT DEFAULT 'New Chat',
            created_at  TEXT DEFAULT (datetime('now')),
            updated_at  TEXT DEFAULT (datetime('now'))
        )
    ''')

    # Messages table — har message ka record
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            thread_id   TEXT NOT NULL,
            role        TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
            content     TEXT NOT NULL,
            created_at  TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (thread_id) REFERENCES threads(thread_id)
        )
    ''')

    conn.commit()
    conn.close()

def create_thread(thread_id: str, title: str = "New Chat"):
    conn = get_conn()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO threads (thread_id, title) VALUES (?, ?)",
            (thread_id, title)
        )
        conn.commit()
    finally:
        conn.close()

def update_thread_title(thread_id: str, title: str):
    conn = get_conn()
    try:
        conn.execute(
            "UPDATE threads SET title = ?, updated_at = ? WHERE thread_id = ?",
            (title, datetime.now().isoformat(), thread_id)
        )
        conn.commit()
    finally:
        conn.close()

def update_thread_timestamp(thread_id: str):
    conn = get_conn()
    try:
        conn.execute(
            "UPDATE threads SET updated_at = ? WHERE thread_id = ?",
            (datetime.now().isoformat(), thread_id)
        )
        conn.commit()
    finally:
        conn.close()

def save_message(thread_id: str, role: str, content: str):
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO messages (thread_id, role, content) VALUES (?, ?, ?)",
            (thread_id, role, content)
        )
        conn.commit()
    finally:
        conn.close()

def get_all_threads():
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT thread_id, title, created_at, updated_at FROM threads ORDER BY updated_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def get_thread_messages(thread_id: str):
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT role, content, created_at FROM messages WHERE thread_id = ? ORDER BY id ASC",
            (thread_id,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def delete_thread(thread_id: str):
    conn = get_conn()
    try:
        conn.execute("DELETE FROM messages WHERE thread_id = ?", (thread_id,))
        conn.execute("DELETE FROM threads WHERE thread_id = ?", (thread_id,))
        conn.commit()
    finally:
        conn.close()

# App start hote hi DB init ho jaye
init_db()
