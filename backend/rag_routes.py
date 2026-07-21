"""
rag_routes.py - Backward-compatible RAG upload/chat endpoints.
"""

import json
import os

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from auth import get_chat_count, increment_chat_count
from auth_routes import get_current_user
from database import (
    create_workspace,
    get_document,
    get_thread_workspace_id,
    get_workspace_documents,
    save_message,
    update_thread_timestamp,
    update_thread_title,
    update_thread_workspace,
    verify_thread_owner,
    verify_workspace_owner,
)
from document_service import ALLOWED_EXTENSIONS, upload_and_index_document
from rag_engine import delete_doc_from_store, retrieve_context_with_sources, stream_rag_response

router = APIRouter(prefix="/rag", tags=["rag"])


def ensure_thread_workspace(thread_id: str, user_id: str):
    verify_thread_owner(thread_id, user_id)
    workspace_id = get_thread_workspace_id(thread_id)
    if workspace_id:
        verify_workspace_owner(workspace_id, user_id)
        return workspace_id
    workspace = create_workspace(user_id, name="Thread documents", workspace_id=thread_id)
    update_thread_workspace(thread_id, workspace["workspace_id"])
    return workspace["workspace_id"]


def get_thread_docs(thread_id: str):
    from db import execute

    workspace_id = get_thread_workspace_id(thread_id)
    if workspace_id:
        return get_workspace_documents(workspace_id)
    return execute(
        "SELECT * FROM documents WHERE thread_id=%s ORDER BY uploaded_at ASC",
        (thread_id,),
        fetch="all",
    )


def get_doc_by_id(doc_id: str):
    return get_document(doc_id)


@router.post("/upload")
async def upload_document(
    thread_id: str = Form(...),
    file: UploadFile = File(...),
    current_user=Depends(get_current_user),
):
    workspace_id = ensure_thread_workspace(thread_id, current_user["email"])
    doc = await upload_and_index_document(
        thread_id=thread_id,
        workspace_id=workspace_id,
        file=file,
        user_id=current_user["email"],
        raise_on_failure=False,
    )
    if doc.get("status") == "failed":
        message = f"'{doc['filename']}' uploaded, but indexing failed. You can retry after fixing the issue."
    else:
        message = f"'{doc['filename']}' uploaded and indexed ({doc['chunk_count']} chunks)"
    return {
        **doc,
        "message": message,
    }


@router.get("/documents/{thread_id}")
def list_documents(thread_id: str, current_user=Depends(get_current_user)):
    verify_thread_owner(thread_id, current_user["email"])
    return get_thread_docs(thread_id)


@router.delete("/documents/{doc_id}")
def delete_document(doc_id: str, current_user=Depends(get_current_user)):
    from database import delete_document_record

    row = get_doc_by_id(doc_id)
    if not row:
        raise HTTPException(404, "Document not found")
    verify_workspace_owner(row["workspace_id"], current_user["email"])

    delete_doc_from_store(row["workspace_id"], doc_id)

    for ext in ALLOWED_EXTENSIONS:
        path = os.path.join(os.path.dirname(__file__), "uploads", f"{doc_id}{ext}")
        if os.path.exists(path):
            os.remove(path)
            break

    delete_document_record(doc_id)
    return {"message": f"'{row['filename']}' deleted successfully"}


class RagChatRequest(BaseModel):
    thread_id: str
    message: str
    chat_history: list = []
    workspace_id: str | None = None


@router.post("/chat")
def rag_chat(req: RagChatRequest, current_user=Depends(get_current_user)):
    email = current_user["email"]
    verify_thread_owner(req.thread_id, email)
    workspace_id = req.workspace_id or ensure_thread_workspace(req.thread_id, email)
    verify_workspace_owner(workspace_id, email)

    docs = get_workspace_documents(workspace_id)
    indexed_docs = [doc for doc in docs if doc.get("status") == "indexed"]
    if not indexed_docs:
        raise HTTPException(400, "No indexed documents in this workspace. Please upload or retry a document first.")

    if not current_user["is_approved"] and not current_user["is_admin"] and get_chat_count(email) >= 5:
        raise HTTPException(403, "Chat limit reached (5/5). Contact admin for unlimited access.")

    save_message(req.thread_id, "user", req.message)
    increment_chat_count(email)
    context, sources = retrieve_context_with_sources(workspace_id, req.message, k=5)

    def generate():
        full_response = []
        status = "complete"
        try:
            for chunk in stream_rag_response(
                thread_id=req.thread_id,
                user_message=req.message,
                chat_history=req.chat_history,
                workspace_id=workspace_id,
            ):
                full_response.append(chunk)
                yield json.dumps({"t": chunk}, ensure_ascii=False) + "\n"
            yield json.dumps({"sources": sources}, ensure_ascii=False) + "\n"
        except GeneratorExit:
            status = "stopped"
        except Exception as exc:
            status = "failed"
            yield json.dumps({"error": str(exc)}, ensure_ascii=False) + "\n"
        finally:
            ai_text = "".join(full_response)
            if ai_text.strip():
                save_message(
                    req.thread_id,
                    "assistant",
                    ai_text,
                    metadata={"sources": sources, "workspace_id": workspace_id},
                    status=status,
                )
                update_thread_timestamp(req.thread_id)
                if len(req.chat_history) == 0:
                    title = req.message[:50] + ("..." if len(req.message) > 50 else "")
                    update_thread_title(req.thread_id, title)
            yield json.dumps({"done": True}) + "\n"

    return StreamingResponse(generate(), media_type="application/x-ndjson")
