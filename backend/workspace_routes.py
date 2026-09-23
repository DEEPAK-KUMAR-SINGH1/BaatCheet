import os

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel

from auth_routes import get_current_user
from database import (
    create_or_refresh_share,
    create_workspace,
    delete_document_record,
    delete_workspace,
    get_document,
    get_document_chunk,
    get_public_share,
    get_share_for_thread,
    get_workspace,
    get_workspace_documents,
    list_workspaces_for_user,
    revoke_share,
    search_user_threads,
    update_thread_workspace,
    update_user_message_and_prune,
    update_workspace,
    verify_thread_owner,
    verify_workspace_owner,
)
from document_service import ALLOWED_EXTENSIONS, index_existing_document, upload_and_index_document
from rag_engine import delete_doc_from_store

router = APIRouter(tags=["workspaces"])


class WorkspaceRequest(BaseModel):
    name: str = "New Workspace"
    description: str | None = None


class AttachWorkspaceRequest(BaseModel):
    workspace_id: str | None = None


class EditMessageRequest(BaseModel):
    content: str


@router.get("/workspaces")
def list_workspaces(current_user=Depends(get_current_user)):
    return list_workspaces_for_user(current_user["email"])


@router.post("/workspaces")
def create_workspace_route(req: WorkspaceRequest, current_user=Depends(get_current_user)):
    return create_workspace(current_user["email"], name=req.name.strip() or "New Workspace")


@router.patch("/workspaces/{workspace_id}")
def update_workspace_route(
    workspace_id: str,
    req: WorkspaceRequest,
    current_user=Depends(get_current_user),
):
    verify_workspace_owner(workspace_id, current_user["email"])
    return update_workspace(workspace_id, req.name.strip() or "New Workspace", req.description)


@router.delete("/workspaces/{workspace_id}")
def delete_workspace_route(workspace_id: str, current_user=Depends(get_current_user)):
    verify_workspace_owner(workspace_id, current_user["email"])
    delete_workspace(workspace_id)
    return {"message": "Workspace deleted"}


@router.patch("/threads/{thread_id}/workspace")
def attach_workspace(
    thread_id: str,
    req: AttachWorkspaceRequest,
    current_user=Depends(get_current_user),
):
    verify_thread_owner(thread_id, current_user["email"])
    if req.workspace_id:
        verify_workspace_owner(req.workspace_id, current_user["email"])
    update_thread_workspace(thread_id, req.workspace_id)
    return {"thread_id": thread_id, "workspace_id": req.workspace_id}


@router.get("/workspaces/{workspace_id}/documents")
def workspace_documents(workspace_id: str, current_user=Depends(get_current_user)):
    verify_workspace_owner(workspace_id, current_user["email"])
    return get_workspace_documents(workspace_id)


@router.post("/workspaces/{workspace_id}/documents")
async def upload_workspace_document(
    workspace_id: str,
    thread_id: str = Form(...),
    file: UploadFile = File(...),
    current_user=Depends(get_current_user),
):
    verify_workspace_owner(workspace_id, current_user["email"])
    verify_thread_owner(thread_id, current_user["email"])
    return await upload_and_index_document(
        thread_id=thread_id,
        workspace_id=workspace_id,
        file=file,
        user_id=current_user["email"],
        raise_on_failure=False,
    )


@router.delete("/workspaces/{workspace_id}/documents/{doc_id}")
def delete_workspace_document(
    workspace_id: str,
    doc_id: str,
    current_user=Depends(get_current_user),
):
    verify_workspace_owner(workspace_id, current_user["email"])
    doc = get_document(doc_id)
    if not doc or doc["workspace_id"] != workspace_id:
        raise HTTPException(404, "Document not found")

    delete_doc_from_store(workspace_id, doc_id)
    for ext in ALLOWED_EXTENSIONS:
        path = os.path.join(os.path.dirname(__file__), "uploads", f"{doc_id}{ext}")
        if os.path.exists(path):
            os.remove(path)
            break
    delete_document_record(doc_id)
    return {"message": f"'{doc['filename']}' deleted successfully"}


@router.post("/workspaces/{workspace_id}/documents/{doc_id}/retry")
def retry_workspace_document(
    workspace_id: str,
    doc_id: str,
    current_user=Depends(get_current_user),
):
    verify_workspace_owner(workspace_id, current_user["email"])
    doc = get_document(doc_id)
    if not doc or doc["workspace_id"] != workspace_id:
        raise HTTPException(404, "Document not found")
    try:
        return index_existing_document(doc_id, workspace_id=workspace_id, user_id=current_user["email"])
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, f"Retry failed: {str(exc)}") from exc


@router.get("/sources/{doc_id}/chunks/{chunk_index}")
def source_preview(
    doc_id: str,
    chunk_index: int,
    current_user=Depends(get_current_user),
):
    chunk = get_document_chunk(doc_id, chunk_index)
    if not chunk:
        raise HTTPException(404, "Source chunk not found")
    verify_workspace_owner(chunk["workspace_id"], current_user["email"])
    return chunk


@router.get("/search")
def search(q: str = Query(..., min_length=1), current_user=Depends(get_current_user)):
    return search_user_threads(current_user["email"], q.strip())


@router.post("/threads/{thread_id}/share")
def share_thread(thread_id: str, current_user=Depends(get_current_user)):
    verify_thread_owner(thread_id, current_user["email"])
    share = create_or_refresh_share(thread_id, current_user["email"])
    return {"token": share["token"], "url": f"/share/{share['token']}"}


@router.get("/threads/{thread_id}/share")
def get_thread_share(thread_id: str, current_user=Depends(get_current_user)):
    verify_thread_owner(thread_id, current_user["email"])
    return get_share_for_thread(thread_id, current_user["email"]) or {}


@router.delete("/threads/{thread_id}/share")
def unshare_thread(thread_id: str, current_user=Depends(get_current_user)):
    verify_thread_owner(thread_id, current_user["email"])
    revoke_share(thread_id, current_user["email"])
    return {"message": "Share link revoked"}


@router.get("/share/{token}")
def public_share(token: str):
    share = get_public_share(token)
    if not share:
        raise HTTPException(404, "Share link not found")
    return {
        "title": share["title"],
        "created_at": share["created_at"],
        "messages": share["messages"],
    }


@router.get("/public/share/{token}")
def public_share_api(token: str):
    return public_share(token)


@router.patch("/threads/{thread_id}/messages/{message_id}")
def edit_latest_user_message(
    thread_id: str,
    message_id: int,
    req: EditMessageRequest,
    current_user=Depends(get_current_user),
):
    verify_thread_owner(thread_id, current_user["email"])
    content = req.content.strip()
    if not content:
        raise HTTPException(400, "Message cannot be empty")
    return update_user_message_and_prune(thread_id, message_id, content)
