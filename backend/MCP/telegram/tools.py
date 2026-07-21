"""LangChain tools exposed by the Telegram MCP connector."""

from __future__ import annotations

import json
from typing import Any, Callable

from langchain_core.tools import tool

from MCP.context import get_current_user_email
from MCP.telegram import client


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def _run(action: Callable[[str], Any]) -> str:
    user_email = get_current_user_email()
    if not user_email:
        return "Telegram tool unavailable: no authenticated chatbot user is active."
    if not client.is_connected(user_email):
        return "Telegram is not connected. Ask the user to connect Telegram from the chat header first."
    try:
        return _json(action(user_email))
    except Exception as exc:
        return f"Telegram tool error: {type(exc).__name__}: {exc}"


@tool
def telegram_get_me() -> str:
    """Get the connected Telegram bot's information."""
    return _run(lambda email: {"bot": client.get_me(email)})


@tool
def telegram_send_message(chat_id: str, text: str) -> str:
    """Send a message to a chat on the connected Telegram bot."""
    return _run(
        lambda email: {
            "message": client.send_message(email, chat_id, text)
        }
    )


@tool
def telegram_get_updates(offset: int = None, limit: int = 100) -> str:
    """Get updates from the connected Telegram bot."""
    return _run(lambda email: {"updates": client.get_updates(email, offset, limit)})


@tool
def telegram_get_chat(chat_id: str) -> str:
    """Get information about a chat from the connected Telegram bot."""
    return _run(lambda email: {"chat": client.get_chat(email, chat_id)})


def get_telegram_tools() -> list:
    return [
        telegram_get_me,
        telegram_send_message,
        telegram_get_updates,
        telegram_get_chat,
    ]