"""LangChain tools exposed by the Notion MCP connector."""

from __future__ import annotations

import json
from typing import Any, Callable

from langchain_core.tools import tool

from MCP.context import get_current_user_email
from MCP.notion import client


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def _run(action: Callable[[str], Any]) -> str:
    user_email = get_current_user_email()
    if not user_email:
        return "Notion tool unavailable: no authenticated chatbot user is active."
    if not client.is_connected(user_email):
        return "Notion is not connected. Ask the user to connect Notion from the chat header first."
    try:
        return _json(action(user_email))
    except Exception as exc:
        return f"Notion tool error: {type(exc).__name__}: {exc}"


@tool
def notion_search(query: str = "") -> str:
    """Search for content in the connected Notion workspace."""
    return _run(lambda email: {"results": client.search(email, query)})


@tool
def notion_get_block(block_id: str) -> str:
    """Get a block from the connected Notion workspace by block ID."""
    return _run(lambda email: {"block": client.get_block(email, block_id)})


@tool
def notion_get_page(page_id: str) -> str:
    """Get a page from the connected Notion workspace by page ID."""
    return _run(lambda email: {"page": client.get_page(email, page_id)})


@tool
def notion_create_page(parent_id: str, properties: str = "{}") -> str:
    """Create a new page in the connected Notion workspace."""
    import json as _json
    try:
        props = _json.loads(properties)
    except Exception:
        props = {}
    return _run(
        lambda email: {
            "page": client.create_page(email, parent_id, props)
        }
    )


@tool
def notion_update_page(page_id: str, properties: str = "{}") -> str:
    """Update an existing page in the connected Notion workspace."""
    import json as _json
    try:
        props = _json.loads(properties)
    except Exception:
        props = {}
    return _run(
        lambda email: {
            "page": client.update_page(email, page_id, props)
        }
    )


@tool
def notion_delete_page(page_id: str) -> str:
    """Delete a page from the connected Notion workspace."""
    return _run(lambda email: {"result": client.delete_page(email, page_id)})


def get_notion_tools() -> list:
    return [
        notion_search,
        notion_get_block,
        notion_get_page,
        notion_create_page,
        notion_update_page,
        notion_delete_page,
    ]