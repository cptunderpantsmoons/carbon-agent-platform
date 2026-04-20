"""Tests for auth routes - Clerk-based API key retrieval."""

from datetime import datetime, timedelta, timezone
import json

import jwt
import pytest
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import rsa
from httpx import ASGITransport, AsyncClient

from app.auth_routes import get_clerk_jwks_for_verification
from app.database import get_session
from app.main import app
from app.models import User, UserStatus


def _generate_rsa_keypair() -> tuple[rsa.RSAPrivateKey, dict]:
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend(),
    )
    public_jwk = json.loads(
        jwt.algorithms.RSAAlgorithm.to_jwk(private_key.public_key())
    )
    public_jwk.update({"kid": "test-kid", "alg": "RS256", "use": "sig"})
    return private_key, {"keys": [public_jwk]}


def _make_clerk_token(
    private_key: rsa.RSAPrivateKey,
    clerk_user_id: str,
    *,
    email: str = "test@example.com",
    kid: str = "test-kid",
    exp_delta: timedelta = timedelta(hours=1),
    nbf_delta: timedelta = timedelta(seconds=-1),
) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": clerk_user_id,
        "email": email,
        "iat": now,
        "exp": now + exp_delta,
        "nbf": now + nbf_delta,
    }
    return jwt.encode(payload, private_key, algorithm="RS256", headers={"kid": kid})


@pytest.fixture
def signing_material():
    return _generate_rsa_keypair()


@pytest.fixture
async def auth_client(db_session, signing_material):
    _, jwks = signing_material

    async def override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_clerk_jwks_for_verification] = lambda: jwks

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture
async def seed_clerk_user(db_session):
    user = User(
        id="clerk-user-001",
        email="clerk@test.com",
        display_name="Clerk Test User",
        api_key="sk-clerk-test-key-abc123",
        status=UserStatus.ACTIVE,
        clerk_user_id="user_clerk_123",
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest.fixture
async def seed_suspended_user(db_session):
    user = User(
        id="suspended-clerk-001",
        email="suspended@test.com",
        display_name="Suspended User",
        api_key="sk-suspended-key",
        status=UserStatus.SUSPENDED,
        clerk_user_id="user_clerk_suspended",
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest.mark.asyncio
async def test_get_api_key_success(auth_client, seed_clerk_user, signing_material):
    private_key, _ = signing_material
    token = _make_clerk_token(private_key, "user_clerk_123", email="clerk@test.com")
    response = await auth_client.get(
        "/api/v1/auth/get-api-key",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json() == {
        "api_key": "sk-clerk-test-key-abc123",
        "user_id": "clerk-user-001",
    }


@pytest.mark.asyncio
async def test_get_api_key_missing_auth_header(auth_client):
    response = await auth_client.get("/api/v1/auth/get-api-key")
    assert response.status_code == 401
    assert response.json()["detail"] == "Missing or invalid Authorization header"


@pytest.mark.asyncio
async def test_get_api_key_rejects_tampered_signature(
    auth_client, seed_clerk_user, signing_material
):
    private_key, _ = signing_material
    valid_token = _make_clerk_token(
        private_key, "user_clerk_123", email="clerk@test.com"
    )
    header_part, payload_part, signature_part = valid_token.split(".")
    mid = len(signature_part) // 2
    flipped = "A" if signature_part[mid] != "A" else "B"
    tampered_signature = f"{signature_part[:mid]}{flipped}{signature_part[mid + 1 :]}"
    tampered_token = ".".join([header_part, payload_part, tampered_signature])
    response = await auth_client.get(
        "/api/v1/auth/get-api-key",
        headers={"Authorization": f"Bearer {tampered_token}"},
    )
    assert response.status_code == 401
    assert "Invalid token" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_api_key_rejects_expired_token(
    auth_client, seed_clerk_user, signing_material
):
    private_key, _ = signing_material
    expired_token = _make_clerk_token(
        private_key,
        "user_clerk_123",
        email="clerk@test.com",
        exp_delta=timedelta(minutes=-1),
    )
    response = await auth_client.get(
        "/api/v1/auth/get-api-key",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert response.status_code == 401
    assert "expired" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_api_key_rejects_nbf_in_future(
    auth_client, seed_clerk_user, signing_material
):
    private_key, _ = signing_material
    nbf_future_token = _make_clerk_token(
        private_key,
        "user_clerk_123",
        email="clerk@test.com",
        nbf_delta=timedelta(minutes=10),
    )
    response = await auth_client.get(
        "/api/v1/auth/get-api-key",
        headers={"Authorization": f"Bearer {nbf_future_token}"},
    )
    assert response.status_code == 401
    assert "Invalid token" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_api_key_rejects_unknown_kid(
    auth_client, seed_clerk_user, signing_material
):
    private_key, _ = signing_material
    unknown_kid_token = _make_clerk_token(
        private_key,
        "user_clerk_123",
        email="clerk@test.com",
        kid="unknown-kid",
    )
    response = await auth_client.get(
        "/api/v1/auth/get-api-key",
        headers={"Authorization": f"Bearer {unknown_kid_token}"},
    )
    assert response.status_code == 401
    assert "Invalid token" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_api_key_suspended_user_returns_403(
    auth_client,
    seed_suspended_user,
    signing_material,
):
    private_key, _ = signing_material
    token = _make_clerk_token(
        private_key,
        "user_clerk_suspended",
        email="suspended@test.com",
    )
    response = await auth_client.get(
        "/api/v1/auth/get-api-key",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "User account is not active"


@pytest.mark.asyncio
async def test_get_api_key_user_not_found(auth_client, signing_material):
    private_key, _ = signing_material
    token = _make_clerk_token(private_key, "user_nonexistent", email="nobody@test.com")
    response = await auth_client.get(
        "/api/v1/auth/get-api-key",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_api_key_email_fallback(auth_client, db_session, signing_material):
    user = User(
        id="email-user-001",
        email="fallback@test.com",
        display_name="Fallback User",
        api_key="sk-fallback-key",
        status=UserStatus.ACTIVE,
        clerk_user_id=None,
    )
    db_session.add(user)
    await db_session.commit()

    private_key, _ = signing_material
    token = _make_clerk_token(
        private_key, "user_new_clerk_id", email="fallback@test.com"
    )

    response = await auth_client.get(
        "/api/v1/auth/get-api-key",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json() == {
        "api_key": "sk-fallback-key",
        "user_id": "email-user-001",
    }

    await db_session.refresh(user)
    assert user.clerk_user_id == "user_new_clerk_id"


@pytest.mark.asyncio
async def test_clerk_status_endpoint():
    response_transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=response_transport, base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/auth/clerk-status")
    assert response.status_code == 200
    payload = response.json()
    assert "clerk_enabled" in payload
    assert payload["service"] == "orchestrator"
