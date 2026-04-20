"""Tests for model policy endpoints and ORM logic."""
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import pytest
import jwt
from datetime import datetime, timezone, timedelta
from sqlalchemy import select

from app.models import ModelPolicy


def create_test_admin_token(clerk_user_id: str = "admin_user_123", admin: bool = True):
    """Create a test JWT token with admin role claim."""
    payload = {
        "sub": clerk_user_id,
        "email": "admin@example.com",
        "public_metadata": {"role": "admin"} if admin else {},
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, "test-secret", algorithm="HS256")


@pytest.fixture
def app_with_policy():
    """Create app with model policy routers but without lifespan."""
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    from app.model_policy import model_policy_router, public_policy_router

    app = FastAPI(title="Test Policy API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(model_policy_router)
    app.include_router(public_policy_router)
    return app


@pytest.mark.asyncio
async def test_get_or_create_policy_creates_default(db_session):
    """Test _get_or_create_policy creates a default policy when none exists."""
    from app.model_policy import _get_or_create_policy

    policy = await _get_or_create_policy(db_session, tenant_id="default")
    assert policy is not None
    assert policy.routing_mode == "auto"
    assert policy.default_provider == "featherless"
    assert policy.benchmark_mode is True
    assert "featherless" in policy.allowed_providers


@pytest.mark.asyncio
async def test_get_or_create_policy_returns_existing(db_session):
    """Test _get_or_create_policy returns existing policy without creating duplicate."""
    from app.model_policy import _get_or_create_policy

    first = await _get_or_create_policy(db_session, tenant_id="test-tenant")
    first.routing_mode = "block_premium"
    await db_session.commit()

    second = await _get_or_create_policy(db_session, tenant_id="test-tenant")
    assert second.id == first.id
    assert second.routing_mode == "block_premium"


@pytest.mark.asyncio
async def test_model_policy_orm_fields(db_session):
    """Test ModelPolicy ORM model fields and persistence."""
    policy = ModelPolicy(
        id="policy-orm-001",
        tenant_id="tenant-a",
        routing_mode="force_premium",
        default_provider="openai",
        allowed_providers=["openai", "anthropic"],
        benchmark_mode=False,
    )
    db_session.add(policy)
    await db_session.commit()

    result = await db_session.execute(select(ModelPolicy).where(ModelPolicy.tenant_id == "tenant-a"))
    fetched = result.scalar_one()
    assert fetched.routing_mode == "force_premium"
    assert fetched.default_provider == "openai"
    assert fetched.allowed_providers == ["openai", "anthropic"]
    assert fetched.benchmark_mode is False


def test_public_policy_endpoint(app_with_policy):
    """Test that /v1/model-policy/me returns a default policy via endpoint."""
    client = TestClient(app_with_policy, raise_server_exceptions=False)

    with patch("app.model_policy._get_policy_or_default") as mock_get:
        mock_policy = MagicMock()
        mock_policy.id = "policy-001"
        mock_policy.tenant_id = "default"
        mock_policy.routing_mode = "auto"
        mock_policy.default_provider = "featherless"
        mock_policy.allowed_providers = ["featherless", "deepseek"]
        mock_policy.benchmark_mode = True
        mock_policy.created_at = datetime.now(timezone.utc)
        mock_policy.updated_at = datetime.now(timezone.utc)
        mock_get.return_value = mock_policy

        response = client.get("/v1/model-policy/me")
        assert response.status_code == 200
        data = response.json()
        assert data["routing_mode"] == "auto"
        assert data["default_provider"] == "featherless"
        assert data["benchmark_mode"] is True


def test_admin_policy_requires_auth(app_with_policy):
    """Test that admin endpoints reject requests without valid auth."""
    client = TestClient(app_with_policy, raise_server_exceptions=False)
    response = client.get("/admin/model-policy")
    assert response.status_code in (401, 403, 422)


def test_admin_policy_with_valid_jwt_passes_auth(app_with_policy):
    """Test admin endpoint accepts valid JWT (auth passes; DB may fail later)."""
    token = create_test_admin_token(admin=True)
    client = TestClient(app_with_policy, raise_server_exceptions=False)

    with patch("app.admin.verify_clerk_token") as mock_verify:
        mock_verify.return_value = {
            "sub": "admin_user_123",
            "email": "admin@example.com",
            "public_metadata": {"role": "admin"},
        }
        response = client.get(
            "/admin/model-policy",
            headers={"Authorization": f"Bearer {token}"},
        )
        # Auth should pass (not 401/403); 500 is acceptable because test DB is not wired
        assert response.status_code not in (401, 403)


def test_admin_policy_rejects_non_admin_jwt(app_with_policy):
    """Test non-admin JWT is rejected."""
    token = create_test_admin_token(admin=False)
    client = TestClient(app_with_policy, raise_server_exceptions=False)

    with patch("app.admin.verify_clerk_token") as mock_verify:
        mock_verify.return_value = {
            "sub": "regular_user_123",
            "email": "user@example.com",
            "public_metadata": {},  # No admin role
        }
        response = client.get(
            "/admin/model-policy",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403
