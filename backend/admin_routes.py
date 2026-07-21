import glob
import os

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr

from auth import approve_user, decode_token, get_all_users, get_user, revoke_user
from database import (
    delete_document_record,
    delete_thread,
    get_admin_analytics,
    get_document,
    get_thread,
    list_admin_documents,
    list_admin_threads,
)
from rag_engine import UPLOADS_DIR, delete_doc_from_store

router = APIRouter(prefix="/admin", tags=["admin"])
bearer = HTTPBearer()


def get_admin_user(creds: HTTPAuthorizationCredentials = Depends(bearer)):
    email = decode_token(creds.credentials)
    if not email:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = get_user(email)
    if not user or not user["is_admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


class ApproveRequest(BaseModel):
    email: EmailStr


@router.get("/users")
def list_users(admin=Depends(get_admin_user)):
    return get_all_users()


@router.post("/users/approve")
def approve(req: ApproveRequest, admin=Depends(get_admin_user)):
    user = get_user(req.email)
    if not user:
        raise HTTPException(404, "User not found")
    approve_user(req.email)
    return {"message": f"{req.email} approved for unlimited chat"}


@router.post("/users/revoke")
def revoke(req: ApproveRequest, admin=Depends(get_admin_user)):
    user = get_user(req.email)
    if not user:
        raise HTTPException(404, "User not found")
    revoke_user(req.email)
    return {"message": f"{req.email} revoked; will be limited to 5 chats"}


@router.get("/analytics")
def analytics(days: int = 30, admin=Depends(get_admin_user)):
    return get_admin_analytics(days)


@router.get("/threads")
def admin_threads(limit: int = 50, admin=Depends(get_admin_user)):
    return list_admin_threads(limit)


@router.delete("/threads/{thread_id}")
def admin_delete_thread(thread_id: str, admin=Depends(get_admin_user)):
    thread = get_thread(thread_id)
    if not thread:
        raise HTTPException(404, "Thread not found")
    delete_thread(thread_id)
    return {"message": "Thread deleted"}


@router.get("/documents")
def admin_documents(limit: int = 50, admin=Depends(get_admin_user)):
    return list_admin_documents(limit)


@router.delete("/documents/{doc_id}")
def admin_delete_document(doc_id: str, admin=Depends(get_admin_user)):
    doc = get_document(doc_id)
    if not doc:
        raise HTTPException(404, "Document not found")

    if doc.get("workspace_id"):
        delete_doc_from_store(doc["workspace_id"], doc_id)
    for path in glob.glob(os.path.join(UPLOADS_DIR, f"{doc_id}.*")):
        if os.path.isfile(path):
            os.remove(path)
    delete_document_record(doc_id)
    return {"message": f"'{doc['filename']}' deleted successfully"}
