"""Tests for admin endpoints."""

from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import pytest
import jwt
from datetime import datetime, timezone, timedelta


def create_test_admin_token(clerk_user_id: str = "admin_user_123", admin: bool = True):
    """Create a test JWT token with admin role claim."""
    payload = {
        "sub": clerk_user_id,
        "email": "admin@example.com",
        "public_metadata": {"role": "admin"} if admin else {},
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        "iat": datetime.now(timezone.utc),
    }
    # Use a dummy key for testing - in real tests this would be properly mocked
    return jwt.encode(payload, "test-secret", algorithm="HS256")


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


def test_admin_health_requires_auth(app_no_lifespan):
    """Test that admin endpoints require Authorization header."""
    client = TestClient(app_no_lifespan, raise_server_exceptions=False)
    response = client.get("/admin/health")
    assert response.status_code == 422  # Missing Authorization header


def test_admin_health_with_valid_admin_jwt(app_no_lifespan):
    """Test admin access with valid JWT containing admin role."""
    token = create_test_admin_token(admin=True)
    client = TestClient(app_no_lifespan, raise_server_exceptions=False)

    with patch("app.admin.verify_clerk_token") as mock_verify:
        mock_verify.return_value = {
            "sub": "admin_user_123",
            "email": "admin@example.com",
            "public_metadata": {"role": "admin"},
        }
        response = client.get(
            "/admin/health",
            headers={"Authorization": f"Bearer {token}"},
        )
        # Will fail on DB but auth passed (401/403 would mean auth failed)
        assert response.status_code not in [401, 403]


def test_admin_health_with_non_admin_jwt(app_no_lifespan):
    """Test that non-admin users are rejected."""
    token = create_test_admin_token(admin=False)
    client = TestClient(app_no_lifespan, raise_server_exceptions=False)

    with patch("app.admin.verify_clerk_token") as mock_verify:
        mock_verify.return_value = {
            "sub": "regular_user_123",
            "email": "user@example.com",
            "public_metadata": {},  # No admin role
        }
        response = client.get(
            "/admin/health",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403  # Forbidden - not an admin


def test_admin_command_endpoint(app_no_lifespan):
    """Test admin command endpoint with valid admin JWT."""
    token = create_test_admin_token(admin=True)
    client = TestClient(app_no_lifespan, raise_server_exceptions=False)

    # Mock both the token verification and database lookup
    with (
        patch("app.admin.verify_clerk_token") as mock_verify,
        patch("app.admin.select") as mock_select,
        patch("app.admin.User") as _mock_user_class,
    ):
        mock_verify.return_value = {
            "sub": "admin_user_123",
            "email": "admin@example.com",
            "public_metadata": {"role": "admin"},
        }

        # Create a mock user that will be returned
        mock_user = MagicMock()
        mock_user.id = "user_123"
        mock_user.status = MagicMock()
        mock_user.status.value = "active"

        # Mock the database result chain
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_select.return_value.where.return_value = mock_select

        response = client.post(
            "/admin/command",
            headers={"Authorization": f"Bearer {token}"},
            json={"command": "List all users"},
        )
        # The endpoint may fail on DB but should not fail on auth
        # 401/403 = auth failure, 200/422/500 = other issues
        if response.status_code in [401, 403]:
            pytest.fail(
                "Authentication failed - should have passed with valid admin JWT"
            )

        # If we get here, auth passed (even if other parts failed)
        if response.status_code == 200:
            data = response.json()
            assert data["status"] == "received"
            assert "List all users" in data["message"]
