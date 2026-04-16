"""Tests for admin endpoints."""
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import pytest


@pytest.fixture
def app_no_lifespan():
    """Create app without lifespan to avoid DB init in unit tests."""
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    from app.admin import admin_router

    app = FastAPI(title="Test Orchestrator")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(admin_router)
    return app


def test_health_endpoint_no_lifespan():
    """Test /health endpoint without lifespan (no DB needed)."""
    from app.main import app
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_admin_health_requires_key(app_no_lifespan):
    client = TestClient(app_no_lifespan, raise_server_exceptions=False)
    response = client.get("/admin/health")
    assert response.status_code == 422  # Missing header


def test_admin_health_with_valid_key(app_no_lifespan):
    with patch("app.admin.get_settings") as mock_settings:
        mock_settings.return_value = MagicMock(admin_agent_api_key="test-key")
        client = TestClient(app_no_lifespan, raise_server_exceptions=False)
        response = client.get(
            "/admin/health",
            headers={"X-Admin-Key": "test-key"},
        )
        # Will fail on DB but auth passed (500 not 403)
        assert response.status_code in [200, 500]


def test_admin_command_endpoint(app_no_lifespan):
    with patch("app.admin.get_settings") as mock_settings:
        mock_settings.return_value = MagicMock(admin_agent_api_key="test-key")
        client = TestClient(app_no_lifespan, raise_server_exceptions=False)
        response = client.post(
            "/admin/command",
            headers={"X-Admin-Key": "test-key"},
            json={"command": "List all users"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "received"
        assert "List all users" in data["message"]
