"""
Telegram Bot API helpers for the connector.

Configure an official Telegram bot token from BotFather through TELEGRAM_BOT_TOKEN.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import requests
from jose import JWTError, jwt

from config import FRONTEND_URL, JWT_SECRET, load_env

load_env()

logger = logging.getLogger(__name__)

_HERE = Path(__file__).resolve().parent
TOKENS_DIR = _HERE / "tokens"
TOKENS_DIR.mkdir(parents=True, exist_ok=True)
OAUTH_STATES_DIR = _HERE / "oauth_states"
OAUTH_STATES_DIR.mkdir(parents=True, exist_ok=True)

SCOPES = ["bot"]

# Telegram uses a simple bot token, not OAuth redirect URI
REDIRECT_URI = os.getenv(
    "TELEGRAM_REDIRECT_URI",
    "http://localhost:8000/connectors/telegram/callback",
)

STATE_ALGORITHM = "HS256"


def _token_path(user_email: str) -> Path:
    # For Telegram, we associate the bot token with the user email for storage
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", user_email.lower())
    return TOKENS_DIR / f"{safe}.json"


def _oauth_state_path(state: str) -> Path:
    digest = hashlib.sha256(state.encode("utf-8")).hexdigest()
    return OAUTH_STATES_DIR / f"{digest}.json"


def _read_token_data(user_email: str) -> dict[str, Any] | None:
    path = _token_path(user_email)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Could not read Telegram token for %s: %s", user_email, exc)
        return None


def bot_token_configured() -> bool:
    return bool(os.getenv("TELEGRAM_BOT_TOKEN", "").strip())


def ensure_bot_token_config() -> None:
    if not bot_token_configured():
        raise RuntimeError(
            "Telegram bot authentication is missing TELEGRAM_BOT_TOKEN. "
            "Create a Telegram bot via BotFather and add the bot token to .env."
        )


def _serialize_expiry(expiry: datetime | None) -> str | None:
    if not expiry:
        return None
    if expiry.tzinfo is not None:
        expiry = expiry.astimezone(timezone.utc).replace(tzinfo=None)
    return expiry.isoformat() + "Z"


def _parse_expiry(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        clean_value = value[:-1] if value.endswith("Z") else value
        parsed = datetime.fromisoformat(clean_value)
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def create_oauth_state(user_email: str) -> str:
    token = jwt.encode(
        {"sub": user_email, "app": "telegram"},
        JWT_SECRET,
        algorithm=STATE_ALGORITHM,
    )
    if isinstance(token, bytes):
        return token.decode("utf-8")
    return token


def parse_oauth_state(state: str) -> str:
    try:
        payload = jwt.decode(state, JWT_SECRET, algorithms=[STATE_ALGORITHM])
    except JWTError as exc:
        raise ValueError("Invalid or expired Telegram OAuth state.") from exc

    if payload.get("app") != "telegram" or not payload.get("sub"):
        raise ValueError("Invalid Telegram OAuth state.")
    return str(payload["sub"])


def save_token(user_email: str, creds: Any) -> None:
    # For Telegram, creds is expected to be the bot token string
    old_data = _read_token_data(user_email) or {}
    data = {
        "bot_token": creds if isinstance(creds, str) else getattr(creds, "token", None),
        "username": getattr(creds, "username", old_data.get("username")),
    }
    _token_path(user_email).write_text(
        json.dumps(data, indent=2),
        encoding="utf-8",
    )
    logger.info("Telegram token saved for %s", user_email)


def load_token(user_email: str) -> Any | None:
    # For Telegram, we load the bot token from the storage file
    data = _read_token_data(user_email)
    if not data:
        return None

    class TelegramCreds:
        def __init__(self, data):
            self.token = data.get("bot_token")
            self.username = data.get("username", "bot_username")
            self.valid = bool(self.token)

        def expired(self):
            return not self.valid

        def refresh(self, request):
            pass

    return TelegramCreds(data)


def delete_token(user_email: str) -> None:
    path = _token_path(user_email)
    if path.exists():
        path.unlink()
        logger.info("Telegram token deleted for %s", user_email)


def is_connected(user_email: str) -> bool:
    try:
        creds = load_token(user_email)
        return bool(creds and getattr(creds, "valid", False))
    except RuntimeError:
        return False


def _read_configured_bot_token() -> str:
    ensure_bot_token_config()
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is empty.")
    return token


def get_auth_url(user_email: str) -> str:
    token = _read_configured_bot_token()
    save_token(user_email, token)
    params = {"connector": "telegram", "status": "connected"}
    separator = "&" if "?" in FRONTEND_URL else "?"
    return f"{FRONTEND_URL}{separator}{urlencode(params)}"


def exchange_code(user_email: str, code: str, state: str) -> Any:
    # Telegram doesn't use OAuth code exchange; the user provides the bot token.
    class TelegramCreds:
        def __init__(self):
            self.token = code  # Treat the code as the bot token
            self.username = "bot_username"
            self.valid = bool(code)

        def expired(self):
            return False

        def refresh(self, request):
            pass

    creds = TelegramCreds()
    save_token(user_email, creds)
    return creds


def get_connection_status(user_email: str) -> dict[str, Any]:
    configured = False
    setup_error = None
    missing_dependency = None
    connected = False

    try:
        ensure_bot_token_config()
        configured = True
    except RuntimeError as exc:
        setup_error = str(exc)
        configured = bot_token_configured()

    try:
        connected = is_connected(user_email)
    except Exception as exc:
        missing_dependency = str(exc)

    status = "connected" if connected else "not_connected"
    if not connected and setup_error:
        status = "needs_credentials"
    elif not connected and missing_dependency:
        status = "needs_dependencies"

    return {
        "app": "telegram",
        "name": "Telegram",
        "connected": connected,
        "configured": configured,
        "status": status,
        "scopes": SCOPES,
        "redirect_uri": REDIRECT_URI,  # Not really used but kept for structure
        "capabilities": [
            "get_me",
            "send_message",
            "get_updates",
            "get_chat",
        ],
        "message": setup_error or missing_dependency or (
            "Connected" if connected else "Connect Telegram using the configured BotFather bot token."
        ),
    }


def _telegram_service(user_email: str) -> Any:
    creds = load_token(user_email)
    if not creds or not getattr(creds, "valid", False):
        raise RuntimeError("Telegram is not connected for this user.")
    class TelegramService:
        def __init__(self, token):
            self.token = token
            self.base_url = f"https://api.telegram.org/bot{token}"

        def _request(self, method: str, endpoint: str, **kwargs):
            response = requests.request(method, f"{self.base_url}/{endpoint}", timeout=30, **kwargs)
            if response.status_code >= 400:
                raise RuntimeError(f"Telegram API error {response.status_code}: {response.text[:300]}")
            data = response.json()
            if not data.get("ok"):
                raise RuntimeError(f"Telegram API error: {data.get('description', 'unknown error')}")
            return data.get("result")

        def get_me(self):
            return self._request("GET", "getMe")

        def send_message(self, chat_id, text):
            return self._request("POST", "sendMessage", json={"chat_id": chat_id, "text": text})

        def get_updates(self, offset=None, limit=100):
            params = {"limit": max(1, min(int(limit or 100), 100))}
            if offset is not None:
                params["offset"] = offset
            return self._request("GET", "getUpdates", params=params)

        def get_chat(self, chat_id):
            return self._request("GET", "getChat", params={"chat_id": chat_id})

    return TelegramService(creds.token)


def _headers_from_payload(payload: dict[str, Any]) -> dict[str, str]:
    headers = {}
    for header in payload.get("headers", []):
        name = str(header.get("name", "")).lower()
        if name:
            headers[name] = str(header.get("value", ""))
    return headers


def _decode_body(data: str | None) -> str:
    if not data:
        return ""
    padded = data + ("=" * (-len(data) % 4))
    raw = base64.urlsafe_b64decode(padded.encode("utf-8"))
    return raw.decode("utf-8", errors="replace")


def _strip_html(value: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", value)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _extract_message_body(payload: dict[str, Any]) -> str:
    return ""


def get_me(user_email: str) -> dict[str, Any]:
    """Get the bot's information."""
    service = _telegram_service(user_email)
    return service.get_me()


def send_message(user_email: str, chat_id: str, text: str) -> dict[str, Any]:
    """Send a message to a chat."""
    service = _telegram_service(user_email)
    return service.send_message(chat_id, text)


def get_updates(user_email: str, offset: int = None, limit: int = 100) -> list:
    """Get updates from Telegram."""
    service = _telegram_service(user_email)
    return service.get_updates(offset, limit)


def get_chat(user_email: str, chat_id: str) -> dict[str, Any]:
    """Get information about a chat."""
    service = _telegram_service(user_email)
    return service.get_chat(chat_id)


def get_telegram_tools() -> list:
    """Return a list of LangChain tools for Telegram."""
    from .tools import get_telegram_tools as _get_telegram_tools
    return _get_telegram_tools()
