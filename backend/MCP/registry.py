"""Registry for MCP connector metadata, routes, and chatbot tools."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from importlib import import_module
from types import ModuleType
from typing import Callable

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class McpApp:
    app: str
    name: str
    client_module: str
    tools_module: str
    tools_getter: str
    capabilities: tuple[str, ...]
    connect_label: str = "Connect"

    def client(self) -> ModuleType:
        return import_module(self.client_module)

    def get_tools(self) -> list:
        module = import_module(self.tools_module)
        getter: Callable[[], list] = getattr(module, self.tools_getter)
        return getter()

    def connection_status(self, user_email: str) -> dict:
        try:
            status = self.client().get_connection_status(user_email)
        except Exception as exc:
            logger.warning("MCP status failed for %s: %s", self.app, exc)
            status = {
                "app": self.app,
                "name": self.name,
                "connected": False,
                "configured": False,
                "status": "error",
                "message": f"{self.name} status unavailable: {type(exc).__name__}: {exc}",
            }

        status.setdefault("app", self.app)
        status.setdefault("name", self.name)
        status.setdefault("connected", False)
        status.setdefault("configured", False)
        status.setdefault("status", "connected" if status["connected"] else "not_connected")
        status.setdefault("message", "Connected" if status["connected"] else f"Connect {self.name} to use it in chat.")
        status.setdefault("capabilities", list(self.capabilities))
        status.setdefault("connect_label", self.connect_label)
        if status.get("connected"):
            status["configured"] = True
            status["status"] = "connected"
            status["message"] = "Connected"
        status.setdefault("chat_enabled", bool(status.get("connected")))
        return status


MCP_APPS: dict[str, McpApp] = {
    "gmail": McpApp(
        app="gmail",
        name="Gmail",
        client_module="MCP.gmail.client",
        tools_module="MCP.gmail.tools",
        tools_getter="get_gmail_tools",
        capabilities=(
            "search_messages",
            "read_messages",
            "list_labels",
            "modify_labels",
            "send_email",
        ),
    ),
    "linkedin": McpApp(
        app="linkedin",
        name="LinkedIn",
        client_module="MCP.linkedin.client",
        tools_module="MCP.linkedin.tools",
        tools_getter="get_linkedin_tools",
        capabilities=("get_profile", "get_connections", "share_post"),
    ),
    "google_drive": McpApp(
        app="google_drive",
        name="Google Drive",
        client_module="MCP.google_drive.client",
        tools_module="MCP.google_drive.tools",
        tools_getter="get_google_drive_tools",
        capabilities=("list_files", "get_file", "create_file", "update_file", "delete_file"),
    ),
    "youtube": McpApp(
        app="youtube",
        name="YouTube",
        client_module="MCP.youtube.client",
        tools_module="MCP.youtube.tools",
        tools_getter="get_youtube_tools",
        capabilities=("list_videos", "get_video", "upload_video", "update_video", "delete_video"),
    ),
    "telegram": McpApp(
        app="telegram",
        name="Telegram",
        client_module="MCP.telegram.client",
        tools_module="MCP.telegram.tools",
        tools_getter="get_telegram_tools",
        capabilities=("get_me", "send_message", "get_updates", "get_chat"),
        connect_label="Use configured bot",
    ),
    "notion": McpApp(
        app="notion",
        name="Notion",
        client_module="MCP.notion.client",
        tools_module="MCP.notion.tools",
        tools_getter="get_notion_tools",
        capabilities=("search", "get_block", "get_page", "create_page", "update_page", "delete_page"),
    ),
    "trello": McpApp(
        app="trello",
        name="Trello",
        client_module="MCP.trello.client",
        tools_module="MCP.trello.tools",
        tools_getter="get_trello_tools",
        capabilities=("get_boards", "get_lists", "get_cards", "create_card", "update_card", "delete_card"),
        connect_label="Use configured token",
    ),
}


def get_mcp_app(app: str) -> McpApp | None:
    return MCP_APPS.get(app)


def iter_mcp_apps() -> list[McpApp]:
    return list(MCP_APPS.values())


def get_all_mcp_tools() -> list:
    tools = []
    for app in iter_mcp_apps():
        try:
            tools.extend(app.get_tools())
        except Exception as exc:
            logger.warning("Skipping MCP tools for %s: %s", app.app, exc)
    return tools


def get_mcp_connections(user_email: str) -> list[dict]:
    return [app.connection_status(user_email) for app in iter_mcp_apps()]


def get_mcp_system_message(user_email: str | None) -> str:
    if not user_email:
        return ""

    connections = get_mcp_connections(user_email)
    connected = [item for item in connections if item.get("connected")]
    if not connected:
        app_names = ", ".join(item["name"] for item in connections)
        return (
            f"MCP apps available in the chat UI: {app_names}. None are connected for this user. "
            "If a request needs an app, ask the user to connect it from the MCP menu first."
        )

    lines = []
    for item in connected:
        capabilities = ", ".join(item.get("capabilities") or [])
        lines.append(f"- {item['name']}: {capabilities}")

    return (
        "Connected MCP apps for this user:\n"
        + "\n".join(lines)
        + "\nUse these tools only when the request clearly needs the connected app. "
        "Before write actions such as sending, posting, uploading, creating, updating, or deleting, "
        "make sure the user has explicitly asked for that exact action and supplied the required details."
    )
