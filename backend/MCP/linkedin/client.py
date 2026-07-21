"""
LinkedIn OAuth and API helpers for the MCP connector.

The OAuth client secret is expected at backend/MCP/linkedin/credentials.json by
default. Override it with LINKEDIN_CLIENT_SECRETS_FILE when needed.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from urllib.parse import urlencode

import requests

from jose import JWTError, jwt

from config import JWT_SECRET, load_env

load_env()

logger = logging.getLogger(__name__)

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[2]


def _resolve_path(value: str) -> str:
    path = Path(value)
    if not path.is_absolute():
        path = _ROOT / path
    return str(path)


CLIENT_SECRETS_FILE = _resolve_path(
    os.getenv(
        "LINKEDIN_CLIENT_SECRETS_FILE",
        str(_HERE / "credentials.json"),
    )
)
TOKENS_DIR = _HERE / "tokens"
TOKENS_DIR.mkdir(parents=True, exist_ok=True)
OAUTH_STATES_DIR = _HERE / "oauth_states"
OAUTH_STATES_DIR.mkdir(parents=True, exist_ok=True)

SCOPES = [
    "r_liteprofile",
    "r_emailaddress",
    "w_member_social",
]

AUTH_URI = "https://www.linkedin.com/oauth/v2/authorization"
TOKEN_URI = "https://www.linkedin.com/oauth/v2/accessToken"
API_BASE = "https://api.linkedin.com"

REDIRECT_URI = os.getenv(
    "LINKEDIN_REDIRECT_URI",
    "http://localhost:8000/mcp/linkedin/callback",
)

STATE_ALGORITHM = "HS256"
STATE_TTL_MINUTES = 15
CODE_VERIFIER_LENGTH = 96


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
        logger.warning("Could not read LinkedIn token for %s: %s", user_email, exc)
        return None


def credentials_file_exists() -> bool:
    return os.path.exists(CLIENT_SECRETS_FILE)


def _load_client_config() -> tuple[str, dict[str, Any]]:
    try:
        with open(CLIENT_SECRETS_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"LinkedIn OAuth client secret at {CLIENT_SECRETS_FILE} is not valid JSON."
        ) from exc

    if "web" in data:
        client_type = "web"
        config = data["web"]
    elif "installed" in data:
        client_type = "installed"
        config = data["installed"]
    else:
        client_type = "web"
        config = data

    config.setdefault("auth_uri", AUTH_URI)
    config.setdefault("token_uri", TOKEN_URI)
    required = ("client_id", "client_secret")
    missing = [key for key in required if not config.get(key)]
    if missing:
        raise RuntimeError(
            "LinkedIn OAuth client secret is missing required field(s): "
            + ", ".join(missing)
            + "."
        )

    redirect_uris = config.get("redirect_uris") or [REDIRECT_URI]
    if client_type == "web" and REDIRECT_URI not in redirect_uris:
        raise RuntimeError(
            "LinkedIn redirect URI mismatch. Add "
            f"{REDIRECT_URI} to the OAuth client's Authorized redirect URIs "
            "in LinkedIn Developer Portal, then download the updated JSON."
        )

    return client_type, config


def ensure_credentials_file() -> None:
    if not credentials_file_exists():
        raise FileNotFoundError(
            f"LinkedIn OAuth client secret was not found at {CLIENT_SECRETS_FILE}. "
            "Create a LinkedIn OAuth application and place the JSON file there, "
            "or set LINKEDIN_CLIENT_SECRETS_FILE."
        )
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
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=STATE_TTL_MINUTES)
    token = jwt.encode(
        {"sub": user_email, "app": "linkedin", "exp": expires_at},
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
        raise ValueError("Invalid or expired LinkedIn OAuth state.") from exc

    if payload.get("app") != "linkedin" or not payload.get("sub"):
        raise ValueError("Invalid LinkedIn OAuth state.")
    return str(payload["sub"])


def _new_code_verifier() -> str:
    return secrets.token_urlsafe(CODE_VERIFIER_LENGTH)[:128]


def _save_oauth_code_verifier(state: str, user_email: str, code_verifier: str) -> None:
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=STATE_TTL_MINUTES)
    _oauth_state_path(state).write_text(
        json.dumps(
            {
                "user_email": user_email,
                "code_verifier": code_verifier,
                "expires_at": expires_at.isoformat(),
            }
        ),
        encoding="utf-8",
    )


def _load_oauth_code_verifier(state: str, user_email: str) -> str:
    path = _oauth_state_path(state)
    if not path.exists():
        raise ValueError("LinkedIn OAuth session expired. Start LinkedIn connection again.")

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    finally:
        path.unlink(missing_ok=True)

    if data.get("user_email") != user_email:
        raise ValueError("LinkedIn OAuth session does not match the current user.")

    expires_at = datetime.fromisoformat(str(data["expires_at"]))
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) > expires_at:
        raise ValueError("LinkedIn OAuth session expired. Start LinkedIn connection again.")

    code_verifier = data.get("code_verifier")
    if not code_verifier:
        raise ValueError("LinkedIn OAuth session is missing its code verifier.")
    return str(code_verifier)


def save_token(user_email: str, creds: Any) -> None:
    old_data = _read_token_data(user_email) or {}
    access_token = creds if isinstance(creds, str) else getattr(creds, "token", None)
    data = {
        "access_token": access_token,
        "refresh_token": getattr(creds, "refresh_token", None) or old_data.get("refresh_token"),
        "token_type": getattr(creds, "token_type", "Bearer"),
        "expires_in": getattr(creds, "expires_in", old_data.get("expires_in")),
        "scope": getattr(creds, "scope", list(SCOPES)),
    }
    _token_path(user_email).write_text(
        json.dumps(data, indent=2),
        encoding="utf-8",
    )
    logger.info("LinkedIn token saved for %s", user_email)


def load_token(user_email: str) -> Any | None:
    data = _read_token_data(user_email)
    if not data:
        return None

    class LinkedInCreds:
        def __init__(self, data):
            self.token = data.get("access_token")
            self.refresh_token = data.get("refresh_token")
            self.token_uri = TOKEN_URI
            self.client_id = data.get("client_id", "")
            self.client_secret = data.get("client_secret", "")
            self.scopes = data.get("scope", SCOPES)
            self.expires_at = None
            self.valid = bool(self.token)

        def expired(self):
            return not self.valid

        def refresh(self, request):
            pass

    return LinkedInCreds(data)


def delete_token(user_email: str) -> None:
    path = _token_path(user_email)
    if path.exists():
        path.unlink()
        logger.info("LinkedIn token deleted for %s", user_email)


def is_connected(user_email: str) -> bool:
    try:
        creds = load_token(user_email)
        return bool(creds and getattr(creds, "valid", False))
    except RuntimeError:
        return False


def get_auth_url(user_email: str) -> str:
    ensure_credentials_file()
    _, config = _load_client_config()
    state = create_oauth_state(user_email)
    params = {
        "response_type": "code",
        "client_id": config["client_id"],
        "redirect_uri": REDIRECT_URI,
        "state": state,
        "scope": " ".join(SCOPES),
    }
    return f"{config.get('auth_uri', AUTH_URI)}?{urlencode(params)}"


def exchange_code(user_email: str, code: str, state: str) -> Any:
    ensure_credentials_file()
    parse_oauth_state(state)
    _, config = _load_client_config()
    response = requests.post(
        config.get("token_uri", TOKEN_URI),
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "client_id": config["client_id"],
            "client_secret": config["client_secret"],
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"LinkedIn token exchange failed: {response.text[:300]}")
    data = response.json()
    creds = SimpleNamespace(
        token=data.get("access_token"),
        refresh_token=data.get("refresh_token"),
        token_type=data.get("token_type", "Bearer"),
        expires_in=data.get("expires_in"),
        scope=data.get("scope") or list(SCOPES),
        valid=bool(data.get("access_token")),
    )
    if not creds.valid:
        raise RuntimeError("LinkedIn token exchange did not return an access token.")
    save_token(user_email, creds)
    return creds


def get_connection_status(user_email: str) -> dict[str, Any]:
    configured = False
    setup_error = None
    missing_dependency = None
    connected = False

    try:
        ensure_credentials_file()
        configured = True
    except FileNotFoundError as exc:
        setup_error = str(exc)
    except RuntimeError as exc:
        setup_error = str(exc)
        configured = credentials_file_exists()

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
        "app": "linkedin",
        "name": "LinkedIn",
        "connected": connected,
        "configured": configured,
        "status": status,
        "scopes": SCOPES,
        "redirect_uri": REDIRECT_URI,
        "capabilities": [
            "get_profile",
            "get_connections",
            "share_post",
            "get_organization_updates",
        ],
        "message": setup_error or missing_dependency or (
            "Connected" if connected else "Connect LinkedIn to let chat use your profile."
        ),
    }


def _linkedin_service(user_email: str) -> Any:
    creds = load_token(user_email)
    if not creds or not getattr(creds, "valid", False):
        raise RuntimeError("LinkedIn is not connected for this user.")
    return creds


def _auth_headers(user_email: str) -> dict[str, str]:
    creds = _linkedin_service(user_email)
    return {
        "Authorization": f"Bearer {creds.token}",
        "X-Restli-Protocol-Version": "2.0.0",
        "Content-Type": "application/json",
    }


def _request(user_email: str, method: str, path: str, **kwargs) -> Any:
    response = requests.request(
        method,
        f"{API_BASE}{path}",
        headers=_auth_headers(user_email),
        timeout=30,
        **kwargs,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"LinkedIn API error {response.status_code}: {response.text[:300]}")
    if response.status_code == 204 or not response.text:
        return {}
    return response.json()


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


def get_profile(user_email: str) -> dict[str, Any]:
    """Get the user's LinkedIn profile."""
    return _request(
        user_email,
        "GET",
        "/v2/me?projection=(id,localizedFirstName,localizedLastName,profilePicture(displayImage~:playableStreams))",
    )


def get_connections(user_email: str, max_results: int = 10) -> list[dict[str, Any]]:
    """Get the user's LinkedIn connections."""
    max_results = max(1, min(int(max_results or 10), 100))
    data = _request(user_email, "GET", f"/v2/connections?q=viewer&count={max_results}")
    return data.get("elements", data if isinstance(data, list) else [])


def share_post(user_email: str, content: str, visibility: str = "PUBLIC") -> dict[str, Any]:
    """Share a post on LinkedIn."""
    profile = get_profile(user_email)
    author = f"urn:li:person:{profile['id']}"
    visibility_value = "PUBLIC" if visibility.upper() == "PUBLIC" else "CONNECTIONS"
    return _request(
        user_email,
        "POST",
        "/v2/ugcPosts",
        json={
            "author": author,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": content},
                    "shareMediaCategory": "NONE",
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": visibility_value,
            },
        },
    )


# Note: Additional LinkedIn API functions can be added here as needed.


def get_linkedin_tools() -> list:
    """Return a list of LangChain tools for LinkedIn MCP."""
    from .tools import get_linkedin_tools as _get_linkedin_tools
    return _get_linkedin_tools()
