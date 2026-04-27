"""
rag_routes.py - RAG upload/chat endpoints using local SQLite metadata.
"""

import json
import os
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from auth_routes import get_current_user
from database import verify_thread_owner
from db import execute
from rag_engine import (
    UPLOADS_DIR,
    add_document_to_store,
    delete_doc_from_store,
    extract_text,
    stream_rag_response,
)

router = APIRouter(prefix="/rag", tags=["rag"])


def save_doc_record(doc_id, thread_id, filename, file_type, chunk_count):
    execute(
        """
        INSERT INTO documents (doc_id, thread_id, filename, file_type, chunk_count)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (doc_id, thread_id, filename, file_type, chunk_count),
    )


def get_thread_docs(thread_id: str):
    return execute(
        "SELECT * FROM documents WHERE thread_id=%s ORDER BY uploaded_at ASC",
        (thread_id,),
        fetch="all",
    )


def get_doc_by_id(doc_id: str):
    return execute("SELECT * FROM documents WHERE doc_id=%s", (doc_id,), fetch="one")


def delete_doc_record(doc_id: str):
    execute("DELETE FROM documents WHERE doc_id=%s", (doc_id,))


ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".webp", ".txt", ".md", ".csv"}
MAX_FILE_SIZE_MB = 20


@router.post("/upload")
async def upload_document(
    thread_id: str = Form(...),
    file: UploadFile = File(...),
    current_user=Depends(get_current_user),
):
    verify_thread_owner(thread_id, current_user["email"])

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"File type '{ext}' not supported. Allowed: {', '.join(ALLOWED_EXTENSIONS)}")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(400, f"File too large. Max size: {MAX_FILE_SIZE_MB}MB")

    doc_id = str(uuid.uuid4())
    save_path = os.path.join(UPLOADS_DIR, f"{doc_id}{ext}")
    with open(save_path, "wb") as f:
        f.write(content)

    try:
        text = extract_text(save_path, file.filename)
        if not text.strip():
            raise HTTPException(400, "Could not extract text from this file.")

        chunk_count = add_document_to_store(thread_id, text, file.filename, doc_id)
        save_doc_record(doc_id, thread_id, file.filename, ext, chunk_count)

        return {
            "doc_id": doc_id,
            "filename": file.filename,
            "chunk_count": chunk_count,
            "message": f"'{file.filename}' uploaded and indexed ({chunk_count} chunks)",
        }

    except HTTPException:
        if os.path.exists(save_path):
            os.remove(save_path)
        raise
    except Exception as e:
        if os.path.exists(save_path):
            os.remove(save_path)
        raise HTTPException(500, f"Failed to process file: {str(e)}")


@router.get("/documents/{thread_id}")
def list_documents(thread_id: str, current_user=Depends(get_current_user)):
    verify_thread_owner(thread_id, current_user["email"])
    return get_thread_docs(thread_id)


@router.delete("/documents/{doc_id}")
def delete_document(doc_id: str, current_user=Depends(get_current_user)):
    row = get_doc_by_id(doc_id)
    if not row:
        raise HTTPException(404, "Document not found")
    verify_thread_owner(row["thread_id"], current_user["email"])

    delete_doc_from_store(row["thread_id"], doc_id)

    for ext in ALLOWED_EXTENSIONS:
        path = os.path.join(UPLOADS_DIR, f"{doc_id}{ext}")
        if os.path.exists(path):
            os.remove(path)
            break

    delete_doc_record(doc_id)
    return {"message": f"'{row['filename']}' deleted successfully"}


class RagChatRequest(BaseModel):
    thread_id: str
    message: str
    chat_history: list = []


@router.post("/chat")
def rag_chat(req: RagChatRequest, current_user=Depends(get_current_user)):
    verify_thread_owner(req.thread_id, current_user["email"])
    docs = get_thread_docs(req.thread_id)
    if not docs:
        raise HTTPException(400, "No documents uploaded in this thread. Please upload a file first.")

    def generate():
        for chunk in stream_rag_response(
            thread_id=req.thread_id,
            user_message=req.message,
            chat_history=req.chat_history,
        ):
            yield json.dumps({"t": chunk}, ensure_ascii=False) + "\n"
        yield json.dumps({"done": True}) + "\n"

    return StreamingResponse(generate(), media_type="application/x-ndjson")
