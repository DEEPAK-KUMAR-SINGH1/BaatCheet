"""
config.py — Single source of truth for all environment variables.
Saari files yahan se keys leti hain — .env ek hi jagah se load hoti hai.
"""

import os
from dotenv import load_dotenv

# .env file project root mein hai (backend ke ek level upar)
_ENV_PATH = os.path.join(os.path.dirname(__file__), "..", ".env")


def load_env():
    """
    .env ko explicit path se load karo with override=True.
    Har file mein call karo — dotenv internally idempotent hai.
    """
    load_dotenv(dotenv_path=_ENV_PATH, override=True)


# Module load hote hi keys load kar lo
load_env()

# ─────────────────────────────────────────
# API KEYS
# ─────────────────────────────────────────

MISTRAL_API_KEY: str = os.getenv("MISTRAL_API_KEY", "")
GEMINI_API_KEY:  str = os.getenv("GEMINI_API_KEY", "")

# ─────────────────────────────────────────
# EMAIL
# ─────────────────────────────────────────

SENDER_EMAIL: str = os.getenv("EMAIL_ADDRESS", "")
APP_PASSWORD:  str = os.getenv("EMAIL_APP_PASSWORD", "")

# ─────────────────────────────────────────
# JWT
# ─────────────────────────────────────────

JWT_SECRET: str = os.getenv("JWT_SECRET", "fallback-secret-change-this")

# ─────────────────────────────────────────
# LANGSMITH
# ─────────────────────────────────────────

LANGCHAIN_API_KEY:    str = os.getenv("LANGCHAIN_API_KEY", "")
LANGCHAIN_PROJECT:    str = os.getenv("LANGCHAIN_PROJECT", "chatbot")
LANGCHAIN_TRACING_V2: str = os.getenv("LANGCHAIN_TRACING_V2", "false")
