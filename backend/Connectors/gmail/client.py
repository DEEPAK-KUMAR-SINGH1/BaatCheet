"""
Gmail OAuth and API helpers for the connector.

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
from email.mime.text import MIMEText
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
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.labels",
    "https://www.googleapis.com/auth/gmail.send",
]

REDIRECT_URI = os.getenv(
    "GMAIL_REDIRECT_URI",
    "http://localhost:8000/connectors/gmail/callback",
)

STATE_ALGORITHM = "HS256"
STATE_TTL_MINUTES = 15
CODE_VERIFIER_LENGTH = 96


def _import_google_oauth():
    try:
        request_module = importlib.import_module("google.auth.transport.requests")
        credentials_module = importlib.import_module("google.oauth2.credentials")
        flow_module = importlib.import_module("google_auth_oauthlib.flow")
    except ImportError as exc:
        raise RuntimeError(
            "Gmail connector dependencies are missing. Install "
            "google-api-python-client, google-auth, and google-auth-oauthlib."
        ) from exc
    return credentials_module.Credentials, flow_module.Flow, request_module.Request


def _import_google_api_client():
    try:
        discovery_module = importlib.import_module("googleapiclient.discovery")
    except ImportError as exc:
        raise RuntimeError(
            "Gmail connector dependencies are missing. Install "
            "google-api-python-client."
        ) from exc
    return discovery_module.build


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
        logger.warning("Could not read Gmail token for %s: %s", user_email, exc)
        return None


def oauth_credentials_configured() -> bool:
    try:
        _load_client_config()
        return True
    except RuntimeError:
        return False


def _load_client_config() -> tuple[str, dict[str, Any]]:
    data = google_oauth_client_config("GMAIL", "Gmail", REDIRECT_URI)
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
        {"sub": user_email, "app": "gmail", "exp": expires_at},
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
        raise ValueError("Invalid or expired Gmail OAuth state.") from exc

    if payload.get("app") != "gmail" or not payload.get("sub"):
        raise ValueError("Invalid Gmail OAuth state.")
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
        raise ValueError("Gmail OAuth session expired. Start Gmail connection again.")

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    finally:
        path.unlink(missing_ok=True)

    if data.get("user_email") != user_email:
        raise ValueError("Gmail OAuth session does not match the current user.")

    expires_at = datetime.fromisoformat(str(data["expires_at"]))
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) > expires_at:
        raise ValueError("Gmail OAuth session expired. Start Gmail connection again.")

    code_verifier = data.get("code_verifier")
    if not code_verifier:
        raise ValueError("Gmail OAuth session is missing its code verifier.")
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
    logger.info("Gmail token saved for %s", user_email)


def load_token(user_email: str) -> Any | None:
    Credentials, _, Request = _import_google_oauth()
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
            logger.warning("Gmail token refresh failed for %s: %s", user_email, exc)
            return None

    return creds if creds.valid else None


def delete_token(user_email: str) -> None:
    path = _token_path(user_email)
    if path.exists():
        path.unlink()
        logger.info("Gmail token deleted for %s", user_email)


def is_connected(user_email: str) -> bool:
    try:
        return load_token(user_email) is not None
    except RuntimeError:
        return False


def get_auth_url(user_email: str) -> str:
    ensure_oauth_config()
    _, Flow, _ = _import_google_oauth()
    code_verifier = _new_code_verifier()
    flow = Flow.from_client_config(
        google_oauth_client_config("GMAIL", "Gmail", REDIRECT_URI),
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
    _, Flow, _ = _import_google_oauth()
    code_verifier = _load_oauth_code_verifier(state, user_email)
    flow = Flow.from_client_config(
        google_oauth_client_config("GMAIL", "Gmail", REDIRECT_URI),
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
        "app": "gmail",
        "name": "Gmail",
        "connected": connected,
        "configured": configured,
        "status": status,
        "scopes": SCOPES,
        "redirect_uri": REDIRECT_URI,
        "capabilities": [
            "search_messages",
            "read_messages",
            "list_labels",
            "modify_labels",
            "send_email",
        ],
        "message": setup_error or missing_dependency or (
            "Connected" if connected else "Connect Gmail to let chat use your mailbox."
        ),
    }


def _gmail_service(user_email: str) -> Any:
    creds = load_token(user_email)
    if not creds:
        raise RuntimeError("Gmail is not connected for this user.")
    build = _import_google_api_client()
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


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
    plain_parts: list[str] = []
    html_parts: list[str] = []

    def walk(part: dict[str, Any]) -> None:
        mime_type = part.get("mimeType", "")
        body_data = (part.get("body") or {}).get("data")
        if body_data:
            decoded = _decode_body(body_data)
            if mime_type == "text/plain":
                plain_parts.append(decoded)
            elif mime_type == "text/html":
                html_parts.append(_strip_html(decoded))
        for child in part.get("parts", []) or []:
            walk(child)

    walk(payload)
    body = "\n\n".join(p.strip() for p in plain_parts if p.strip())
    if not body:
        body = "\n\n".join(p.strip() for p in html_parts if p.strip())
    return body[:12000]


def search_messages(
    user_email: str,
    query: str = "",
    max_results: int = 5,
) -> list[dict[str, Any]]:
    service = _gmail_service(user_email)
    max_results = max(1, min(int(max_results or 5), 10))
    params: dict[str, Any] = {"userId": "me", "maxResults": max_results}
    if query.strip():
        params["q"] = query.strip()

    response = service.users().messages().list(**params).execute()
    items = response.get("messages", []) or []
    messages = []
    for item in items[:max_results]:
        msg = service.users().messages().get(
            userId="me",
            id=item["id"],
            format="metadata",
            metadataHeaders=["From", "To", "Subject", "Date"],
        ).execute()
        headers = _headers_from_payload(msg.get("payload", {}))
        messages.append(
            {
                "id": msg.get("id"),
                "thread_id": msg.get("threadId"),
                "from": headers.get("from", ""),
                "to": headers.get("to", ""),
                "subject": headers.get("subject", ""),
                "date": headers.get("date", ""),
                "snippet": msg.get("snippet", ""),
            }
        )
    return messages


def read_message(user_email: str, message_id: str) -> dict[str, Any]:
    service = _gmail_service(user_email)
    msg = service.users().messages().get(
        userId="me",
        id=message_id,
        format="full",
    ).execute()
    payload = msg.get("payload", {})
    headers = _headers_from_payload(payload)
    return {
        "id": msg.get("id"),
        "thread_id": msg.get("threadId"),
        "from": headers.get("from", ""),
        "to": headers.get("to", ""),
        "cc": headers.get("cc", ""),
        "subject": headers.get("subject", ""),
        "date": headers.get("date", ""),
        "snippet": msg.get("snippet", ""),
        "body": _extract_message_body(payload),
        "label_ids": msg.get("labelIds", []),
    }


def list_labels(user_email: str) -> list[dict[str, Any]]:
    service = _gmail_service(user_email)
    response = service.users().labels().list(userId="me").execute()
    return [
        {
            "id": label.get("id"),
            "name": label.get("name"),
            "type": label.get("type"),
        }
        for label in response.get("labels", []) or []
    ]


def modify_message(
    user_email: str,
    message_id: str,
    add_label_ids: list[str] | None = None,
    remove_label_ids: list[str] | None = None,
) -> dict[str, Any]:
    service = _gmail_service(user_email)
    return service.users().messages().modify(
        userId="me",
        id=message_id,
        body={
            "addLabelIds": add_label_ids or [],
            "removeLabelIds": remove_label_ids or [],
        },
    ).execute()


def send_email(
    user_email: str,
    to: str,
    subject: str,
    body: str,
    cc: str = "",
    bcc: str = "",
) -> dict[str, Any]:
    service = _gmail_service(user_email)
    message = MIMEText(body, "plain", "utf-8")
    message["To"] = to
    message["Subject"] = subject
    if cc:
        message["Cc"] = cc
    if bcc:
        message["Bcc"] = bcc

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
    return service.users().messages().send(
        userId="me",
        body={"raw": raw},
    ).execute()
