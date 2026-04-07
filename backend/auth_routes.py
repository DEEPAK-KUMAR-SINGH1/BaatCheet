from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from auth import (
    generate_otp, store_otp, verify_otp,
    get_user, create_user, verify_user_email,
    update_password, check_password,
    create_token, decode_token
)
from email_service import send_otp_email

router = APIRouter(prefix="/auth", tags=["auth"])
bearer = HTTPBearer()


# ─────────────────────────────────────────
# SCHEMAS
# ─────────────────────────────────────────

class EmailOnly(BaseModel):
    email: EmailStr

class SignupRequest(BaseModel):
    email: EmailStr
    password: str

class OTPVerify(BaseModel):
    email: EmailStr
    otp: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class ResetPasswordRequest(BaseModel):
    email: EmailStr
    otp: str
    new_password: str


# ─────────────────────────────────────────
# DEPENDENCY — token check
# ─────────────────────────────────────────

def get_current_user(creds: HTTPAuthorizationCredentials = Depends(bearer)):
    email = decode_token(creds.credentials)
    if not email:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user = get_user(email)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    if not user["is_verified"]:
        raise HTTPException(status_code=403, detail="Email not verified")
    return user


# ─────────────────────────────────────────
# SIGNUP FLOW
# Step 1: Register → OTP mail bhejo
# Step 2: Verify OTP → account activate
# ─────────────────────────────────────────

@router.post("/signup")
def signup(req: SignupRequest):
    if len(req.password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")

    existing = get_user(req.email)
    if existing and existing["is_verified"]:
        raise HTTPException(400, "Email already registered. Please login.")
    if existing and not existing["is_verified"]:
        # Resend OTP
        otp = generate_otp()
        store_otp(req.email, otp, "verify")
        send_otp_email(req.email, otp, "verify")
        return {"message": "OTP resent. Please verify your email."}

    created = create_user(req.email, req.password)
    if not created:
        raise HTTPException(400, "Could not create account. Try again.")

    otp = generate_otp()
    store_otp(req.email, otp, "verify")
    send_otp_email(req.email, otp, "verify")
    return {"message": "OTP sent to your email. Please verify to activate your account."}


@router.post("/signup/verify")
def signup_verify(req: OTPVerify):
    if not verify_otp(req.email, req.otp, "verify"):
        raise HTTPException(400, "Invalid or expired OTP")
    verify_user_email(req.email)
    token = create_token(req.email)
    return {"message": "Account verified!", "token": token, "email": req.email}


# ─────────────────────────────────────────
# LOGIN FLOW
# Step 1: Email + Password check → OTP bhejo
# Step 2: Verify OTP → token milega
# ─────────────────────────────────────────

@router.post("/login")
def login(req: LoginRequest):
    user = get_user(req.email)
    if not user:
        raise HTTPException(400, "No account found with this email. Please sign up.")
    if not user["is_verified"]:
        raise HTTPException(400, "Email not verified. Please check your inbox.")
    if not check_password(req.password, user["password_hash"]):
        raise HTTPException(400, "Incorrect password.")

    otp = generate_otp()
    store_otp(req.email, otp, "login")
    send_otp_email(req.email, otp, "login")
    return {"message": "OTP sent to your email."}


# auth_routes.py — login_verify
@router.post("/login/verify")
def login_verify(req: OTPVerify):
    if not verify_otp(req.email, req.otp, "login"):
        raise HTTPException(400, "Invalid or expired OTP")
    user = get_user(req.email)
    if not user:
        raise HTTPException(400, "User not found")
    token = create_token(req.email)
    return {
        "message":     "Login successful!",
        "token":       token,
        "email":       user["email"],
        "is_admin":    bool(user["is_admin"]),      # ← ADD
        "is_approved": bool(user["is_approved"]),   # ← ADD
    }

# signup/verify mein bhi same karo:
@router.post("/signup/verify")
def signup_verify(req: OTPVerify):
    if not verify_otp(req.email, req.otp, "verify"):
        raise HTTPException(400, "Invalid or expired OTP")
    verify_user_email(req.email)
    user = get_user(req.email)
    token = create_token(req.email)
    return {
        "message":     "Account verified!",
        "token":       token,
        "email":       req.email,
        "is_admin":    bool(user["is_admin"]),
        "is_approved": bool(user["is_approved"]),
    }

# ─────────────────────────────────────────
# FORGOT PASSWORD FLOW
# Step 1: Email → OTP bhejo
# Step 2: OTP + new password → reset
# ─────────────────────────────────────────

@router.post("/forgot-password")
def forgot_password(req: EmailOnly):
    user = get_user(req.email)
    if not user:
        raise HTTPException(400, "No account found with this email.")

    otp = generate_otp()
    store_otp(req.email, otp, "reset")
    send_otp_email(req.email, otp, "reset")
    return {"message": "Password reset OTP sent to your email."}


@router.post("/forgot-password/verify")
def forgot_password_verify(req: ResetPasswordRequest):
    if len(req.new_password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")
    if not verify_otp(req.email, req.otp, "reset"):
        raise HTTPException(400, "Invalid or expired OTP")
    update_password(req.email, req.new_password)
    return {"message": "Password reset successful! Please login."}


# ─────────────────────────────────────────
# ME — token se current user info
# ─────────────────────────────────────────

@router.get("/me")
def me(current_user=Depends(get_current_user)):
    return {"email": current_user["email"]}

@router.get("/me/stats")
def me_stats(current_user=Depends(get_current_user)):
    return {
        "email":       current_user["email"],
        "is_admin":    bool(current_user["is_admin"]),
        "is_approved": bool(current_user["is_approved"]),
        "chat_count":  current_user["chat_count"],
    }