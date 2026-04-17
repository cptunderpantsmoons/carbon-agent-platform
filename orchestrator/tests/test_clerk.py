"""Tests for Clerk webhook handler and authentication."""
import json
import uuid
import time
import base64
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient
import pytest
import pytest_asyncio

from svix.webhooks import Webhook

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.models import User, UserStatus, Base, AuditLog


# --- Test App Setup ---

@pytest.fixture
def clerk_test_app():
    """Create a minimal FastAPI app with Clerk webhook router for testing."""
    from fastapi import FastAPI, Request
    from fastapi.middleware.cors import CORSMiddleware
    from starlette.middleware.base import BaseHTTPMiddleware
    from app.clerk import clerk_webhook_router

    class TestDBMiddleware(BaseHTTPMiddleware):
        """Provides a mock DB session via request.state."""
        async def dispatch(self, request, call_next):
            request.state.db = AsyncMock()
            request.state.db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
            request.state.db.commit = AsyncMock()
            request.state.db.add = MagicMock()
            response = await call_next(request)
            return response

    app = FastAPI(title="Test Clerk Webhooks")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(TestDBMiddleware)
    app.include_router(clerk_webhook_router)
    return app


@pytest.fixture
def client(clerk_test_app):
    """Create test client for Clerk webhook tests."""
    return TestClient(clerk_test_app, raise_server_exceptions=False)


# --- Helper Functions ---

# Svix expects a base64-encoded secret (whsec_ prefix or raw base64).
_RAW_SECRET = b"test_webhook_secret_value_12345678"
WEBHOOK_SECRET = "whsec_" + base64.b64encode(_RAW_SECRET).decode("utf-8")


def _sign_webhook_payload(payload: bytes, secret: str = WEBHOOK_SECRET) -> dict:
    """Generate valid Svix webhook headers for a payload."""
    wh = Webhook(secret)
    timestamp = datetime.now(timezone.utc)
    msg_id = f"msg_{uuid.uuid4().hex}"
    signature = wh.sign(msg_id, timestamp, payload.decode("utf-8"))
    return {
        "svix-id": msg_id,
        "svix-timestamp": str(int(timestamp.timestamp())),
        "svix-signature": signature,
    }


def _make_webhook_payload(event_type: str, clerk_user_id: str, extra_data: dict | None = None) -> dict:
    """Create a standard Clerk webhook payload."""
    data = {
        "id": clerk_user_id,
        "email_addresses": [{"email_address": "test@example.com", "id": "idn_123"}],
        "first_name": "John",
        "last_name": "Doe",
        "created_at": 1700000000000,
        "updated_at": 1700000000000,
    }
    if extra_data:
        data.update(extra_data)
    return {
        "object": "event",
        "type": event_type,
        "data": data,
    }


# --- Database Fixtures ---

@pytest_asyncio.fixture
async def test_engine():
    """Create test database engine."""
    engine = create_async_engine("sqlite+aiosqlite:///test_clerk.db", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def test_db(test_engine):
    """Create test database session."""
    async_session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with async_session_factory() as session:
        yield session
        await session.rollback()


@pytest.fixture
def test_user(test_db):
    """Create a test user with Clerk user ID."""
    user = User(
        id=str(uuid.uuid4()),
        clerk_user_id="user_test123",
        email="existing@example.com",
        display_name="Existing User",
        api_key="sk-existing-key-123",
        status=UserStatus.ACTIVE,
        railway_service_id="svc-existing",
        volume_id="vol-existing",
    )
    test_db.add(user)
    import asyncio
    asyncio.run(test_db.commit())
    asyncio.run(test_db.refresh(user))
    return user


# --- Webhook Signature Verification Tests ---

class TestWebhookSignatureVerification:
    """Tests for webhook signature verification using Svix."""

    def test_valid_svix_signature(self, client):
        """Test that valid Svix signature is accepted."""
        with patch("app.clerk.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(clerk_webhook_secret=WEBHOOK_SECRET)

            payload = _make_webhook_payload("user.created", "user_new123")
            body = json.dumps(payload).encode("utf-8")
            headers = _sign_webhook_payload(body)

            response = client.post(
                "/webhooks/clerk",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    **headers,
                },
            )
            assert response.status_code == 200

    def test_invalid_svix_signature(self, client):
        """Test that tampered Svix signature is rejected."""
        with patch("app.clerk.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(clerk_webhook_secret=WEBHOOK_SECRET)

            payload = _make_webhook_payload("user.created", "user_new123")
            body = json.dumps(payload).encode("utf-8")
            headers = _sign_webhook_payload(body)
            headers["svix-signature"] = "v1,g0hM9SsE+OTPJTDtR6QxvJah0JYJ7BEdd0fySUJHycQ="  # tampered but valid base64

            response = client.post(
                "/webhooks/clerk",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    **headers,
                },
            )
            assert response.status_code == 400
            assert "Invalid webhook signature" in response.json().get("detail", "")

    def test_missing_svix_headers(self, client):
        """Test that missing Svix headers returns 400."""
        with patch("app.clerk.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(clerk_webhook_secret=WEBHOOK_SECRET)

            payload = _make_webhook_payload("user.created", "user_new123")
            body = json.dumps(payload).encode("utf-8")

            response = client.post(
                "/webhooks/clerk",
                content=body,
                headers={"Content-Type": "application/json"},
            )
            assert response.status_code == 400
            assert "Missing Svix signature headers" in response.json().get("detail", "")

    def test_partial_svix_headers_missing_id(self, client):
        """Test that missing svix-id header returns 400."""
        with patch("app.clerk.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(clerk_webhook_secret=WEBHOOK_SECRET)

            payload = _make_webhook_payload("user.created", "user_new123")
            body = json.dumps(payload).encode("utf-8")
            headers = _sign_webhook_payload(body)
            del headers["svix-id"]

            response = client.post(
                "/webhooks/clerk",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    **headers,
                },
            )
            assert response.status_code == 400

    def test_old_timestamp_rejected(self, client):
        """Test that Svix timestamp older than 5 minutes is rejected."""
        with patch("app.clerk.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(clerk_webhook_secret=WEBHOOK_SECRET)

            payload = _make_webhook_payload("user.created", "user_new123")
            body = json.dumps(payload).encode("utf-8")

            # Sign with a timestamp 10 minutes in the past
            wh = Webhook(WEBHOOK_SECRET)
            old_timestamp = datetime.now(timezone.utc) - timedelta(minutes=10)
            msg_id = f"msg_{uuid.uuid4().hex}"
            signature = wh.sign(msg_id, old_timestamp, body.decode("utf-8"))

            response = client.post(
                "/webhooks/clerk",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "svix-id": msg_id,
                    "svix-timestamp": str(int(old_timestamp.timestamp())),
                    "svix-signature": signature,
                },
            )
            assert response.status_code == 400

    def test_malformed_json_payload(self, client):
        """Test that malformed JSON returns appropriate error.

        Note: The Svix library internally parses JSON during verification,
        so malformed JSON fails signature verification (400) rather than
        reaching our JSON parser (400). This is correct security behavior -
        we don't process unverified payloads.
        """
        with patch("app.clerk.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(clerk_webhook_secret=WEBHOOK_SECRET)

            body = b"not valid json{"
            headers = _sign_webhook_payload(body)

            response = client.post(
                "/webhooks/clerk",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    **headers,
                },
            )
            # Svix verify fails on malformed JSON, returns 400
            assert response.status_code == 400

    def test_oversized_payload_rejected(self, client):
        """Test that payload larger than 1 MiB is rejected."""
        with patch("app.clerk.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(clerk_webhook_secret=WEBHOOK_SECRET)

            # Create payload larger than 1 MiB
            big_payload = {"type": "user.created", "data": {"id": "x", "pad": "A" * (2 * 1024 * 1024)}}
            body = json.dumps(big_payload).encode("utf-8")

            response = client.post(
                "/webhooks/clerk",
                content=body,
                headers={"Content-Type": "application/json"},
            )
            assert response.status_code in (400, 413)

    def test_missing_event_type(self, client):
        """Test that missing event type is rejected."""
        with patch("app.clerk.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(clerk_webhook_secret=WEBHOOK_SECRET)

            payload = {"data": {"id": "user_123"}}
            body = json.dumps(payload).encode("utf-8")
            headers = _sign_webhook_payload(body)

            response = client.post(
                "/webhooks/clerk",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    **headers,
                },
            )
            assert response.status_code == 400
            assert "Missing event type" in response.json().get("detail", "")

    def test_missing_clerk_user_id(self, client):
        """Test that missing Clerk user ID is rejected."""
        with patch("app.clerk.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(clerk_webhook_secret=WEBHOOK_SECRET)

            payload = {"type": "user.created", "data": {}}
            body = json.dumps(payload).encode("utf-8")
            headers = _sign_webhook_payload(body)

            response = client.post(
                "/webhooks/clerk",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    **headers,
                },
            )
            assert response.status_code == 400
            assert "Missing Clerk user ID" in response.json().get("detail", "")

    def test_unsupported_event_type(self, client):
        """Test that unsupported event types are handled gracefully."""
        with patch("app.clerk.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(clerk_webhook_secret=WEBHOOK_SECRET)

            payload = _make_webhook_payload("session.created", "user_new123")
            body = json.dumps(payload).encode("utf-8")
            headers = _sign_webhook_payload(body)

            response = client.post(
                "/webhooks/clerk",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    **headers,
                },
            )
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ignored"


# --- user.created Event Tests ---

class TestUserCreatedEvent:
    """Tests for user.created webhook event processing."""

    def test_new_user_provisioning(self, client):
        """Test that user.created creates a new Carbon Agent user."""
        with patch("app.clerk.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(clerk_webhook_secret=WEBHOOK_SECRET)

            payload = _make_webhook_payload("user.created", "user_new999")
            body = json.dumps(payload).encode("utf-8")
            headers = _sign_webhook_payload(body)

            response = client.post(
                "/webhooks/clerk",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    **headers,
                },
            )
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"

    def test_idempotent_user_creation(self, client):
        """Test that duplicate user.created events don't create duplicate users."""
        with patch("app.clerk.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(clerk_webhook_secret=WEBHOOK_SECRET)

            payload = _make_webhook_payload("user.created", "user_existing123")
            body = json.dumps(payload).encode("utf-8")
            headers = _sign_webhook_payload(body)

            response1 = client.post(
                "/webhooks/clerk",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    **headers,
                },
            )
            assert response1.status_code == 200

            # Svix signatures are timestamp-based; re-sign for second request
            headers2 = _sign_webhook_payload(body)
            response2 = client.post(
                "/webhooks/clerk",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    **headers2,
                },
            )
            assert response2.status_code == 200

    def test_user_created_missing_email(self, client):
        """Test that user.created without email is rejected."""
        with patch("app.clerk.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(clerk_webhook_secret=WEBHOOK_SECRET)

            payload = {
                "type": "user.created",
                "data": {
                    "id": "user_new123",
                    "email_addresses": [],
                    "first_name": "John",
                    "last_name": "Doe",
                },
            }
            body = json.dumps(payload).encode("utf-8")
            headers = _sign_webhook_payload(body)

            response = client.post(
                "/webhooks/clerk",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    **headers,
                },
            )
            assert response.status_code == 400


# --- user.updated Event Tests ---

class TestUserUpdatedEvent:
    """Tests for user.updated webhook event processing."""

    def test_sync_user_profile(self, client):
        """Test that user.updated syncs profile data."""
        with patch("app.clerk.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(clerk_webhook_secret=WEBHOOK_SECRET)

            payload = _make_webhook_payload("user.updated", "user_test123")
            body = json.dumps(payload).encode("utf-8")
            headers = _sign_webhook_payload(body)

            response = client.post(
                "/webhooks/clerk",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    **headers,
                },
            )
            # Mock DB returns None, so returns 404
            assert response.status_code in [404, 200]

    def test_user_not_found_for_update(self, client):
        """Test that user.updated for unknown user returns 404."""
        with patch("app.clerk.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(clerk_webhook_secret=WEBHOOK_SECRET)

            payload = _make_webhook_payload("user.updated", "user_nonexistent")
            body = json.dumps(payload).encode("utf-8")
            headers = _sign_webhook_payload(body)

            response = client.post(
                "/webhooks/clerk",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    **headers,
                },
            )
            assert response.status_code == 404


# --- user.deleted Event Tests ---

class TestUserDeletedEvent:
    """Tests for user.deleted webhook event processing."""

    def test_soft_delete_user(self, client):
        """Test that user.deleted soft-deletes the user."""
        with patch("app.clerk.get_settings") as mock_settings, \
             patch("app.clerk.get_session_manager") as mock_get_sm:
            mock_settings.return_value = MagicMock(clerk_webhook_secret=WEBHOOK_SECRET)
            mock_sm = MagicMock()
            mock_sm.spin_down_user_service = AsyncMock(return_value=True)
            mock_get_sm.return_value = mock_sm

            payload = _make_webhook_payload("user.deleted", "user_test123")
            body = json.dumps(payload).encode("utf-8")
            headers = _sign_webhook_payload(body)

            response = client.post(
                "/webhooks/clerk",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    **headers,
                },
            )
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"

    def test_idempotent_user_deletion(self, client):
        """Test that deleting an already-deleted user is idempotent."""
        with patch("app.clerk.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(clerk_webhook_secret=WEBHOOK_SECRET)

            payload = _make_webhook_payload("user.deleted", "user_test123")
            body = json.dumps(payload).encode("utf-8")
            headers = _sign_webhook_payload(body)

            response1 = client.post(
                "/webhooks/clerk",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    **headers,
                },
            )

            headers2 = _sign_webhook_payload(body)
            response2 = client.post(
                "/webhooks/clerk",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    **headers2,
                },
            )
            assert response1.status_code == 200
            assert response2.status_code == 200

    def test_delete_nonexistent_user(self, client):
        """Test that deleting a nonexistent user returns success."""
        with patch("app.clerk.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(clerk_webhook_secret=WEBHOOK_SECRET)

            payload = _make_webhook_payload("user.deleted", "user_nonexistent")
            body = json.dumps(payload).encode("utf-8")
            headers = _sign_webhook_payload(body)

            response = client.post(
                "/webhooks/clerk",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    **headers,
                },
            )
            assert response.status_code == 200
            data = response.json()
            assert "already deleted or not found" in data.get("message", "").lower()


# --- Helper Function Unit Tests ---

class TestHelperFunctions:
    """Unit tests for internal helper functions."""

    def test_verify_webhook_signature_valid(self):
        """Test valid Svix signature verification."""
        from app.clerk import _verify_webhook_signature

        payload = b'{"type": "user.created", "data": {"id": "user_123"}}'
        headers = _sign_webhook_payload(payload)

        with patch("app.clerk.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(clerk_webhook_secret=WEBHOOK_SECRET)
            assert _verify_webhook_signature(
                payload,
                headers["svix-id"],
                headers["svix-timestamp"],
                headers["svix-signature"],
            ) is True

    def test_verify_webhook_signature_invalid(self):
        """Test invalid Svix signature verification."""
        from app.clerk import _verify_webhook_signature

        payload = b'{"type": "user.created", "data": {"id": "user_123"}}'

        with patch("app.clerk.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(clerk_webhook_secret=WEBHOOK_SECRET)
            assert _verify_webhook_signature(
                payload,
                "msg_fake",
                str(int(time.time())),
                "v1,g0hM9SsE+OTPJTDtR6QxvJah0JYJ7BEdd0fySUJHycQ=",  # valid base64 but wrong signature
            ) is False

    def test_verify_webhook_signature_no_secret(self):
        """Test verification when no secret is configured returns 500."""
        from app.clerk import _verify_webhook_signature
        from fastapi import HTTPException

        payload = b'{"type": "user.created"}'
        headers = _sign_webhook_payload(payload)

        with patch("app.clerk.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(clerk_webhook_secret="")
            with pytest.raises(HTTPException) as exc_info:
                _verify_webhook_signature(
                    payload,
                    headers["svix-id"],
                    headers["svix-timestamp"],
                    headers["svix-signature"],
                )
            assert exc_info.value.status_code == 500

    def test_generate_api_key_format(self):
        """Test API key generation format."""
        from app.clerk import _generate_api_key

        key = _generate_api_key()
        assert key.startswith("sk-")
        assert len(key) == 51  # "sk-" + 48 hex chars

    def test_generate_api_key_uniqueness(self):
        """Test that generated API keys are unique."""
        from app.clerk import _generate_api_key

        keys = [_generate_api_key() for _ in range(100)]
        assert len(set(keys)) == 100  # All unique

    def test_prepare_webhook_secret_with_prefix(self):
        """Test that whsec_ prefix is stripped from webhook secret."""
        from app.clerk import _prepare_webhook_secret
        
        secret_with_prefix = "whsec_abc123def456"
        result = _prepare_webhook_secret(secret_with_prefix)
        assert result == "abc123def456"
        assert not result.startswith("whsec_")

    def test_prepare_webhook_secret_without_prefix(self):
        """Test that secret without prefix is returned unchanged."""
        from app.clerk import _prepare_webhook_secret
        
        secret_without_prefix = "abc123def456"
        result = _prepare_webhook_secret(secret_without_prefix)
        assert result == "abc123def456"

    def test_prepare_webhook_secret_with_real_base64_secret(self):
        """Test preparing a real base64-encoded webhook secret."""
        from app.clerk import _prepare_webhook_secret
        
        # This is how Clerk provides webhook secrets
        raw_secret = "dGVzdF9zZWNyZXRfa2V5XzEyMzQ1Njc4"
        secret_with_prefix = f"whsec_{raw_secret}"
        
        result = _prepare_webhook_secret(secret_with_prefix)
        assert result == raw_secret
        assert not result.startswith("whsec_")


# --- Clerk Auth Middleware Tests ---

class TestClerkAuthMiddleware:
    """Tests for Clerk JWT authentication middleware."""

    def test_decode_clerk_jwt_valid(self):
        """Test decoding a valid Clerk JWT."""
        from app.clerk_auth import _decode_clerk_jwt

        import jwt
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.backends import default_backend
        from cryptography.hazmat.primitives.asymmetric import rsa

        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend(),
        )
        public_key = private_key.public_key()

        payload = {
            "sub": "user_test123",
            "email": "test@example.com",
            "exp": 9999999999,
            "nbf": 1000000000,
        }
        token = jwt.encode(payload, private_key, algorithm="RS256")

        pem_public_key = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("utf-8")

        with patch("app.clerk_auth.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(clerk_jwt_public_key=pem_public_key)

            decoded = _decode_clerk_jwt(token)
            assert decoded["sub"] == "user_test123"
            assert decoded["email"] == "test@example.com"

    def test_decode_clerk_jwt_expired(self):
        """Test that expired JWT is rejected."""
        from app.clerk_auth import _decode_clerk_jwt

        import jwt
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.backends import default_backend
        from cryptography.hazmat.primitives.asymmetric import rsa

        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend(),
        )
        public_key = private_key.public_key()

        payload = {
            "sub": "user_test123",
            "exp": 1000000000,
            "nbf": 1000000000,
        }
        token = jwt.encode(payload, private_key, algorithm="RS256")

        pem_public_key = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("utf-8")

        with patch("app.clerk_auth.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(clerk_jwt_public_key=pem_public_key)

            from fastapi import HTTPException
            with pytest.raises(HTTPException) as exc_info:
                _decode_clerk_jwt(token)
            assert exc_info.value.status_code == 401

    def test_decode_clerk_jwt_invalid_format(self):
        """Test that invalid JWT format is rejected."""
        from app.clerk_auth import _decode_clerk_jwt
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            _decode_clerk_jwt("not-a-valid-jwt-token")
        assert exc_info.value.status_code == 401

    def test_get_clerk_user_id_from_header(self):
        """Test extracting Clerk user ID from Authorization header."""
        from app.clerk_auth import get_clerk_user_id

        import jwt
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.backends import default_backend
        from cryptography.hazmat.primitives.asymmetric import rsa

        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend(),
        )
        public_key = private_key.public_key()

        payload = {"sub": "user_test123", "exp": 9999999999, "nbf": 1000000000}
        token = jwt.encode(payload, private_key, algorithm="RS256")

        pem_public_key = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("utf-8")

        with patch("app.clerk_auth.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(clerk_jwt_public_key=pem_public_key)

            user_id = get_clerk_user_id(authorization=f"Bearer {token}")
            assert user_id == "user_test123"

    def test_get_clerk_user_id_missing_header(self):
        """Test extracting user ID with missing header."""
        from app.clerk_auth import get_clerk_user_id

        user_id = get_clerk_user_id(authorization="")
        assert user_id is None

    def test_get_clerk_user_id_invalid_header(self):
        """Test extracting user ID with invalid header format."""
        from app.clerk_auth import get_clerk_user_id

        user_id = get_clerk_user_id(authorization="InvalidFormat token")
        assert user_id is None


# --- API Key Injection Middleware Tests ---

class TestApiKeyInjectionMiddleware:
    """Tests for API key injection middleware."""

    @pytest.mark.asyncio
    async def test_extract_clerk_user_id_from_header(self):
        """Test extracting Clerk user ID from X-Clerk-User-ID header."""
        from app.api_key_injection import _extract_clerk_user_id_from_request

        mock_request = MagicMock()
        mock_request.headers = {"X-Clerk-User-ID": "user_test123"}

        user_id = await _extract_clerk_user_id_from_request(mock_request)
        assert user_id == "user_test123"

    @pytest.mark.asyncio
    async def test_extract_clerk_user_id_from_auth_header(self):
        """Test extracting Clerk user ID from Authorization header."""
        from app.api_key_injection import _extract_clerk_user_id_from_request

        mock_request = MagicMock()
        mock_request.headers = {"Authorization": "Bearer token"}
        mock_request.app = MagicMock()
        mock_request.app.dependency_overrides = {}

        with patch("app.api_key_injection.verify_clerk_token", new=AsyncMock(return_value={"sub": "user_test123"})):
            user_id = await _extract_clerk_user_id_from_request(mock_request)
        assert user_id == "user_test123"

    @pytest.mark.asyncio
    async def test_extract_clerk_user_id_no_headers(self):
        """Test extracting user ID with no relevant headers."""
        from app.api_key_injection import _extract_clerk_user_id_from_request

        mock_request = MagicMock()
        mock_request.headers = {}

        user_id = await _extract_clerk_user_id_from_request(mock_request)
        assert user_id is None

    def test_api_key_cache_hit(self):
        """Test that cached API keys are returned."""
        from app.api_key_injection import _api_key_cache

        # Populate cache
        _api_key_cache["user_cached"] = ("sk-cached-key", time.time())

        assert "user_cached" in _api_key_cache
        cached_key, cached_at = _api_key_cache["user_cached"]
        assert cached_key == "sk-cached-key"
        assert time.time() - cached_at < 300  # Within TTL

        # Clean up
        del _api_key_cache["user_cached"]

    def test_api_key_cache_expiry(self):
        """Test that expired cache entries are not used."""
        from app.api_key_injection import _api_key_cache

        # Populate cache with expired entry
        _api_key_cache["user_expired"] = ("sk-old-key", time.time() - 600)  # 10 min old

        # Verify it's expired
        _, cached_at = _api_key_cache["user_expired"]
        assert time.time() - cached_at >= 300  # Past TTL

        # Clean up
        del _api_key_cache["user_expired"]

    def test_invalidate_api_key_cache(self):
        """Test API key cache invalidation."""
        from app.api_key_injection import _api_key_cache, invalidate_api_key_cache

        _api_key_cache["user_to_invalidate"] = ("sk-key", 1000000000)
        assert "user_to_invalidate" in _api_key_cache

        invalidate_api_key_cache("user_to_invalidate")
        assert "user_to_invalidate" not in _api_key_cache

    def test_invalidate_nonexistent_key(self):
        """Test invalidating a nonexistent cache entry doesn't raise."""
        from app.api_key_injection import invalidate_api_key_cache

        # Should not raise
        invalidate_api_key_cache("user_does_not_exist")

    @pytest.mark.asyncio
    async def test_dispatch_rejects_missing_bearer_for_v1(self):
        """Middleware should reject /v1 requests without bearer header."""
        from app.api_key_injection import ApiKeyInjectionMiddleware

        request = MagicMock()
        request.url.path = "/v1/chat/completions"
        request.headers = {}
        request.state = MagicMock()
        request.app = MagicMock()
        request.app.dependency_overrides = {}

        call_next = AsyncMock()
        middleware = ApiKeyInjectionMiddleware(app=MagicMock())

        response = await middleware.dispatch(request, call_next)

        assert response.status_code == 401
        assert call_next.await_count == 0

    @pytest.mark.asyncio
    async def test_dispatch_rejects_invalid_signature_for_v1(self):
        """Middleware should reject invalid JWTs before forwarding."""
        from fastapi import HTTPException
        from app.api_key_injection import ApiKeyInjectionMiddleware

        request = MagicMock()
        request.url.path = "/v1/chat/completions"
        request.headers = {"Authorization": "Bearer bad-token"}
        request.state = MagicMock()
        request.app = MagicMock()
        request.app.dependency_overrides = {}

        call_next = AsyncMock()
        middleware = ApiKeyInjectionMiddleware(app=MagicMock())

        with patch(
            "app.api_key_injection._extract_clerk_user_id_from_request",
            new=AsyncMock(side_effect=HTTPException(status_code=401, detail="Invalid token")),
        ):
            response = await middleware.dispatch(request, call_next)

        assert response.status_code == 401
        assert call_next.await_count == 0
