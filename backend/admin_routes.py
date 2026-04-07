from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from auth import decode_token, get_user, approve_user, revoke_user, get_all_users

router = APIRouter(prefix="/admin", tags=["admin"])
bearer = HTTPBearer()


def get_admin_user(creds: HTTPAuthorizationCredentials = Depends(bearer)):
    """Sirf admin hi ye routes use kar sakta hai"""
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
    """Sabhi users ki list with approval status"""
    return get_all_users()


@router.post("/users/approve")
def approve(req: ApproveRequest, admin=Depends(get_admin_user)):
    """Kisi user ko approve karo → unlimited chat"""
    user = get_user(req.email)
    if not user:
        raise HTTPException(404, "User not found")
    approve_user(req.email)
    return {"message": f"{req.email} approved for unlimited chat"}


@router.post("/users/revoke")
def revoke(req: ApproveRequest, admin=Depends(get_admin_user)):
    """Kisi user ki approval hatao"""
    user = get_user(req.email)
    if not user:
        raise HTTPException(404, "User not found")
    revoke_user(req.email)
    return {"message": f"{req.email} revoked — will be limited to 5 chats"}