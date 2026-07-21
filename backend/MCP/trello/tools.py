"""LangChain tools exposed by the Trello MCP connector."""

from __future__ import annotations

import json
from typing import Any, Callable

from langchain_core.tools import tool

from MCP.context import get_current_user_email
from MCP.trello import client


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def _run(action: Callable[[str], Any]) -> str:
    user_email = get_current_user_email()
    if not user_email:
        return "Trello tool unavailable: no authenticated chatbot user is active."
    if not client.is_connected(user_email):
        return "Trello is not connected. Ask the user to connect Trello from the chat header first."
    try:
        return _json(action(user_email))
    except Exception as exc:
        return f"Trello tool error: {type(exc).__name__}: {exc}"


@tool
def trello_get_boards() -> str:
    """Get the connected Trello user's boards."""
    return _run(lambda email: {"boards": client.get_boards(email)})


@tool
def trello_get_lists(board_id: str) -> str:
    """Get the lists on a Trello board."""
    return _run(lambda email: {"lists": client.get_lists(email, board_id)})


@tool
def trello_get_cards(list_id: str) -> str:
    """Get the cards on a Trello list."""
    return _run(lambda email: {"cards": client.get_cards(email, list_id)})


@tool
def trello_create_card(name: str, desc: str, list_id: str) -> str:
    """Create a new card on a Trello list."""
    return _run(
        lambda email: {
            "card": client.create_card(email, name, desc, list_id)
        }
    )


@tool
def trello_update_card(card_id: str, name: str = None, desc: str = None) -> str:
    """Update an existing Trello card."""
    return _run(
        lambda email: {
            "card": client.update_card(email, card_id, name, desc)
        }
    )


@tool
def trello_delete_card(card_id: str) -> str:
    """Delete a Trello card."""
    return _run(lambda email: {"result": client.delete_card(email, card_id)})


def get_trello_tools() -> list:
    return [
        trello_get_boards,
        trello_get_lists,
        trello_get_cards,
        trello_create_card,
        trello_update_card,
        trello_delete_card,
    ]