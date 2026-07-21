import os
import sys
from pathlib import Path

import pytest


BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_DIR))


@pytest.fixture()
def isolated_db(tmp_path, monkeypatch):
    import db

    test_db = tmp_path / "chatbot-test.db"
    monkeypatch.setattr(db, "DATABASE_PATH", str(test_db))
    db.init_all_tables()
    return db


def test_thread_owner_check_blocks_other_users(isolated_db):
    import database

    database.create_thread("thread-a", "owner@example.com")

    database.verify_thread_owner("thread-a", "owner@example.com")
    with pytest.raises(Exception):
        database.verify_thread_owner("thread-a", "other@example.com")


def test_workspace_documents_can_outlive_origin_thread(isolated_db):
    import database

    database.create_thread("thread-a", "owner@example.com")
    database.create_thread("thread-b", "owner@example.com")
    workspace = database.create_workspace("owner@example.com", "Shared", "workspace-a")
    database.update_thread_workspace("thread-a", workspace["workspace_id"])
    database.update_thread_workspace("thread-b", workspace["workspace_id"])
    isolated_db.execute(
        """
        INSERT INTO documents (doc_id, thread_id, workspace_id, filename, file_type)
        VALUES (%s, %s, %s, %s, %s)
        """,
        ("doc-a", "thread-a", "workspace-a", "shared.pdf", ".pdf"),
    )

    database.delete_thread("thread-a")

    assert isolated_db.execute(
        "SELECT * FROM documents WHERE workspace_id=%s",
        ("workspace-a",),
        fetch="all",
    )


def test_create_workspace_with_explicit_id_is_idempotent_for_owner(isolated_db):
    import database

    first = database.create_workspace("owner@example.com", "Thread docs", "thread-a")
    second = database.create_workspace("owner@example.com", "Thread docs", "thread-a")

    assert second["workspace_id"] == first["workspace_id"]
    assert isolated_db.execute(
        "SELECT COUNT(*) AS count FROM workspaces WHERE workspace_id=%s",
        ("thread-a",),
        fetch="one",
    )["count"] == 1


def test_create_workspace_with_explicit_id_rejects_other_owner(isolated_db):
    import database

    database.create_workspace("owner@example.com", "Thread docs", "thread-a")

    with pytest.raises(Exception):
        database.create_workspace("other@example.com", "Thread docs", "thread-a")


def test_delete_thread_removes_document_records_uploads_and_store(
    isolated_db,
    tmp_path,
    monkeypatch,
):
    import database

    uploads_dir = tmp_path / "uploads"
    chroma_base = tmp_path / "chroma_store"
    uploads_dir.mkdir()
    chroma_base.mkdir()
    uploaded_file = uploads_dir / "doc-a.pdf"
    uploaded_file.write_text("content", encoding="utf-8")

    vector_dir = chroma_base / "thread-a"
    vector_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(database, "UPLOADS_DIR", str(uploads_dir))
    monkeypatch.setattr(database, "CHROMA_BASE", str(chroma_base))

    database.create_thread("thread-a", "owner@example.com")
    database.create_workspace("owner@example.com", "Thread docs", "thread-a")
    database.update_thread_workspace("thread-a", "thread-a")
    isolated_db.execute(
        """
        INSERT INTO documents (doc_id, thread_id, workspace_id, filename, file_type)
        VALUES (%s, %s, %s, %s, %s)
        """,
        ("doc-a", "thread-a", "thread-a", "file.pdf", ".pdf"),
    )

    database.delete_thread("thread-a")

    assert not os.path.exists(uploaded_file)
    assert not vector_dir.exists()
    assert isolated_db.execute(
        "SELECT * FROM documents WHERE thread_id=%s",
        ("thread-a",),
        fetch="all",
    ) == []
