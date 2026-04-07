import os
import uuid
import sqlite3
from datetime import datetime

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List
import json

from rag_engine import (
    extract_text, add_document_to_store,
    delete_doc_from_store, delete_thread_store,
    stream_rag_response, UPLOADS_DIR
)

router = APIRouter(prefix="/rag", tags=["rag"])

# ─────────────────────────────────────────
# DB HELPERS — documents table
# ─────────────────────────────────────────

DB_PATH = os.path.join(os.path.dirname(__file__), 'chatbot.db')

def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_rag_tables():
    conn = get_conn()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS documents (
            doc_id      TEXT PRIMARY KEY,
            thread_id   TEXT NOT NULL,
            filename    TEXT NOT NULL,
            file_type   TEXT NOT NULL,
            chunk_count INTEGER DEFAULT 0,
            uploaded_at TEXT DEFAULT (datetime('now'))
        )
    ''')
    conn.commit()
    conn.close()

def save_doc_record(doc_id, thread_id, filename, file_type, chunk_count):
    conn = get_conn()
    conn.execute(
        "INSERT INTO documents (doc_id, thread_id, filename, file_type, chunk_count) VALUES (?,?,?,?,?)",
        (doc_id, thread_id, filename, file_type, chunk_count)
    )
    conn.commit()
    conn.close()

def get_thread_docs(thread_id: str):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM documents WHERE thread_id=? ORDER BY uploaded_at ASC",
        (thread_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def delete_doc_record(doc_id: str):
    conn = get_conn()
    conn.execute("DELETE FROM documents WHERE doc_id=?", (doc_id,))
    conn.commit()
    conn.close()

init_rag_tables()

# ─────────────────────────────────────────
# ALLOWED FILE TYPES
# ─────────────────────────────────────────

ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".webp", ".txt", ".md", ".csv"}
MAX_FILE_SIZE_MB   = 20

# ─────────────────────────────────────────
# UPLOAD ENDPOINT
# ─────────────────────────────────────────

@router.post("/upload")
async def upload_document(
    thread_id: str = Form(...),
    file: UploadFile = File(...)
):
    # Extension check
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"File type '{ext}' not supported. Allowed: {', '.join(ALLOWED_EXTENSIONS)}")

    # Read file
    content = await file.read()

    # Size check
    if len(content) > MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(400, f"File too large. Max size: {MAX_FILE_SIZE_MB}MB")

    # Save to disk
    doc_id    = str(uuid.uuid4())
    save_path = os.path.join(UPLOADS_DIR, f"{doc_id}{ext}")
    with open(save_path, "wb") as f:
        f.write(content)

    try:
        # Extract text
        text = extract_text(save_path, file.filename)
        if not text.strip():
            raise HTTPException(400, "Could not extract text from this file. Please try another file.")

        # Add to Chroma
        chunk_count = add_document_to_store(thread_id, text, file.filename, doc_id)

        # Save record to DB
        save_doc_record(doc_id, thread_id, file.filename, ext, chunk_count)

        return {
            "doc_id":      doc_id,
            "filename":    file.filename,
            "chunk_count": chunk_count,
            "message":     f"✅ '{file.filename}' uploaded and indexed ({chunk_count} chunks)"
        }

    except HTTPException:
        raise
    except Exception as e:
        # Cleanup on failure
        if os.path.exists(save_path):
            os.remove(save_path)
        raise HTTPException(500, f"Failed to process file: {str(e)}")


# ─────────────────────────────────────────
# LIST DOCUMENTS
# ─────────────────────────────────────────

@router.get("/documents/{thread_id}")
def list_documents(thread_id: str):
    return get_thread_docs(thread_id)


# ─────────────────────────────────────────
# DELETE DOCUMENT
# ─────────────────────────────────────────

@router.delete("/documents/{doc_id}")
def delete_document(doc_id: str):
    conn = get_conn()
    row = conn.execute("SELECT * FROM documents WHERE doc_id=?", (doc_id,)).fetchone()
    conn.close()

    if not row:
        raise HTTPException(404, "Document not found")

    row = dict(row)
    # Delete from Chroma
    delete_doc_from_store(row["thread_id"], doc_id)

    # Delete file from disk
    for ext in ALLOWED_EXTENSIONS:
        path = os.path.join(UPLOADS_DIR, f"{doc_id}{ext}")
        if os.path.exists(path):
            os.remove(path)
            break

    # Delete DB record
    delete_doc_record(doc_id)

    return {"message": f"'{row['filename']}' deleted successfully"}


# ─────────────────────────────────────────
# RAG CHAT ENDPOINT — streaming
# ─────────────────────────────────────────

class RagChatRequest(BaseModel):
    thread_id: str
    message: str
    chat_history: list = []


@router.post("/chat")
def rag_chat(req: RagChatRequest):
    # Check if thread has documents
    docs = get_thread_docs(req.thread_id)
    if not docs:
        raise HTTPException(400, "No documents uploaded in this thread. Please upload a file first.")

    def generate():
        full_response = []
        for chunk in stream_rag_response(
            thread_id=req.thread_id,
            user_message=req.message,
            chat_history=req.chat_history,
        ):
            full_response.append(chunk)
            yield json.dumps({"t": chunk}, ensure_ascii=False) + "\n"
        yield json.dumps({"done": True}) + "\n"

    return StreamingResponse(generate(), media_type="application/x-ndjson")
