"""
config.py — Single source of truth for all environment variables.
"""

import os
from dotenv import load_dotenv

_BASE_DIR = os.path.dirname(__file__)
_ROOT_DIR = os.path.abspath(os.path.join(_BASE_DIR, ".."))
_ENV_PATH = os.path.join(_ROOT_DIR, ".env")

def load_env():
    load_dotenv(dotenv_path=_ENV_PATH, override=True)

load_env()

# ─── API KEYS ───────────────────────────
MISTRAL_API_KEY: str = os.getenv("MISTRAL_API_KEY", "")
GEMINI_API_KEY:  str = os.getenv("GEMINI_API_KEY", "")

# Admin bootstrap. Leave ADMIN_BOOTSTRAP_PASSWORD empty after first setup.
ADMIN_EMAIL: str = os.getenv("ADMIN_EMAIL", "")
ADMIN_BOOTSTRAP_PASSWORD: str = os.getenv("ADMIN_BOOTSTRAP_PASSWORD", "")

# ─── EMAIL ──────────────────────────────
SENDER_EMAIL: str = os.getenv("EMAIL_ADDRESS", "")
APP_PASSWORD:  str = os.getenv("EMAIL_APP_PASSWORD", "")

# ─── JWT ────────────────────────────────
JWT_SECRET: str = os.getenv("JWT_SECRET", "fallback-secret-change-this")

# CORS
_CORS_ORIGINS = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173",
)
CORS_ORIGINS: list[str] = [
    origin.strip() for origin in _CORS_ORIGINS.split(",") if origin.strip()
]

# Frontend URL used for OAuth callbacks after a provider redirects to the API.
FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:5173")

# ─── LANGSMITH ──────────────────────────
LANGCHAIN_API_KEY:    str = os.getenv("LANGCHAIN_API_KEY", "")
LANGCHAIN_PROJECT:    str = os.getenv("LANGCHAIN_PROJECT", "chatbot")
LANGCHAIN_TRACING_V2: str = os.getenv("LANGCHAIN_TRACING_V2", "false")

# ─── SUPABASE / POSTGRES ──────────────────
# Full Postgres connection string for your Supabase project.
# Dashboard → Project Settings → Database → Connection string (URI).
# Example: postgresql://postgres.qdjqbkmthmyxztgcleji:[PASSWORD]@aws-0-ap-south-1.pooler.supabase.com:5432/postgres
DATABASE_URL: str = os.getenv("DATABASE_URL", "")
if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is not set. Add your Supabase connection string to .env "
        "(Project Settings \u2192 Database \u2192 Connection string)."
    )
