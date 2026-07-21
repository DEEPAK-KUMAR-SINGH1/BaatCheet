"""
Google Drive OAuth and API helpers for the MCP connector.

The OAuth client secret is expected at backend/MCP/google_drive/credentials.json by
default. Override it with GOOGLE_DRIVE_CLIENT_SECRETS_FILE when needed.
"""

from __future__ import annotations

import base64
import hashlib
import io
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
        "GOOGLE_DRIVE_CLIENT_SECRETS_FILE",
        str(_HERE / "credentials.json"),
    )
)
TOKENS_DIR = _HERE / "tokens"
TOKENS_DIR.mkdir(parents=True, exist_ok=True)
OAUTH_STATES_DIR = _HERE / "oauth_states"
OAUTH_STATES_DIR.mkdir(parents=True, exist_ok=True)

SCOPES = [
    "https://www.googleapis.com/auth/drive.file",
]

REDIRECT_URI = os.getenv(
    "GOOGLE_DRIVE_REDIRECT_URI",
    "http://localhost:8000/mcp/google_drive/callback",
)

STATE_ALGORITHM = "HS256"
STATE_TTL_MINUTES = 15
CODE_VERIFIER_LENGTH = 96


def _import_google_drive_oauth():
    try:
        request_module = importlib.import_module("google.auth.transport.requests")
        credentials_module = importlib.import_module("google.oauth2.credentials")
        flow_module = importlib.import_module("google_auth_oauthlib.flow")
    except ImportError as exc:
        raise RuntimeError(
            "Google Drive connector dependencies are missing. Install google-api-python-client, google-auth, and google-auth-oauthlib."
        ) from exc
    return credentials_module.Credentials, flow_module.Flow, request_module.Request


def _import_google_drive_api_client():
    try:
        discovery_module = importlib.import_module("googleapiclient.discovery")
    except ImportError as exc:
        raise RuntimeError(
            "Google Drive connector dependencies are missing. Install google-api-python-client."
        ) from exc
    return discovery_module.build


def _import_media_upload():
    try:
        http_module = importlib.import_module("googleapiclient.http")
    except ImportError as exc:
        raise RuntimeError(
            "Google Drive connector dependencies are missing. Install google-api-python-client."
        ) from exc
    return http_module.MediaIoBaseUpload


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
        logger.warning("Could not read Google Drive token for %s: %s", user_email, exc)
        return None


def credentials_file_exists() -> bool:
    return os.path.exists(CLIENT_SECRETS_FILE)


def _load_client_config() -> tuple[str, dict[str, Any]]:
    try:
        with open(CLIENT_SECRETS_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Google Drive OAuth client secret at {CLIENT_SECRETS_FILE} is not valid JSON."
        ) from exc

    if "web" in data:
        client_type = "web"
        config = data["web"]
    elif "installed" in data:
        client_type = "installed"
        config = data["installed"]
    else:
        raise RuntimeError(
            "Google Drive OAuth client secret must contain a 'web' or 'installed' client."
        )

    required = ("client_id", "client_secret", "auth_uri", "token_uri")
    missing = [key for key in required if not config.get(key)]
    if missing:
        raise RuntimeError(
            "Google Drive OAuth client secret is missing required field(s): "
            + ", ".join(missing)
            + "."
        )

    redirect_uris = config.get("redirect_uris") or []
    if client_type == "web" and REDIRECT_URI not in redirect_uris:
        raise RuntimeError(
            "Google Drive redirect URI mismatch. Add "
            f"{REDIRECT_URI} to the OAuth client's Authorized redirect URIs "
            "in Google Cloud Console, then download the updated JSON."
        )

    return client_type, config


def ensure_credentials_file() -> None:
    if not credentials_file_exists():
        raise FileNotFoundError(
            f"Google Drive OAuth client secret was not found at {CLIENT_SECRETS_FILE}. "
            "Create a Google OAuth client ID and place the JSON file there, "
            "or set GOOGLE_DRIVE_CLIENT_SECRETS_FILE."
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
        {"sub": user_email, "app": "google_drive", "exp": expires_at},
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
        raise ValueError("Invalid or expired Google Drive OAuth state.") from exc

    if payload.get("app") != "google_drive" or not payload.get("sub"):
        raise ValueError("Invalid Google Drive OAuth state.")
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
        raise ValueError("Google Drive OAuth session expired. Start Google Drive connection again.")

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    finally:
        path.unlink(missing_ok=True)

    if data.get("user_email") != user_email:
        raise ValueError("Google Drive OAuth session does not match the current user.")

    expires_at = datetime.fromisoformat(str(data["expires_at"]))
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) > expires_at:
        raise ValueError("Google Drive OAuth session expired. Start Google Drive connection again.")

    code_verifier = data.get("code_verifier")
    if not code_verifier:
        raise ValueError("Google Drive OAuth session is missing its code verifier.")
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
    logger.info("Google Drive token saved for %s", user_email)


def load_token(user_email: str) -> Any | None:
    Credentials, _, Request = _import_google_drive_oauth()
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
            logger.warning("Google Drive token refresh failed for %s: %s", user_email, exc)
            return None

    return creds if creds.valid else None


def delete_token(user_email: str) -> None:
    path = _token_path(user_email)
    if path.exists():
        path.unlink()
        logger.info("Google Drive token deleted for %s", user_email)


def is_connected(user_email: str) -> bool:
    try:
        return load_token(user_email) is not None
    except RuntimeError:
        return False


def get_auth_url(user_email: str) -> str:
    ensure_credentials_file()
    _, Flow, _ = _import_google_drive_oauth()
    code_verifier = _new_code_verifier()
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
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
    ensure_credentials_file()
    _, Flow, _ = _import_google_drive_oauth()
    code_verifier = _load_oauth_code_verifier(state, user_email)
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
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
        "app": "google_drive",
        "name": "Google Drive",
        "connected": connected,
        "configured": configured,
        "status": status,
        "scopes": SCOPES,
        "redirect_uri": REDIRECT_URI,
        "capabilities": [
            "list_files",
            "get_file",
            "create_file",
            "update_file",
            "delete_file",
        ],
        "message": setup_error or missing_dependency or (
            "Connected" if connected else "Connect Google Drive to let chat access your files."
        ),
    }


def _drive_service(user_email: str) -> Any:
    creds = load_token(user_email)
    if not creds:
        raise RuntimeError("Google Drive is not connected for this user.")
    build = _import_google_drive_api_client()
    return build("drive", "v3", credentials=creds, cache_discovery=False)


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


def list_files(user_email: str, query: str = "", page_size: int = 10) -> dict[str, Any]:
    """List files in Google Drive."""
    service = _drive_service(user_email)
    page_size = max(1, min(int(page_size or 10), 100))
    params = {
        "pageSize": page_size,
        "fields": "files(id,name,mimeType,size,createdTime,modifiedTime,webViewLink)",
        "orderBy": "modifiedTime desc",
    }
    if query:
        params["q"] = query
    return service.files().list(**params).execute()


def get_file(user_email: str, file_id: str) -> dict[str, Any]:
    """Get a specific file from Google Drive by ID."""
    service = _drive_service(user_email)
    return service.files().get(
        fileId=file_id,
        fields="id,name,mimeType,size,createdTime,modifiedTime,webViewLink,owners,shared",
    ).execute()


def create_file(user_email: str, name: str, content: bytes, mime_type: str = "application/octet-stream") -> dict[str, Any]:
    """Create a new file in Google Drive."""
    service = _drive_service(user_email)
    MediaIoBaseUpload = _import_media_upload()
    media = MediaIoBaseUpload(io.BytesIO(content), mimetype=mime_type, resumable=False)
    return service.files().create(
        body={"name": name},
        media_body=media,
        fields="id,name,mimeType,webViewLink",
    ).execute()


def update_file(user_email: str, file_id: str, content: bytes = None, name: str = None) -> dict[str, Any]:
    """Update an existing file in Google Drive."""
    service = _drive_service(user_email)
    body = {"name": name} if name else None
    media = None
    if content is not None:
        MediaIoBaseUpload = _import_media_upload()
        media = MediaIoBaseUpload(io.BytesIO(content), mimetype="application/octet-stream", resumable=False)
    return service.files().update(
        fileId=file_id,
        body=body,
        media_body=media,
        fields="id,name,mimeType,webViewLink",
    ).execute()


def delete_file(user_email: str, file_id: str) -> dict[str, Any]:
    """Delete a file from Google Drive."""
    service = _drive_service(user_email)
    service.files().delete(fileId=file_id).execute()
    return {"id": file_id, "deleted": True}


def get_google_drive_tools() -> list:
    """Return a list of LangChain tools for Google Drive MCP."""
    from .tools import get_google_drive_tools as _get_google_drive_tools
    return _get_google_drive_tools()
