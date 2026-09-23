"""
YouTube OAuth and API helpers for the connector.

Configure a Google Cloud OAuth Web client and provide its client ID and secret
through environment variables.
"""

from __future__ import annotations

import base64
import hashlib
import importlib
import json
import logging
import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from jose import JWTError, jwt

from Connectors.oauth import google_oauth_client_config
from config import JWT_SECRET, load_env

load_env()

logger = logging.getLogger(__name__)

_HERE = Path(__file__).resolve().parent
TOKENS_DIR = _HERE / "tokens"
TOKENS_DIR.mkdir(parents=True, exist_ok=True)
OAUTH_STATES_DIR = _HERE / "oauth_states"
OAUTH_STATES_DIR.mkdir(parents=True, exist_ok=True)

SCOPES = [
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
]

REDIRECT_URI = os.getenv(
    "YOUTUBE_REDIRECT_URI",
    "http://localhost:8000/connectors/youtube/callback",
)

STATE_ALGORITHM = "HS256"
STATE_TTL_MINUTES = 15
CODE_VERIFIER_LENGTH = 96


def _import_youtube_oauth():
    try:
        request_module = importlib.import_module("google.auth.transport.requests")
        credentials_module = importlib.import_module("google.oauth2.credentials")
        flow_module = importlib.import_module("google_auth_oauthlib.flow")
    except ImportError as exc:
        raise RuntimeError(
            "YouTube connector dependencies are missing. Install google-api-python-client, google-auth, and google-auth-oauthlib."
        ) from exc
    return credentials_module.Credentials, flow_module.Flow, request_module.Request


def _import_youtube_api_client():
    try:
        discovery_module = importlib.import_module("googleapiclient.discovery")
    except ImportError as exc:
        raise RuntimeError(
            "YouTube connector dependencies are missing. Install google-api-python-client."
        ) from exc
    return discovery_module.build


def _import_media_file_upload():
    try:
        http_module = importlib.import_module("googleapiclient.http")
    except ImportError as exc:
        raise RuntimeError(
            "YouTube connector dependencies are missing. Install google-api-python-client."
        ) from exc
    return http_module.MediaFileUpload


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
        logger.warning("Could not read YouTube token for %s: %s", user_email, exc)
        return None


def oauth_credentials_configured() -> bool:
    try:
        _load_client_config()
        return True
    except RuntimeError:
        return False


def _load_client_config() -> tuple[str, dict[str, Any]]:
    data = google_oauth_client_config("YOUTUBE", "YouTube", REDIRECT_URI)
    return "web", data["web"]


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
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=STATE_TTL_MINUTES)
    token = jwt.encode(
        {"sub": user_email, "app": "youtube", "exp": expires_at},
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
        raise ValueError("Invalid or expired YouTube OAuth state.") from exc

    if payload.get("app") != "youtube" or not payload.get("sub"):
        raise ValueError("Invalid YouTube OAuth state.")
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
        raise ValueError("YouTube OAuth session expired. Start YouTube connection again.")

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    finally:
        path.unlink(missing_ok=True)

    if data.get("user_email") != user_email:
        raise ValueError("YouTube OAuth session does not match the current user.")

    expires_at = datetime.fromisoformat(str(data["expires_at"]))
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) > expires_at:
        raise ValueError("YouTube OAuth session expired. Start YouTube connection again.")

    code_verifier = data.get("code_verifier")
    if not code_verifier:
        raise ValueError("YouTube OAuth session is missing its code verifier.")
    return str(code_verifier)


def save_token(user_email: str, creds: Any) -> None:
    old_data = _read_token_data(user_email) or {}
    data = {
        "token": creds.token,
        "refresh_token": creds.refresh_token or old_data.get("refresh_token"),
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": list(creds.scopes or SCOPES),
        "expiry": _serialize_expiry(creds.expiry) or old_data.get("expiry"),
    }
    _token_path(user_email).write_text(
        json.dumps(data, indent=2),
        encoding="utf-8",
    )
    logger.info("YouTube token saved for %s", user_email)


def load_token(user_email: str) -> Any | None:
    Credentials, _, Request = _import_youtube_oauth()
    data = _read_token_data(user_email)
    if not data:
        return None

    creds = Credentials(
        token=data.get("token"),
        refresh_token=data.get("refresh_token"),
        token_uri=data.get("token_uri"),
        client_id=data.get("client_id"),
        client_secret=data.get("client_secret"),
        scopes=data.get("scopes") or SCOPES,
        expiry=_parse_expiry(data.get("expiry")),
    )

    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            save_token(user_email, creds)
        except Exception as exc:
            logger.warning("YouTube token refresh failed for %s: %s", user_email, exc)
            return None

    return creds if creds.valid else None


def delete_token(user_email: str) -> None:
    path = _token_path(user_email)
    if path.exists():
        path.unlink()
        logger.info("YouTube token deleted for %s", user_email)


def is_connected(user_email: str) -> bool:
    try:
        return load_token(user_email) is not None
    except RuntimeError:
        return False


def get_auth_url(user_email: str) -> str:
    ensure_oauth_config()
    _, Flow, _ = _import_youtube_oauth()
    code_verifier = _new_code_verifier()
    flow = Flow.from_client_config(
        google_oauth_client_config("YOUTUBE", "YouTube", REDIRECT_URI),
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
        code_verifier=code_verifier,
    )
    state = create_oauth_state(user_email)
    _save_oauth_code_verifier(state, user_email, code_verifier)
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
        state=state,
    )
    return auth_url


def exchange_code(user_email: str, code: str, state: str) -> Any:
    ensure_oauth_config()
    _, Flow, _ = _import_youtube_oauth()
    code_verifier = _load_oauth_code_verifier(state, user_email)
    flow = Flow.from_client_config(
        google_oauth_client_config("YOUTUBE", "YouTube", REDIRECT_URI),
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
        code_verifier=code_verifier,
    )
    flow.fetch_token(code=code)
    creds = flow.credentials
    save_token(user_email, creds)
    return creds


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
        "app": "youtube",
        "name": "YouTube",
        "connected": connected,
        "configured": configured,
        "status": status,
        "scopes": SCOPES,
        "redirect_uri": REDIRECT_URI,
        "capabilities": [
            "list_videos",
            "get_video",
            "upload_video",
            "update_video",
            "delete_video",
        ],
        "message": setup_error or missing_dependency or (
            "Connected" if connected else "Connect YouTube to let chat access your channel."
        ),
    }


def _youtube_service(user_email: str) -> Any:
    creds = load_token(user_email)
    if not creds:
        raise RuntimeError("YouTube is not connected for this user.")
    build = _import_youtube_api_client()
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


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


def list_videos(user_email: str, query: str = "", max_results: int = 10) -> dict[str, Any]:
    """List videos in the connected YouTube channel."""
    service = _youtube_service(user_email)
    max_results = max(1, min(int(max_results or 10), 50))
    params = {
        "part": "snippet",
        "type": "video",
        "forMine": True,
        "maxResults": max_results,
    }
    if query:
        params["q"] = query
    return service.search().list(**params).execute()


def get_video(user_email: str, video_id: str) -> dict[str, Any]:
    """Get a specific video from YouTube by ID."""
    service = _youtube_service(user_email)
    data = service.videos().list(
        part="snippet,statistics,status",
        id=video_id,
    ).execute()
    items = data.get("items", [])
    return items[0] if items else {"id": video_id, "found": False}


def upload_video(user_email: str, title: str, description: str, video_file_path: str) -> dict[str, Any]:
    """Upload a video to YouTube."""
    service = _youtube_service(user_email)
    MediaFileUpload = _import_media_file_upload()
    media = MediaFileUpload(video_file_path, resumable=True)
    body = {
        "snippet": {"title": title, "description": description},
        "status": {"privacyStatus": "private"},
    }
    return service.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    ).execute()


def update_video(user_email: str, video_id: str, title: str = None, description: str = None) -> dict[str, Any]:
    """Update an existing video on YouTube."""
    service = _youtube_service(user_email)
    current = get_video(user_email, video_id)
    if not current.get("snippet"):
        raise RuntimeError(f"YouTube video not found: {video_id}")
    snippet = dict(current["snippet"])
    if title is not None:
        snippet["title"] = title
    if description is not None:
        snippet["description"] = description
    if "categoryId" not in snippet:
        snippet["categoryId"] = "22"
    return service.videos().update(
        part="snippet",
        body={"id": video_id, "snippet": snippet},
    ).execute()


def delete_video(user_email: str, video_id: str) -> dict[str, Any]:
    """Delete a video from YouTube."""
    service = _youtube_service(user_email)
    service.videos().delete(id=video_id).execute()
    return {"id": video_id, "deleted": True}


def get_youtube_tools() -> list:
    """Return a list of LangChain tools for YouTube."""
    from .tools import get_youtube_tools as _get_youtube_tools
    return _get_youtube_tools()
