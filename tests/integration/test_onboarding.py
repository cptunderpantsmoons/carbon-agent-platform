"""Integration tests for user onboarding flow.

Tests the full Clerk webhook → DB user → Docker container creation pipeline.
Uses SQLite in-memory database and mocked Docker Engine API.
"""
import base64
import json
import uuid
from datetime import datetime, timezone
from unittest.mock import patch, AsyncMock, MagicMock

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from svix.webhooks import Webhook

from app.models import User, UserStatus, AuditLog, Base
from app.clerk import clerk_webhook_router


# --- Svix signing helpers ---

_RAW_SECRET = b"itest_webhook_secret_2026"
WEBHOOK_SECRET = "whsec_" + base64.b64encode(_RAW_SECRET).decode("utf-8")


def _sign_payload(payload: bytes) -> dict:
    wh = Webhook(WEBHOOK_SECRET)
    ts = datetime.now(timezone.utc)
    msg_id = f"msg_{uuid.uuid4().hex}"
    sig = wh.sign(msg_id, ts, payload.decode("utf-8"))
    return {
        "svix-id": msg_id,
        "svix-timestamp": str(int(ts.timestamp())),
        "svix-signature": sig,
    }


def _make_user_created_payload(clerk_user_id: str, email: str = "new@example.com") -> bytes:
    payload = {
        "object": "event",
        "type": "user.created",
        "data": {
            "id": clerk_user_id,
            "email_addresses": [{"email_address": email, "id": "idn_new"}],
            "first_name": "New",
            "last_name": "User",
            "created_at": 1700000000000,
            "updated_at": 1700000000000,
        },
    }
    return json.dumps(payload).encode("utf-8")


# --- Database fixtures ---

@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine):
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as session:
        yield session


# --- App fixtures ---

def _create_test_app(db_session: AsyncSession) -> FastAPI:
    from starlette.middleware.base import BaseHTTPMiddleware

    class FixedDBMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            request.state.db = db_session
            return await call_next(request)

    app = FastAPI()
    app.add_middleware(FixedDBMiddleware)
    app.include_router(clerk_webhook_router)
    return app


@pytest.fixture
def settings_mock():
    with patch("app.clerk.get_settings") as mock:
        mock.return_value = MagicMock(
            clerk_webhook_secret=WEBHOOK_SECRET,
        )
        yield mock


# --- Tests ---

class TestUserOnboarding:
    """Integration tests for the Clerk webhook → provisioning flow."""

    @pytest.mark.asyncio
    async def test_user_created_triggers_provisioning(
        self, db_session, settings_mock
    ):
        """Clerk webhook → DB user record → Docker container created.

        Validates VAL-PROV-001, VAL-PROV-002, VAL-PROV-004.
        """
        clerk_user_id = f"user_{uuid.uuid4().hex[:8]}"
        body = _make_user_created_payload(clerk_user_id)
        headers = _sign_payload(body)

        # Mock Docker manager so we don't need real Docker access
        mock_docker_manager = MagicMock()
        mock_docker_manager.ensure_user_service = AsyncMock(
            return_value={"action": "created", "container_id": "abc123", "was_created": True}
        )

        with patch("app.session_manager.DockerServiceManager", return_value=mock_docker_manager), \
             patch("app.clerk.get_session_manager") as mock_get_sm:
            from app.session_manager import SessionManager
            sm = SessionManager()
            sm.docker_manager = mock_docker_manager
            mock_get_sm.return_value = sm

            app = _create_test_app(db_session)
            client = TestClient(app, raise_server_exceptions=True)

            response = client.post(
                "/webhooks/clerk",
                content=body,
                headers={"Content-Type": "application/json", **headers},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"

        # Verify user was created in DB
        result = await db_session.execute(
            select(User).where(User.clerk_user_id == clerk_user_id)
        )
        user = result.scalar_one_or_none()
        assert user is not None, "User should be created in DB"
        assert user.email == "new@example.com"
        assert user.status == UserStatus.ACTIVE
        assert user.api_key.startswith("sk-")

        # Verify audit log was created
        audit_result = await db_session.execute(
            select(AuditLog).where(AuditLog.user_id == user.id)
        )
        audit = audit_result.scalar_one_or_none()
        assert audit is not None
        assert audit.action == "user.created"

    @pytest.mark.asyncio
    async def test_duplicate_webhook_idempotent(
        self, db_session, settings_mock
    ):
        """Same webhook delivered twice doesn't create duplicate resources."""
        clerk_user_id = f"user_{uuid.uuid4().hex[:8]}"
        body = _make_user_created_payload(clerk_user_id)

        with patch("app.clerk.get_session_manager") as mock_get_sm:
            mock_sm = MagicMock()
            mock_sm.provision_user_background = AsyncMock(return_value=False)
            mock_get_sm.return_value = mock_sm

            app = _create_test_app(db_session)
            client = TestClient(app, raise_server_exceptions=True)

            # First request
            headers1 = _sign_payload(body)
            resp1 = client.post(
                "/webhooks/clerk",
                content=body,
                headers={"Content-Type": "application/json", **headers1},
            )
            assert resp1.status_code == 200

            # Second request with same payload (re-signed with new timestamp)
            headers2 = _sign_payload(body)
            resp2 = client.post(
                "/webhooks/clerk",
                content=body,
                headers={"Content-Type": "application/json", **headers2},
            )
            assert resp2.status_code == 200
            assert resp2.json()["message"] == "User already exists"

        # Only one user should exist
        result = await db_session.execute(
            select(User).where(User.clerk_user_id == clerk_user_id)
        )
        users = result.scalars().all()
        assert len(users) == 1

    @pytest.mark.asyncio
    async def test_webhook_signature_rejection(
        self, db_session, settings_mock
    ):
        """Invalid Svix signature returns 400, no DB writes."""
        clerk_user_id = f"user_{uuid.uuid4().hex[:8]}"
        body = _make_user_created_payload(clerk_user_id)

        app = _create_test_app(db_session)
        client = TestClient(app, raise_server_exceptions=False)

        response = client.post(
            "/webhooks/clerk",
            content=body,
            headers={
                "Content-Type": "application/json",
                "svix-id": "msg_fake",
                "svix-timestamp": str(int(datetime.now(timezone.utc).timestamp())),
                "svix-signature": "v1,g0hM9SsE+OTPJTDtR6QxvJah0JYJ7BEdd0fySUJHycQ=",
            },
        )

        assert response.status_code == 400
        assert "Invalid webhook signature" in response.json().get("detail", "")

        # Verify no user was created
        result = await db_session.execute(
            select(User).where(User.clerk_user_id == clerk_user_id)
        )
        assert result.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_user_linked_to_existing_email(
        self, db_session, settings_mock
    ):
        """Clerk webhook for an existing admin-created user links by email."""
        # Pre-create a user without clerk_user_id
        existing_user = User(
            id=str(uuid.uuid4()),
            clerk_user_id=None,
            email="existing@example.com",
            display_name="Admin User",
            api_key="sk-precreated-key",
            status=UserStatus.ACTIVE,
        )
        db_session.add(existing_user)
        await db_session.commit()

        # Send webhook with same email
        clerk_user_id = f"user_{uuid.uuid4().hex[:8]}"
        body = _make_user_created_payload(clerk_user_id, email="existing@example.com")
        headers = _sign_payload(body)

        with patch("app.clerk.get_session_manager") as mock_get_sm:
            mock_sm = MagicMock()
            mock_sm.provision_user_background = AsyncMock(return_value=False)
            mock_get_sm.return_value = mock_sm

            app = _create_test_app(db_session)
            client = TestClient(app, raise_server_exceptions=True)

            response = client.post(
                "/webhooks/clerk",
                content=body,
                headers={"Content-Type": "application/json", **headers},
            )

        assert response.status_code == 200
        assert "linked" in response.json()["message"].lower()

        # Verify the existing user now has a clerk_user_id
        await db_session.refresh(existing_user)
        assert existing_user.clerk_user_id == clerk_user_id

    @pytest.mark.asyncio
    async def test_provision_user_background_creates_container(
        self, db_session
    ):
        """provision_user_background() creates Docker container for a new user."""
        from app.session_manager import SessionManager

        # Create user in DB without container
        user_id = str(uuid.uuid4())
        user = User(
            id=user_id,
            clerk_user_id=f"clerk_{uuid.uuid4().hex[:8]}",
            email="bgtest@example.com",
            display_name="BG Test",
            api_key="sk-bgtest-key",
            status=UserStatus.PENDING,
        )
        db_session.add(user)
        await db_session.commit()

        # Mock Docker manager
        mock_docker_manager = MagicMock()
        mock_docker_manager.ensure_user_service = AsyncMock(
            return_value={"action": "created", "container_id": "abc_bg", "was_created": True}
        )

        sm = SessionManager()
        sm.docker_manager = mock_docker_manager
        with patch("app.session_manager.create_session", return_value=db_session):
            was_created = await sm.provision_user_background(user_id)

        assert was_created is True

        # Verify user is now ACTIVE
        await db_session.refresh(user)
        assert user.status == UserStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_provision_user_background_reraises_on_failure(
        self, db_session
    ):
        """provision_user_background() re-raises so asyncio.create_task logs it."""
        from app.session_manager import SessionManager

        user_id = str(uuid.uuid4())
        user = User(
            id=user_id,
            clerk_user_id=f"clerk_{uuid.uuid4().hex[:8]}",
            email="failtest@example.com",
            display_name="Fail Test",
            api_key="sk-fail-key",
            status=UserStatus.PENDING,
        )
        db_session.add(user)
        await db_session.commit()

        # Mock Docker manager to raise
        mock_docker_manager = MagicMock()
        mock_docker_manager.ensure_user_service = AsyncMock(
            side_effect=RuntimeError("Docker API unavailable")
        )

        sm = SessionManager()
        sm.docker_manager = mock_docker_manager
        with patch("app.session_manager.create_session", return_value=db_session):
            with pytest.raises(RuntimeError, match="Docker API unavailable"):
                await sm.provision_user_background(user_id)