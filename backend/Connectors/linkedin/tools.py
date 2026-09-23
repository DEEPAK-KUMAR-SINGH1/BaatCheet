"""LangChain tools exposed by the LinkedIn connector."""

from __future__ import annotations

import json
from typing import Any, Callable

from langchain_core.tools import tool

from Connectors.context import get_current_user_email
from Connectors.linkedin import client


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def _run(action: Callable[[str], Any]) -> str:
    user_email = get_current_user_email()
    if not user_email:
        return "LinkedIn tool unavailable: no authenticated chatbot user is active."
    if not client.is_connected(user_email):
        return "LinkedIn is not connected. Ask the user to connect LinkedIn from the chat header first."
    try:
        return _json(action(user_email))
    except Exception as exc:
        return f"LinkedIn tool error: {type(exc).__name__}: {exc}"


@tool
def linkedin_get_profile() -> str:
    """Get the connected LinkedIn user's profile."""
    return _run(lambda email: {"profile": client.get_profile(email)})


@tool
def linkedin_get_connections(max_results: int = 10) -> str:
    """Get the connected LinkedIn user's connections."""
    return _run(lambda email: {"connections": client.get_connections(email, max_results)})


@tool
def linkedin_share_post(content: str, visibility: str = "PUBLIC") -> str:
    """Share a post on the connected LinkedIn account."""
    return _run(
        lambda email: {
            "post": client.share_post(email, content, visibility)
        }
    )


def get_linkedin_tools() -> list:
    return [
        linkedin_get_profile,
        linkedin_get_connections,
        linkedin_share_post,
    ]
