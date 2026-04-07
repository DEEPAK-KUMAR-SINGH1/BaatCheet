import sqlite3
import os
import random
import string
from datetime import datetime, timedelta
from passlib.context import CryptContext
from jose import JWTError, jwt
from config import JWT_SECRET

DB_PATH    = os.path.join(os.path.dirname(__file__), 'chatbot.db')
SECRET_KEY = JWT_SECRET
ALGORITHM  = "HS256"
TOKEN_EXPIRE_DAYS = 7
OTP_EXPIRE_MINUTES = 10

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

ADMIN_EMAIL = "kashyap040098@gmail.com"

def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_auth_tables():
    conn = get_conn()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            email         TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            is_verified   INTEGER DEFAULT 0,
            is_approved   INTEGER DEFAULT 0,
            is_admin      INTEGER DEFAULT 0,
            chat_count    INTEGER DEFAULT 0,
            created_at    TEXT DEFAULT (datetime('now'))
        )
    ''')
    # Purani DB ke liye — naye columns add karo safely
    for col, defn in [("is_approved","INTEGER DEFAULT 0"),("is_admin","INTEGER DEFAULT 0"),("chat_count","INTEGER DEFAULT 0")]:
        try:
            c.execute(f"ALTER TABLE users ADD COLUMN {col} {defn}")
        except Exception:
            pass
    c.execute('''
        CREATE TABLE IF NOT EXISTS otps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL, otp TEXT NOT NULL,
            purpose TEXT NOT NULL, expires_at TEXT NOT NULL, used INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

def generate_otp() -> str:
    return ''.join(random.choices(string.digits, k=6))

def store_otp(email, otp, purpose):
    conn = get_conn()
    expires = (datetime.utcnow() + timedelta(minutes=OTP_EXPIRE_MINUTES)).isoformat()
    conn.execute("UPDATE otps SET used=1 WHERE email=? AND purpose=? AND used=0", (email, purpose))
    conn.execute("INSERT INTO otps (email, otp, purpose, expires_at) VALUES (?,?,?,?)", (email, otp, purpose, expires))
    conn.commit()
    conn.close()

def verify_otp(email, otp, purpose):
    conn = get_conn()
    row = conn.execute("SELECT * FROM otps WHERE email=? AND otp=? AND purpose=? AND used=0 ORDER BY id DESC LIMIT 1", (email, otp, purpose)).fetchone()
    if not row: conn.close(); return False
    if datetime.utcnow() > datetime.fromisoformat(row["expires_at"]): conn.close(); return False
    conn.execute("UPDATE otps SET used=1 WHERE id=?", (row["id"],))
    conn.commit(); conn.close(); return True

def get_user(email):
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    conn.close()
    return dict(row) if row else None

def create_user(email, password):
    conn = get_conn()
    hashed = pwd_ctx.hash(password)
    try:
        conn.execute("INSERT INTO users (email, password_hash) VALUES (?,?)", (email, hashed))
        conn.commit(); return True
    except sqlite3.IntegrityError: return False
    finally: conn.close()

def verify_user_email(email):
    conn = get_conn()
    conn.execute("UPDATE users SET is_verified=1 WHERE email=?", (email,))
    conn.commit(); conn.close()

def update_password(email, new_password):
    conn = get_conn()
    hashed = pwd_ctx.hash(new_password)
    conn.execute("UPDATE users SET password_hash=? WHERE email=?", (hashed, email))
    conn.commit(); conn.close()

def check_password(plain, hashed):
    return pwd_ctx.verify(plain, hashed)

def approve_user(email):
    conn = get_conn()
    conn.execute("UPDATE users SET is_approved=1 WHERE email=?", (email,))
    conn.commit(); conn.close()

def revoke_user(email):
    conn = get_conn()
    conn.execute("UPDATE users SET is_approved=0 WHERE email=?", (email,))
    conn.commit(); conn.close()

def get_all_users():
    conn = get_conn()
    rows = conn.execute("SELECT id, email, is_verified, is_approved, is_admin, chat_count, created_at FROM users ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def increment_chat_count(email):
    conn = get_conn()
    conn.execute("UPDATE users SET chat_count = chat_count + 1 WHERE email=?", (email,))
    conn.commit(); conn.close()

def get_chat_count(email):
    conn = get_conn()
    row = conn.execute("SELECT chat_count FROM users WHERE email=?", (email,)).fetchone()
    conn.close()
    return row["chat_count"] if row else 0

def ensure_admin_exists():
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE email=?", (ADMIN_EMAIL,)).fetchone()
    if not row:
        hashed = pwd_ctx.hash("Admin@1234")
        conn.execute("INSERT INTO users (email, password_hash, is_verified, is_approved, is_admin) VALUES (?,?,1,1,1)", (ADMIN_EMAIL, hashed))
    else:
        conn.execute("UPDATE users SET is_admin=1, is_approved=1, is_verified=1 WHERE email=?", (ADMIN_EMAIL,))
    conn.commit(); conn.close()

def create_token(email):
    expire = datetime.utcnow() + timedelta(days=TOKEN_EXPIRE_DAYS)
    return jwt.encode({"sub": email, "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None

init_auth_tables()
ensure_admin_exists()