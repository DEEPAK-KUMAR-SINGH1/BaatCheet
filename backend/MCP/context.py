"""Request-local MCP context for chatbot tool calls."""

from __future__ import annotations

from contextvars import ContextVar, Token

_current_user_email: ContextVar[str | None] = ContextVar(
    "mcp_current_user_email",
    default=None,
)


def get_current_user_email() -> str | None:
    return _current_user_email.get()


def set_current_user_email(user_email: str | None) -> Token:
    return _current_user_email.set(user_email)


def reset_current_user_email(token: Token) -> None:
    _current_user_email.reset(token)
