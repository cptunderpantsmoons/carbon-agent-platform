"""Tests for user-facing API endpoints."""
import re
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import get_session
from app.main import app
from app.models import AuditLog, Base, User, UserStatus


@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def users_client(db_session):
    async def override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
async def test_user(db_session):
    user = User(
        id=str(uuid.uuid4()),
        email="user@test.com",
        display_name="Test User",
        api_key="sk-user-test-key-123",
        status=UserStatus.ACTIVE,
        clerk_user_id="user_clerk_abc",
        railway_service_id="svc-123",
        volume_id="vol-123",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.mark.asyncio
async def test_user_me_without_auth(users_client):
    response = await users_client.get("/user/me")
    assert response.status_code == 401
    assert response.json()["detail"] == "Missing Authorization header"


@pytest.mark.asyncio
async def test_user_me_with_invalid_auth(users_client):
    response = await users_client.get(
        "/user/me",
        headers={"Authorization": "Bearer invalid-key"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid API key"


@pytest.mark.asyncio
async def test_user_me_with_valid_auth_hides_api_key(users_client, test_user):
    response = await users_client.get(
        "/user/me",
        headers={"Authorization": f"Bearer {test_user.api_key}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == test_user.id
    assert data["email"] == test_user.email
    assert data["display_name"] == test_user.display_name
    assert "api_key" not in data


@pytest.mark.asyncio
async def test_user_update_profile_hides_api_key(users_client, test_user):
    response = await users_client.patch(
        "/user/me",
        json={"display_name": "Updated Name"},
        headers={"Authorization": f"Bearer {test_user.api_key}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["display_name"] == "Updated Name"
    assert "api_key" not in data


@pytest.mark.asyncio
async def test_user_session_info(users_client, test_user):
    with patch("app.users.get_session_manager") as mock_get_manager:
        mock_manager = AsyncMock()
        mock_manager.get_session_info.return_value = None
        mock_get_manager.return_value = mock_manager

        response = await users_client.get(
            "/user/me/session",
            headers={"Authorization": f"Bearer {test_user.api_key}"},
        )
        assert response.status_code == 200
        assert response.json()["active"] is False


@pytest.mark.asyncio
async def test_user_session_refresh(users_client, test_user):
    with patch("app.users.get_session_manager") as mock_get_manager:
        mock_manager = AsyncMock()
        mock_manager.record_activity.return_value = None
        mock_get_manager.return_value = mock_manager

        response = await users_client.post(
            "/user/me/session/refresh",
            headers={"Authorization": f"Bearer {test_user.api_key}"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "refreshed"


@pytest.mark.asyncio
async def test_user_ensure_service(users_client, test_user):
    with patch("app.users.get_session_manager") as mock_get_manager:
        mock_manager = AsyncMock()
        mock_manager.ensure_user_service.return_value = (False, None)
        mock_get_manager.return_value = mock_manager

        response = await users_client.post(
            "/user/me/service/ensure",
            headers={"Authorization": f"Bearer {test_user.api_key}"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "existing"


@pytest.mark.asyncio
async def test_user_spin_down_service(users_client, test_user):
    with patch("app.users.get_session_manager") as mock_get_manager:
        mock_manager = AsyncMock()
        mock_manager.spin_down_user_service.return_value = True
        mock_get_manager.return_value = mock_manager

        response = await users_client.post(
            "/user/me/service/spin-down",
            headers={"Authorization": f"Bearer {test_user.api_key}"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "spun_down"


@pytest.mark.asyncio
async def test_user_service_status(users_client, test_user):
    with patch("app.users.get_session_manager") as mock_get_manager:
        mock_manager = AsyncMock()
        mock_manager.get_service_status.return_value = None
        mock_get_manager.return_value = mock_manager

        response = await users_client.get(
            "/user/me/service/status",
            headers={"Authorization": f"Bearer {test_user.api_key}"},
        )
        assert response.status_code == 200
        assert response.json()["active"] is False


@pytest.mark.asyncio
async def test_user_api_key_rotation(users_client, db_session, test_user):
    old_key = test_user.api_key
    response = await users_client.post(
        "/user/me/api-key/rotate",
        headers={"Authorization": f"Bearer {old_key}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "rotated"
    assert data["new_api_key"] != old_key
    assert re.fullmatch(r"sk-[a-f0-9]{48}", data["new_api_key"]) is not None

    db_user = await db_session.get(User, test_user.id)
    assert db_user is not None
    assert db_user.api_key == data["new_api_key"]

    old_key_response = await users_client.get(
        "/user/me",
        headers={"Authorization": f"Bearer {old_key}"},
    )
    assert old_key_response.status_code == 401
    assert old_key_response.json()["detail"] == "Invalid API key"

    new_key_response = await users_client.get(
        "/user/me",
        headers={"Authorization": f"Bearer {data['new_api_key']}"},
    )
    assert new_key_response.status_code == 200

    logs = (await db_session.execute(select(AuditLog).where(AuditLog.user_id == test_user.id))).scalars().all()
    assert any(log.action == "user.api_key_rotated" for log in logs)


@pytest.mark.asyncio
async def test_rotate_requires_authentication(users_client, db_session, test_user):
    old_key = test_user.api_key
    response = await users_client.post("/user/me/api-key/rotate")
    assert response.status_code == 401
    assert response.json()["detail"] == "Missing Authorization header"

    db_user = await db_session.get(User, test_user.id)
    assert db_user is not None
    assert db_user.api_key == old_key


@pytest.mark.asyncio
async def test_rotate_rejects_jwt_bearer(users_client, test_user):
    response = await users_client.post(
        "/user/me/api-key/rotate",
        headers={"Authorization": "Bearer eyJhbGciOiJSUzI1NiJ9.fake.payload"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid API key"
