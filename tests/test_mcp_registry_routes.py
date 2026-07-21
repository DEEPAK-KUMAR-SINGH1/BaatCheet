import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient


BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from auth_routes import get_current_user  # noqa: E402
from MCP import registry  # noqa: E402
from MCP.routes import router as mcp_router  # noqa: E402
import MCP.routes as mcp_routes  # noqa: E402


def _client():
    app = FastAPI()
    app.dependency_overrides[get_current_user] = lambda: {
        "email": "user@example.com",
        "is_verified": True,
    }
    app.include_router(mcp_router)
    return TestClient(app)


def test_mcp_registry_contains_frontend_apps():
    assert list(registry.MCP_APPS) == [
        "gmail",
        "linkedin",
        "google_drive",
        "youtube",
        "telegram",
        "notion",
        "trello",
    ]
    for app in registry.iter_mcp_apps():
        assert app.name
        assert app.capabilities


def test_connections_route_returns_frontend_ready_payload(monkeypatch):
    def fake_connections(user_email):
        assert user_email == "user@example.com"
        return [
            {"app": "gmail", "name": "Gmail", "connected": True},
            {"app": "notion", "name": "Notion", "connected": False},
        ]

    monkeypatch.setattr(mcp_routes, "get_mcp_connections", fake_connections)

    response = _client().get("/mcp/connections")

    assert response.status_code == 200
    data = response.json()
    assert data["connected_count"] == 1
    assert data["available_count"] == 2
    assert data["connections"][0]["app"] == "gmail"


def test_each_registered_app_exposes_status(monkeypatch):
    for app in registry.iter_mcp_apps():
        client_module = app.client()
        monkeypatch.setattr(
            client_module,
            "get_connection_status",
            lambda user_email, app=app: {
                "app": app.app,
                "name": app.name,
                "connected": False,
                "configured": True,
                "status": "not_connected",
                "capabilities": list(app.capabilities),
            },
        )

    client = _client()
    for app in registry.iter_mcp_apps():
        response = client.get(f"/mcp/{app.app}/status")
        assert response.status_code == 200
        assert response.json()["app"] == app.app


def test_generic_connect_route_preserves_existing_frontend_url(monkeypatch):
    app = registry.MCP_APPS["google_drive"]
    client_module = app.client()
    monkeypatch.setattr(
        client_module,
        "get_auth_url",
        lambda user_email: "https://accounts.example.test/oauth",
    )
    monkeypatch.setattr(
        client_module,
        "get_connection_status",
        lambda user_email: {
            "app": "google_drive",
            "name": "Google Drive",
            "connected": False,
            "configured": True,
            "status": "not_connected",
            "capabilities": list(app.capabilities),
        },
    )

    response = _client().post("/mcp/google_drive/connect", json={})

    assert response.status_code == 200
    data = response.json()
    assert data["app"] == "google_drive"
    assert data["auth_url"] == "https://accounts.example.test/oauth"
    assert data["connection"]["capabilities"] == list(app.capabilities)


def test_mcp_system_message_lists_connected_capabilities(monkeypatch):
    monkeypatch.setattr(
        registry,
        "get_mcp_connections",
        lambda user_email: [
            {
                "app": "gmail",
                "name": "Gmail",
                "connected": True,
                "capabilities": ["search_messages", "send_email"],
            }
        ],
    )

    message = registry.get_mcp_system_message("user@example.com")

    assert "Gmail" in message
    assert "search_messages" in message
    assert "explicitly asked" in message
