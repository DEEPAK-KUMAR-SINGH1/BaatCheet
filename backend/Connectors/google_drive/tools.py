"""LangChain tools exposed by the Google Drive connector."""

from __future__ import annotations

import json
from typing import Any, Callable

from langchain_core.tools import tool

from Connectors.context import get_current_user_email
from Connectors.google_drive import client


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def _run(action: Callable[[str], Any]) -> str:
    user_email = get_current_user_email()
    if not user_email:
        return "Google Drive tool unavailable: no authenticated chatbot user is active."
    if not client.is_connected(user_email):
        return "Google Drive is not connected. Ask the user to connect Google Drive from the chat header first."
    try:
        return _json(action(user_email))
    except Exception as exc:
        return f"Google Drive tool error: {type(exc).__name__}: {exc}"


@tool
def gdrive_list_files(query: str = "", page_size: int = 10) -> str:
    """List files in the connected Google Drive. Optional query uses Google Drive search syntax."""
    return _run(lambda email: {"files": client.list_files(email, query, page_size)})


@tool
def gdrive_get_file(file_id: str) -> str:
    """Get a file from the connected Google Drive by file ID."""
    return _run(lambda email: {"file": client.get_file(email, file_id)})


@tool
def gdrive_create_file(name: str, content: str, mime_type: str = "application/octet-stream") -> str:
    """Create a new file in the connected Google Drive."""
    return _run(
        lambda email: {
            "file": client.create_file(email, name, content.encode('utf-8'), mime_type)
        }
    )


@tool
def gdrive_update_file(file_id: str, content: str = None, name: str = None) -> str:
    """Update an existing file in the connected Google Drive."""
    return _run(
        lambda email: {
            "file": client.update_file(email, file_id,
                                      content.encode('utf-8') if content else None,
                                      name)
        }
    )


@tool
def gdrive_delete_file(file_id: str) -> str:
    """Delete a file from the connected Google Drive."""
    return _run(lambda email: {"result": client.delete_file(email, file_id)})


def get_google_drive_tools() -> list:
    return [
        gdrive_list_files,
        gdrive_get_file,
        gdrive_create_file,
        gdrive_update_file,
        gdrive_delete_file,
    ]
