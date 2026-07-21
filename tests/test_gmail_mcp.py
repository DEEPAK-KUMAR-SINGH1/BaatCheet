import json
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest


BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from MCP.gmail import client  # noqa: E402


def test_gmail_credentials_require_matching_redirect_uri(tmp_path, monkeypatch):
    secrets_file = tmp_path / "credentials.json"
    secrets_file.write_text(
        json.dumps(
            {
                "web": {
                    "client_id": "client-id",
                    "client_secret": "client-secret",
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": ["http://localhost:9999/wrong"],
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(client, "CLIENT_SECRETS_FILE", str(secrets_file))
    monkeypatch.setattr(client, "REDIRECT_URI", "http://localhost:8000/mcp/gmail/callback")

    with pytest.raises(RuntimeError, match="redirect URI mismatch"):
        client.ensure_credentials_file()


def test_gmail_token_save_preserves_refresh_token_and_expiry(tmp_path, monkeypatch):
    monkeypatch.setattr(client, "TOKENS_DIR", tmp_path)

    first_creds = SimpleNamespace(
        token="first-token",
        refresh_token="refresh-token",
        token_uri="https://oauth2.googleapis.com/token",
        client_id="client-id",
        client_secret="client-secret",
        scopes=client.SCOPES,
        expiry=datetime(2026, 5, 7, 12, 0, 0),
    )
    client.save_token("User+Test@example.com", first_creds)

    refreshed_creds = SimpleNamespace(
        token="refreshed-token",
        refresh_token=None,
        token_uri="https://oauth2.googleapis.com/token",
        client_id="client-id",
        client_secret="client-secret",
        scopes=client.SCOPES,
        expiry=datetime(2026, 5, 7, 13, 0, 0),
    )
    client.save_token("User+Test@example.com", refreshed_creds)

    token_file = tmp_path / "user_test_example.com.json"
    data = json.loads(token_file.read_text(encoding="utf-8"))

    assert data["token"] == "refreshed-token"
    assert data["refresh_token"] == "refresh-token"
    assert data["expiry"] == "2026-05-07T13:00:00Z"


def test_gmail_oauth_code_verifier_survives_redirect(tmp_path, monkeypatch):
    monkeypatch.setattr(client, "OAUTH_STATES_DIR", tmp_path)

    state = client.create_oauth_state("user@example.com")
    verifier = client._new_code_verifier()

    client._save_oauth_code_verifier(state, "user@example.com", verifier)

    assert client._load_oauth_code_verifier(state, "user@example.com") == verifier
    assert not list(tmp_path.glob("*.json"))
