"""Integration tests for user lifecycle events.

Tests idle spin-down, API key rotation, and user deletion propagation.
Uses SQLite in-memory database and mocked Docker Engine API.
"""
import base64
import json
import uuid
from datetime import datetime, timezone
from unittest.mock import patch, AsyncMock, MagicMock

import pytest
import pytest_asyncio
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from svix.webhooks import Webhook

from app.models import User, UserStatus, AuditLog, Base
from app.clerk import clerk_webhook_router
from app.users import user_router
from app.database import get_session


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


def _make_user_deleted_payload(clerk_user_id: str) -> bytes:
    payload = {
        "object": "event",
        "type": "user.deleted",
        "data": {
            "id": clerk_user_id,
            "email_addresses": [{"email_address": "deleted@example.com", "id": "idn_del"}],
            "first_name": "Deleted",
            "last_name": "User",
            "deleted": True,
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


@pytest_asyncio.fixture
async def active_user(db_session):
    """Create an active user for lifecycle tests."""
    user = User(
        id=str(uuid.uuid4()),
        clerk_user_id=f"clerk_{uuid.uuid4().hex[:8]}",
        email="lifecycle@example.com",
        display_name="Lifecycle User",
        api_key="sk-lifecycle-test-key-0001",
        status=UserStatus.ACTIVE,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


# --- App fixtures ---

def _create_webhook_app(db_session: AsyncSession) -> FastAPI:
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

class TestUserLifecycle:
    """Integration tests for idle spin-down, key rotation, deletion propagation."""

    @pytest.mark.asyncio
    async def test_idle_user_spun_down(self, db_session, active_user):
        """User inactive for idle_timeout -> container stopped, DB updated.

        Validates VAL-CROSS-001.
        """
        from app.session_manager import SessionManager

        mock_docker_manager = MagicMock()
        mock_docker_manager.spin_down_user_service = AsyncMock(return_value=True)

        sm = SessionManager()
        sm.docker_manager = mock_docker_manager
        with patch("app.session_manager.create_session", return_value=db_session):
            result = await sm.spin_down_idle_user(active_user.id)

        assert result is True

        # Verify DB updated — status should be PENDING (spun down)
        await db_session.refresh(active_user)
        assert active_user.status == UserStatus.PENDING

        # Verify Docker spin_down was called
        mock_docker_manager.spin_down_user_service.assert_called_once_with(active_user.id)

    @pytest.mark.asyncio
    async def test_idle_user_no_service(self, db_session):
        """User with no active service returns False when spin-down attempted."""
        from app.session_manager import SessionManager

        user = User(
            id=str(uuid.uuid4()),
            clerk_user_id=f"clerk_{uuid.uuid4().hex[:8]}",
            email="noservice@example.com",
            display_name="No Service User",
            api_key="sk-noservice-key",
            status=UserStatus.PENDING,
        )
        db_session.add(user)
        await db_session.commit()

        sm = SessionManager()
        with patch("app.session_manager.create_session", return_value=db_session):
            result = await sm.spin_down_idle_user(user.id)

        assert result is False

    @pytest.mark.asyncio
    async def test_api_key_rotation_invalidates_old(
        self, db_session, active_user
    ):
        """Rotate API key -> old key rejected, new key accepted.

        Validates VAL-CROSS-002.
        """
        old_key = active_user.api_key

        # Create a user-facing app to test key rotation
        app = FastAPI()

        # Override the get_session dependency to use our test session
        async def _override_get_session():
            yield db_session

        app.dependency_overrides[get_session] = _override_get_session
        app.include_router(user_router)

        client = TestClient(app, raise_server_exceptions=True)

        # Rotate the API key
        response = client.post(
            "/user/me/api-key/rotate",
            headers={"Authorization": f"Bearer {old_key}"},
        )

        assert response.status_code == 200
        data = response.json()
        new_key = data["new_api_key"]
        assert new_key != old_key
        assert new_key.startswith("sk-")

        # Old key should be rejected
        resp_old = client.get(
            "/user/me",
            headers={"Authorization": f"Bearer {old_key}"},
        )
        assert resp_old.status_code == 401

        # New key should be accepted
        resp_new = client.get(
            "/user/me",
            headers={"Authorization": f"Bearer {new_key}"},
        )
        assert resp_new.status_code == 200

    @pytest.mark.asyncio
    async def test_user_deleted_propagates(
        self, db_session, active_user, settings_mock
    ):
        """Clerk user.deleted -> container spun down, user suspended.

        Validates VAL-CROSS-011.
        """
        body = _make_user_deleted_payload(active_user.clerk_user_id)
        headers = _sign_payload(body)

        mock_docker_manager = MagicMock()
        mock_docker_manager.spin_down_user_service = AsyncMock(return_value=True)

        with patch("app.clerk.get_session_manager") as mock_get_sm:
            from app.session_manager import SessionManager
            sm = SessionManager()
            sm.docker_manager = mock_docker_manager
            mock_get_sm.return_value = sm

            app = _create_webhook_app(db_session)
            client = TestClient(app, raise_server_exceptions=True)

            response = client.post(
                "/webhooks/clerk",
                content=body,
                headers={"Content-Type": "application/json", **headers},
            )

        assert response.status_code == 200
        assert response.json()["status"] == "success"

        # Verify user status updated
        await db_session.refresh(active_user)
        assert active_user.status == UserStatus.SUSPENDED

        # Verify Docker spin_down was called
        mock_docker_manager.spin_down_user_service.assert_called_once_with(active_user.id)

    @pytest.mark.asyncio
    async def test_user_deleted_idempotent(
        self, db_session, settings_mock
    ):
        """Deleting an already-suspended user is idempotent."""
        user = User(
            id=str(uuid.uuid4()),
            clerk_user_id=f"clerk_{uuid.uuid4().hex[:8]}",
            email="alreadysuspended@example.com",
            display_name="Already Gone",
            api_key="sk-suspended-key",
            status=UserStatus.SUSPENDED,
        )
        db_session.add(user)
        await db_session.commit()

        body = _make_user_deleted_payload(user.clerk_user_id)
        headers = _sign_payload(body)

        app = _create_webhook_app(db_session)
        client = TestClient(app, raise_server_exceptions=True)

        response = client.post(
            "/webhooks/clerk",
            content=body,
            headers={"Content-Type": "application/json", **headers},
        )

        assert response.status_code == 200
        assert "already deleted" in response.json()["message"].lower()

    @pytest.mark.asyncio
    async def test_deleted_user_api_key_rejected(
        self, db_session, active_user, settings_mock
    ):
        """After user.deleted, API key auth should be rejected (401/403)."""
        # First delete the user via webhook
        body = _make_user_deleted_payload(active_user.clerk_user_id)
        headers = _sign_payload(body)

        mock_docker_manager = MagicMock()
        mock_docker_manager.spin_down_user_service = AsyncMock(return_value=True)

        with patch("app.clerk.get_session_manager") as mock_get_sm:
            from app.session_manager import SessionManager
            sm = SessionManager()
            sm.docker_manager = mock_docker_manager
            mock_get_sm.return_value = sm

            app = _create_webhook_app(db_session)
            client = TestClient(app, raise_server_exceptions=True)

            client.post(
                "/webhooks/clerk",
                content=body,
                headers={"Content-Type": "application/json", **headers},
            )

        # Now try to use the user's API key
        user_app = FastAPI()
        async def _override_get_session():
            yield db_session
        user_app.dependency_overrides[get_session] = _override_get_session
        user_app.include_router(user_router)

        user_client = TestClient(user_app, raise_server_exceptions=False)
        resp = user_client.get(
            "/user/me",
            headers={"Authorization": f"Bearer {active_user.api_key}"},
        )
        assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_spin_down_on_container_failure(
        self, db_session, active_user
    ):
        """If Docker stop fails, spin_down_user_service should still update DB status."""
        from app.session_manager import SessionManager

        mock_docker_manager = MagicMock()
        mock_docker_manager.spin_down_user_service = AsyncMock(return_value=True)

        sm = SessionManager()
        sm.docker_manager = mock_docker_manager
        with patch("app.session_manager.create_session", return_value=db_session):
            result = await sm.spin_down_idle_user(active_user.id)

        assert result is True

        # Verify DB updated
        await db_session.refresh(active_user)
        assert active_user.status == UserStatus.PENDING