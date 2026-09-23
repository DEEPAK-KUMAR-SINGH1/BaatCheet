"""
Trello OAuth and API helpers for the connector.

Configure a Trello Power-Up/API key through environment variables. User tokens
are created through Trello's authorization page when a user connects.
"""

from __future__ import annotations

import base64
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

SCOPES = [
    "read",
    "write",
    "account",
]

API_BASE = "https://api.trello.com/1"

REDIRECT_URI = os.getenv(
    "TRELLO_REDIRECT_URI",
    "http://localhost:8000/connectors/trello/callback",
)

STATE_ALGORITHM = "HS256"
AUTHORIZE_URI = "https://trello.com/1/authorize"


def _token_path(user_email: str) -> Path:
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
        logger.warning("Could not read Trello token for %s: %s", user_email, exc)
        return None


def oauth_credentials_configured() -> bool:
    try:
        _load_client_config()
        return True
    except RuntimeError:
        return False


def _load_client_config() -> tuple[str, dict[str, Any]]:
    api_key = os.getenv("TRELLO_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "Trello authorization is missing TRELLO_API_KEY. "
            "Create a Trello Power-Up/API key and add it to .env."
        )
    return "web", {
        "api_key": api_key,
        "app_name": os.getenv("TRELLO_APP_NAME", "AI Chatbot").strip() or "AI Chatbot",
    }


def ensure_oauth_config() -> None:
    _load_client_config()


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
        {"sub": user_email, "app": "trello"},
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
        raise ValueError("Invalid or expired Trello OAuth state.") from exc

    if payload.get("app") != "trello" or not payload.get("sub"):
        raise ValueError("Invalid Trello OAuth state.")
    return str(payload["sub"])


def save_token(user_email: str, creds: Any) -> None:
    old_data = _read_token_data(user_email) or {}
    try:
        _, config = _load_client_config()
    except Exception:
        config = {}
    if isinstance(creds, dict):
        api_key = creds.get("api_key") or old_data.get("api_key") or config.get("api_key")
        token = creds.get("token") or creds.get("access_token") or old_data.get("token")
    elif isinstance(creds, str):
        api_key = old_data.get("api_key") or config.get("api_key")
        token = creds
    else:
        api_key = getattr(creds, "api_key", None) or getattr(creds, "client_id", None) or old_data.get("api_key") or config.get("api_key")
        token = getattr(creds, "token", None) or getattr(creds, "access_token", None) or old_data.get("token")
    if not token:
        raise RuntimeError("Trello authorization did not return a user token.")
    data = {
        "api_key": api_key,
        "token": token,
    }
    _token_path(user_email).write_text(
        json.dumps(data, indent=2),
        encoding="utf-8",
    )
    logger.info("Trello token saved for %s", user_email)


def load_token(user_email: str) -> Any | None:
    data = _read_token_data(user_email)
    if not data:
        return None

    class TrelloCreds:
        def __init__(self, data):
            self.api_key = data.get("api_key")
            self.token = data.get("token")
            self.scopes = data.get("scopes", SCOPES)
            self.valid = bool(self.api_key and self.token)

    return TrelloCreds(data)


def delete_token(user_email: str) -> None:
    path = _token_path(user_email)
    if path.exists():
        path.unlink()
        logger.info("Trello token deleted for %s", user_email)


def is_connected(user_email: str) -> bool:
    try:
        creds = load_token(user_email)
        return bool(creds and getattr(creds, "valid", False))
    except RuntimeError:
        return False


def get_auth_url(user_email: str) -> str:
    ensure_oauth_config()
    _, config = _load_client_config()
    state = create_oauth_state(user_email)
    return_params = {"connector": "trello", "status": "token", "state": state}
    separator = "&" if "?" in FRONTEND_URL else "?"
    return_url = f"{FRONTEND_URL}{separator}{urlencode(return_params)}"
    params = {
        "expiration": "never",
        "name": config["app_name"],
        "scope": ",".join(SCOPES),
        "response_type": "token",
        "key": config["api_key"],
        "return_url": return_url,
    }
    return f"{AUTHORIZE_URI}?{urlencode(params)}"


def exchange_code(user_email: str, code: str, state: str) -> Any:
    ensure_oauth_config()
    if state:
        state_user = parse_oauth_state(state)
        if state_user != user_email:
            raise ValueError("Trello authorization session does not match the current user.")
    _, config = _load_client_config()
    creds = {"api_key": config["api_key"], "token": code}
    save_token(user_email, creds)
    return load_token(user_email)


def get_connection_status(user_email: str) -> dict[str, Any]:
    configured = False
    setup_error = None
    missing_dependency = None
    connected = False

    try:
        ensure_oauth_config()
        configured = True
    except RuntimeError as exc:
        setup_error = str(exc)
        configured = oauth_credentials_configured()

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
        "app": "trello",
        "name": "Trello",
        "connected": connected,
        "configured": configured,
        "status": status,
        "scopes": SCOPES,
        "redirect_uri": REDIRECT_URI,
        "capabilities": [
            "get_boards",
            "get_lists",
            "get_cards",
            "create_card",
            "update_card",
            "delete_card",
        ],
        "message": setup_error or missing_dependency or (
            "Connected" if connected else "Connect Trello to let chat access your boards."
        ),
    }


def _trello_service(user_email: str) -> Any:
    creds = load_token(user_email)
    if not creds or not getattr(creds, "valid", False):
        raise RuntimeError("Trello is not connected for this user.")
    class TrelloService:
        def __init__(self, api_key, token):
            self.api_key = api_key
            self.token = token
            self.auth = {"key": api_key, "token": token}

        def _request(self, method: str, path: str, **kwargs):
            params = kwargs.pop("params", {}) or {}
            params.update(self.auth)
            response = requests.request(
                method,
                f"{API_BASE}{path}",
                params=params,
                timeout=30,
                **kwargs,
            )
            if response.status_code >= 400:
                raise RuntimeError(f"Trello API error {response.status_code}: {response.text[:300]}")
            if response.status_code == 204 or not response.text:
                return {}
            return response.json()

        def get_boards(self):
            return self._request("GET", "/members/me/boards", params={"fields": "id,name,desc,url,closed"})

        def get_lists(self, board_id):
            return self._request("GET", f"/boards/{board_id}/lists", params={"fields": "id,name,closed"})

        def get_cards(self, list_id):
            return self._request("GET", f"/lists/{list_id}/cards", params={"fields": "id,name,desc,url,due,closed"})

        def create_card(self, name, desc, list_id):
            return self._request("POST", "/cards", params={"idList": list_id, "name": name, "desc": desc})

        def update_card(self, card_id, name=None, desc=None):
            params = {}
            if name is not None:
                params["name"] = name
            if desc is not None:
                params["desc"] = desc
            return self._request("PUT", f"/cards/{card_id}", params=params)

        def delete_card(self, card_id):
            self._request("DELETE", f"/cards/{card_id}")
            return {"id": card_id, "deleted": True}

    return TrelloService(creds.api_key, creds.token)


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


def get_boards(user_email: str) -> dict[str, Any]:
    """Get the user's Trello boards."""
    service = _trello_service(user_email)
    return {"boards": service.get_boards()}


def get_lists(user_email: str, board_id: str) -> dict[str, Any]:
    """Get the lists on a Trello board."""
    service = _trello_service(user_email)
    return {"lists": service.get_lists(board_id)}


def get_cards(user_email: str, list_id: str) -> dict[str, Any]:
    """Get the cards on a Trello list."""
    service = _trello_service(user_email)
    return {"cards": service.get_cards(list_id)}


def create_card(user_email: str, name: str, desc: str, list_id: str) -> dict[str, Any]:
    """Create a new card on a Trello list."""
    service = _trello_service(user_email)
    return {"card": service.create_card(name, desc, list_id)}


def update_card(user_email: str, card_id: str, name: str = None, desc: str = None) -> dict[str, Any]:
    """Update an existing Trello card."""
    service = _trello_service(user_email)
    return {"card": service.update_card(card_id, name, desc)}


def delete_card(user_email: str, card_id: str) -> dict[str, Any]:
    """Delete a Trello card."""
    service = _trello_service(user_email)
    return {"result": service.delete_card(card_id)}


def get_trello_tools() -> list:
    """Return a list of LangChain tools for Trello."""
    from .tools import get_trello_tools as _get_trello_tools
    return _get_trello_tools()
