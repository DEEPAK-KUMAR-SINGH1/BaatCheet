"""Environment-backed OAuth config helpers for connector clients."""

from __future__ import annotations

import os


GOOGLE_AUTH_URI = "https://accounts.google.com/o/oauth2/auth"
GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"


def _first_env(*names: str) -> str:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


def google_oauth_client_config(_prefix: str, app_name: str, redirect_uri: str) -> dict:
    client_id = _first_env("GOOGLE_OAUTH_CLIENT_ID", "GOOGLE_CLIENT_ID")
    client_secret = _first_env("GOOGLE_OAUTH_CLIENT_SECRET", "GOOGLE_CLIENT_SECRET")
    missing = []
    if not client_id:
        missing.append("GOOGLE_OAUTH_CLIENT_ID")
    if not client_secret:
        missing.append("GOOGLE_OAUTH_CLIENT_SECRET")
    if missing:
        raise RuntimeError(
            f"{app_name} OAuth is missing required environment variable(s): "
            + ", ".join(missing)
            + ". Configure a Google Cloud OAuth Web client and add these values to .env."
        )

    return {
        "web": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": GOOGLE_AUTH_URI,
            "token_uri": GOOGLE_TOKEN_URI,
            "redirect_uris": [redirect_uri],
        }
    }


def oauth_client_config(prefix: str, app_name: str, redirect_uri: str, auth_uri: str, token_uri: str) -> dict:
    client_id = _first_env(f"{prefix}_CLIENT_ID", f"{prefix}_OAUTH_CLIENT_ID")
    client_secret = _first_env(f"{prefix}_CLIENT_SECRET", f"{prefix}_OAUTH_CLIENT_SECRET")
    missing = []
    if not client_id:
        missing.append(f"{prefix}_CLIENT_ID")
    if not client_secret:
        missing.append(f"{prefix}_CLIENT_SECRET")
    if missing:
        raise RuntimeError(
            f"{app_name} OAuth is missing required environment variable(s): "
            + ", ".join(missing)
            + ". Configure the provider app and add these values to .env."
        )

    return {
        "client_id": client_id,
        "client_secret": client_secret,
        "auth_uri": auth_uri,
        "token_uri": token_uri,
        "redirect_uris": [redirect_uri],
    }
