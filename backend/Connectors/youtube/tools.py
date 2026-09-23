"""LangChain tools exposed by the YouTube connector."""

from __future__ import annotations

import json
from typing import Any, Callable

from langchain_core.tools import tool

from Connectors.context import get_current_user_email
from Connectors.youtube import client


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def _run(action: Callable[[str], Any]) -> str:
    user_email = get_current_user_email()
    if not user_email:
        return "YouTube tool unavailable: no authenticated chatbot user is active."
    if not client.is_connected(user_email):
        return "YouTube is not connected. Ask the user to connect YouTube from the chat header first."
    try:
        return _json(action(user_email))
    except Exception as exc:
        return f"YouTube tool error: {type(exc).__name__}: {exc}"


@tool
def youtube_list_videos(query: str = "", max_results: int = 10) -> str:
    """List videos in the connected YouTube channel. Optional query uses YouTube search syntax."""
    return _run(lambda email: {"videos": client.list_videos(email, query, max_results)})


@tool
def youtube_get_video(video_id: str) -> str:
    """Get a video from the connected YouTube channel by video ID."""
    return _run(lambda email: {"video": client.get_video(email, video_id)})


@tool
def youtube_upload_video(title: str, description: str, video_file_path: str) -> str:
    """Upload a video to the connected YouTube channel."""
    return _run(
        lambda email: {
            "video": client.upload_video(email, title, description, video_file_path)
        }
    )


@tool
def youtube_update_video(video_id: str, title: str = None, description: str = None) -> str:
    """Update an existing video on the connected YouTube channel."""
    return _run(
        lambda email: {
            "video": client.update_video(email, video_id, title, description)
        }
    )


@tool
def youtube_delete_video(video_id: str) -> str:
    """Delete a video from the connected YouTube channel."""
    return _run(lambda email: {"result": client.delete_video(email, video_id)})


def get_youtube_tools() -> list:
    return [
        youtube_list_videos,
        youtube_get_video,
        youtube_upload_video,
        youtube_update_video,
        youtube_delete_video,
    ]
