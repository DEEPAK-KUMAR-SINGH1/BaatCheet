"""FastAPI routes for MCP app connections."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from auth_routes import get_current_user
from config import FRONTEND_URL
from MCP import get_mcp_app, get_mcp_connections, iter_mcp_apps

router = APIRouter(prefix="/mcp", tags=["mcp"])


class ManualTokenRequest(BaseModel):
    token: str
    extra: dict[str, Any] | None = None


def _frontend_redirect(app: str, status: str, detail: str = "") -> RedirectResponse:
    params = {"mcp": app, "status": status}
    if detail:
        params["detail"] = detail[:180]
    separator = "&" if "?" in FRONTEND_URL else "?"
    return RedirectResponse(f"{FRONTEND_URL}{separator}{urlencode(params)}")


def _mcp_app_or_404(app: str):
    mcp_app = get_mcp_app(app)
    if not mcp_app:
        raise HTTPException(status_code=404, detail=f"Unknown MCP app: {app}")
    return mcp_app


def _service_unavailable(exc: Exception) -> HTTPException:
    return HTTPException(status_code=503, detail=str(exc))


@router.get("/connections")
def list_connections(current_user=Depends(get_current_user)):
    connections = get_mcp_connections(current_user["email"])
    return {
        "connections": connections,
        "connected_count": sum(1 for item in connections if item.get("connected")),
        "available_count": len(connections),
    }


@router.get("/apps")
def list_apps(current_user=Depends(get_current_user)):
    statuses = {
        item["app"]: item
        for item in get_mcp_connections(current_user["email"])
    }
    return {
        "apps": [
            {
                "app": app.app,
                "name": app.name,
                "capabilities": list(app.capabilities),
                "connect_label": app.connect_label,
                "connection": statuses.get(app.app, {}),
            }
            for app in iter_mcp_apps()
        ]
    }


@router.get("/tools")
def list_tools(current_user=Depends(get_current_user)):
    tools = []
    for app in iter_mcp_apps():
        try:
            tools.extend(
                {
                    "app": app.app,
                    "name": tool.name,
                    "description": getattr(tool, "description", "") or "",
                }
                for tool in app.get_tools()
            )
        except Exception as exc:
            tools.append(
                {
                    "app": app.app,
                    "name": "",
                    "description": f"{app.name} tools unavailable: {exc}",
                }
            )
    return {"tools": tools}


@router.get("/{app}/status")
def app_status(app: str, current_user=Depends(get_current_user)):
    return _mcp_app_or_404(app).connection_status(current_user["email"])


@router.post("/{app}/connect")
def app_connect(app: str, current_user=Depends(get_current_user)):
    mcp_app = _mcp_app_or_404(app)
    client = mcp_app.client()
    try:
        auth_url = client.get_auth_url(current_user["email"])
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        raise _service_unavailable(exc) from exc

    return {
        "app": mcp_app.app,
        "name": mcp_app.name,
        "auth_url": auth_url,
        "connection": mcp_app.connection_status(current_user["email"]),
    }


@router.post("/{app}/token")
def app_connect_with_token(
    app: str,
    req: ManualTokenRequest,
    current_user=Depends(get_current_user),
):
    mcp_app = _mcp_app_or_404(app)
    client = mcp_app.client()
    if not hasattr(client, "save_token"):
        raise HTTPException(status_code=400, detail=f"{mcp_app.name} does not support token connection.")

    try:
        client.save_token(current_user["email"], req.token)
    except Exception as exc:
        raise _service_unavailable(exc) from exc
    return mcp_app.connection_status(current_user["email"])


@router.get("/{app}/callback")
def app_callback(
    app: str,
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
):
    mcp_app = _mcp_app_or_404(app)
    client = mcp_app.client()
    if error:
        return _frontend_redirect(app, "failed", error)
    if not code or not state:
        return _frontend_redirect(app, "failed", "Missing OAuth code or state.")

    try:
        user_email = client.parse_oauth_state(state)
        client.exchange_code(user_email, code, state)
    except Exception as exc:
        return _frontend_redirect(app, "failed", str(exc))

    return _frontend_redirect(app, "connected")


@router.delete("/{app}")
def app_disconnect(app: str, current_user=Depends(get_current_user)):
    mcp_app = _mcp_app_or_404(app)
    client = mcp_app.client()
    try:
        client.delete_token(current_user["email"])
    except Exception as exc:
        raise _service_unavailable(exc) from exc
    return mcp_app.connection_status(current_user["email"])


@router.post("/{app}/disconnect")
def app_disconnect_post(app: str, current_user=Depends(get_current_user)):
    return app_disconnect(app, current_user)
