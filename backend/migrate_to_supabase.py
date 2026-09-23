"""
migrate_to_supabase.py - One-time data transfer: local chatbot.db (SQLite) -> Supabase (Postgres).

Run this ONCE, locally, after:
  1. DATABASE_URL is set correctly in your .env (Supabase connection string)
  2. `pip install -r requirements.txt` has installed psycopg2-binary

Usage (from the project root or backend/ folder):
    python backend/migrate_to_supabase.py

What it does:
  - Reads every row out of backend/chatbot.db (the SQLite file)
  - Inserts it into the matching table on your Supabase Postgres database
  - Uses ON CONFLICT DO NOTHING, so it's safe to re-run if it fails partway through

What it does NOT migrate:
  - LangGraph's internal checkpoint/state table (used for mid-conversation model
    memory). That table's binary format is specific to the SQLite checkpointer and
    isn't compatible with the Postgres checkpointer. Your actual chat history
    (threads + messages, visible in the UI) IS migrated in full. The only effect is
    that the model won't "remember" earlier turns of an existing thread the very
    next time you message it -- it'll pick back up with full context from then on.
"""

import os
import sqlite3
import sys

import psycopg2
from psycopg2.extras import execute_values

BASE_DIR = os.path.dirname(__file__)
ROOT_DIR = os.path.abspath(os.path.join(BASE_DIR, ".."))
SQLITE_PATH = os.getenv("SQLITE_SOURCE_PATH", os.path.join(BASE_DIR, "chatbot.db"))

sys.path.insert(0, BASE_DIR)
from config import DATABASE_URL  # noqa: E402


TABLES = [
    # (table_name, [columns...])
    ("users", ["id", "email", "password_hash", "is_verified", "is_approved", "is_admin", "chat_count", "created_at"]),
    ("otps", ["id", "email", "otp", "purpose", "expires_at", "used"]),
    ("workspaces", ["workspace_id", "user_id", "name", "description", "created_at", "updated_at"]),
    ("threads", ["thread_id", "user_id", "title", "workspace_id", "created_at", "updated_at"]),
    ("messages", ["id", "thread_id", "role", "content", "metadata", "status", "created_at"]),
    ("documents", ["doc_id", "thread_id", "workspace_id", "filename", "file_type", "chunk_count", "status", "error", "extracted_preview", "uploaded_at", "updated_at"]),
    ("document_chunks", ["doc_id", "chunk_index", "page", "content", "created_at"]),
    ("thread_shares", ["thread_id", "user_id", "token", "created_at", "revoked_at"]),
    ("analytics_events", ["id", "user_id", "event_type", "reason", "metadata", "created_at"]),
]


def main():
    if not os.path.exists(SQLITE_PATH):
        print(f"No local SQLite database found at {SQLITE_PATH}. Nothing to migrate.")
        return

    print(f"Source (SQLite):  {SQLITE_PATH}")
    print(f"Target (Supabase): {DATABASE_URL.split('@')[-1] if '@' in DATABASE_URL else '(hidden)'}")
    print()

    sconn = sqlite3.connect(SQLITE_PATH)
    sconn.row_factory = sqlite3.Row
    scur = sconn.cursor()

    pconn = psycopg2.connect(DATABASE_URL)
    pconn.autocommit = False
    pcur = pconn.cursor()

    try:
        for table, columns in TABLES:
            try:
                scur.execute(f"SELECT {', '.join(columns)} FROM {table}")
            except sqlite3.OperationalError as exc:
                print(f"  skip {table}: {exc}")
                continue

            rows = scur.fetchall()
            if not rows:
                print(f"  {table}: 0 rows, skipping")
                continue

            values = [tuple(row[col] for col in columns) for row in rows]
            col_list = ", ".join(columns)
            conflict_col = columns[0]

            sql = (
                f"INSERT INTO {table} ({col_list}) VALUES %s "
                f"ON CONFLICT ({conflict_col}) DO NOTHING"
            )
            if table == "document_chunks":
                sql = (
                    f"INSERT INTO {table} ({col_list}) VALUES %s "
                    f"ON CONFLICT (doc_id, chunk_index) DO NOTHING"
                )

            execute_values(pcur, sql, values)
            pconn.commit()
            print(f"  {table}: migrated {len(values)} rows")

        # Realign Postgres auto-increment sequences with the migrated data,
        # otherwise the next INSERT without an explicit id could collide.
        for table, id_col in (("users", "id"), ("otps", "id"), ("messages", "id"), ("analytics_events", "id")):
            pcur.execute(
                f"SELECT setval(pg_get_serial_sequence('{table}', '{id_col}'), "
                f"COALESCE((SELECT MAX({id_col}) FROM {table}), 1))"
            )
        pconn.commit()

        print()
        print("Migration complete.")
    except Exception:
        pconn.rollback()
        raise
    finally:
        scur.close()
        sconn.close()
        pcur.close()
        pconn.close()


if __name__ == "__main__":
    main()
