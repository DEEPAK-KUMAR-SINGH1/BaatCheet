"""
auth.py - Authentication logic backed by local SQLite.
"""

import random
import secrets
import string
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from config import ADMIN_BOOTSTRAP_PASSWORD, ADMIN_EMAIL, JWT_SECRET
from db import execute

SECRET_KEY = JWT_SECRET
ALGORITHM = "HS256"
TOKEN_EXPIRE_DAYS = 7
OTP_EXPIRE_MINUTES = 10
MAX_PASSWORD_BYTES = 72


def _password_to_bytes(password: str) -> bytes:
    return password.encode("utf-8")


def password_exceeds_limit(password: str) -> bool:
    return len(_password_to_bytes(password)) > MAX_PASSWORD_BYTES


def hash_password(password: str) -> str:
    pw_bytes = _password_to_bytes(password)
    if len(pw_bytes) > MAX_PASSWORD_BYTES:
        raise ValueError("Password must be 72 bytes or fewer")
    return bcrypt.hashpw(pw_bytes, bcrypt.gensalt()).decode("utf-8")


def check_password(plain: str, hashed: str) -> bool:
    plain_bytes = _password_to_bytes(plain)
    if len(plain_bytes) > MAX_PASSWORD_BYTES:
        return False
    try:
        return bcrypt.checkpw(plain_bytes, hashed.encode("utf-8"))
    except ValueError:
        return False


def generate_otp() -> str:
    return "".join(random.choices(string.digits, k=6))


def store_otp(email: str, otp: str, purpose: str):
    execute(
        "UPDATE otps SET used=1 WHERE email=%s AND purpose=%s AND used=0",
        (email, purpose),
    )
    expires = datetime.now(timezone.utc) + timedelta(minutes=OTP_EXPIRE_MINUTES)
    execute(
        "INSERT INTO otps (email, otp, purpose, expires_at) VALUES (%s, %s, %s, %s)",
        (email, otp, purpose, expires),
    )


def _parse_datetime(value):
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


def verify_otp(email: str, otp: str, purpose: str) -> bool:
    row = execute(
        """
        SELECT id, expires_at FROM otps
        WHERE email=%s AND otp=%s AND purpose=%s AND used=0
        ORDER BY id DESC LIMIT 1
        """,
        (email, otp, purpose),
        fetch="one",
    )
    if not row:
        return False

    expires_at = _parse_datetime(row["expires_at"])
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) > expires_at:
        return False

    execute("UPDATE otps SET used=1 WHERE id=%s", (row["id"],))
    return True


def get_user(email: str):
    return execute("SELECT * FROM users WHERE email=%s", (email,), fetch="one")


def create_user(email: str, password: str) -> bool:
    hashed = hash_password(password)
    try:
        execute(
            "INSERT INTO users (email, password_hash) VALUES (%s, %s)",
            (email, hashed),
        )
        return True
    except Exception:
        return False


def verify_user_email(email: str):
    execute("UPDATE users SET is_verified=1 WHERE email=%s", (email,))


def update_password(email: str, new_password: str):
    hashed = hash_password(new_password)
    execute("UPDATE users SET password_hash=%s WHERE email=%s", (hashed, email))


def approve_user(email: str):
    execute("UPDATE users SET is_approved=1 WHERE email=%s", (email,))


def revoke_user(email: str):
    execute("UPDATE users SET is_approved=0 WHERE email=%s", (email,))


def get_all_users():
    return execute(
        "SELECT id, email, is_verified, is_approved, is_admin, chat_count, created_at "
        "FROM users ORDER BY created_at DESC",
        fetch="all",
    )


def increment_chat_count(email: str):
    execute("UPDATE users SET chat_count = chat_count + 1 WHERE email=%s", (email,))


def get_chat_count(email: str) -> int:
    row = execute("SELECT chat_count FROM users WHERE email=%s", (email,), fetch="one")
    return row["chat_count"] if row else 0


def ensure_admin_exists():
    if not ADMIN_EMAIL:
        print("ADMIN_EMAIL is not set; skipping admin bootstrap.")
        return

    row = get_user(ADMIN_EMAIL)
    if not row:
        if not ADMIN_BOOTSTRAP_PASSWORD:
            print("ADMIN_BOOTSTRAP_PASSWORD is not set; skipping admin bootstrap.")
            return
        hashed = hash_password(ADMIN_BOOTSTRAP_PASSWORD)
        execute(
            """
            INSERT INTO users (email, password_hash, is_verified, is_approved, is_admin)
            VALUES (%s, %s, 1, 1, 1)
            """,
            (ADMIN_EMAIL, hashed),
        )
    else:
        execute(
            "UPDATE users SET is_admin=1, is_approved=1, is_verified=1 WHERE email=%s",
            (ADMIN_EMAIL,),
        )
        if ADMIN_BOOTSTRAP_PASSWORD and check_password(ADMIN_BOOTSTRAP_PASSWORD, row["password_hash"]):
            execute(
                "UPDATE users SET password_hash=%s WHERE email=%s",
                (hash_password(secrets.token_urlsafe(48)), ADMIN_EMAIL),
            )
            print("Admin bootstrap password was retired; use forgot password to set a new one.")


def create_token(email: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=TOKEN_EXPIRE_DAYS)
    return jwt.encode({"sub": email, "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None
