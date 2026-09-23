"""LangChain tools exposed by the Gmail connector."""

from __future__ import annotations

import json
from typing import Any, Callable

from langchain_core.tools import tool

from Connectors.context import get_current_user_email
from Connectors.gmail import client


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def _run(action: Callable[[str], Any]) -> str:
    user_email = get_current_user_email()
    if not user_email:
        return "Gmail tool unavailable: no authenticated chatbot user is active."
    if not client.is_connected(user_email):
        return "Gmail is not connected. Ask the user to connect Gmail from the chat header first."
    try:
        return _json(action(user_email))
    except Exception as exc:
        return f"Gmail tool error: {type(exc).__name__}: {exc}"


@tool
def gmail_search_messages(query: str = "", max_results: int = 5) -> str:
    """Search the connected Gmail mailbox. Query can use Gmail search syntax such as from:, to:, subject:, newer_than:, has:attachment, or plain text."""
    return _run(lambda email: {"messages": client.search_messages(email, query, max_results)})


@tool
def gmail_read_message(message_id: str) -> str:
    """Read a Gmail message by message id returned from gmail_search_messages."""
    return _run(lambda email: {"message": client.read_message(email, message_id)})


@tool
def gmail_list_labels() -> str:
    """List labels available in the connected Gmail mailbox."""
    return _run(lambda email: {"labels": client.list_labels(email)})


@tool
def gmail_mark_message_read(message_id: str) -> str:
    """Mark a Gmail message as read by removing the UNREAD label."""
    return _run(
        lambda email: {
            "message": client.modify_message(
                email,
                message_id,
                remove_label_ids=["UNREAD"],
            )
        }
    )


@tool
def gmail_archive_message(message_id: str) -> str:
    """Archive a Gmail message by removing it from the inbox."""
    return _run(
        lambda email: {
            "message": client.modify_message(
                email,
                message_id,
                remove_label_ids=["INBOX"],
            )
        }
    )


@tool
def gmail_send_email(
    to: str,
    subject: str,
    body: str,
    cc: str = "",
    bcc: str = "",
    confirm_send: bool = False,
) -> str:
    """Send an email from the connected Gmail account only after the user explicitly asks to send it now and recipient, subject, and body are complete."""
    if not confirm_send:
        return (
            "Gmail send blocked: ask the user to confirm the recipient, subject, "
            "body, and that the email should be sent now."
        )
    return _run(
        lambda email: {
            "sent": client.send_email(email, to, subject, body, cc=cc, bcc=bcc)
        }
    )


def get_gmail_tools() -> list:
    return [
        gmail_search_messages,
        gmail_read_message,
        gmail_list_labels,
        gmail_mark_message_read,
        gmail_archive_message,
        gmail_send_email,
    ]
