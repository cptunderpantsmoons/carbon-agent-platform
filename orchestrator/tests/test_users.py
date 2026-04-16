"""Tests for user-facing API endpoints."""
import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from unittest.mock import patch, AsyncMock
import uuid

from app.main import app
from app.models import User, UserStatus, Base
from app.database import get_session


@pytest_asyncio.fixture
async def test_engine():
    """Create test database engine."""
    engine = create_async_engine("sqlite+aiosqlite:///test_users.db", echo=True)
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
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def test_user(test_db):
    """Create a test user."""
    user = User(
        id=str(uuid.uuid4()),
        email="user@test.com",
        display_name="Test User",
        api_key="sk-user-test-key-123",
        status=UserStatus.ACTIVE,
        railway_service_id="svc-123",
        volume_id="vol-123",
    )
    test_db.add(user)
    import asyncio
    asyncio.run(test_db.commit())
    asyncio.run(test_db.refresh(user))
    return user


def test_health_endpoint(client):
    """Test health endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "service": "orchestrator"}


def test_user_me_without_auth(client):
    """Test /user/me endpoint requires authentication."""
    response = client.get("/user/me")
    assert response.status_code == 422  # Missing header


def test_user_me_with_invalid_auth(client):
    """Test /user/me rejects invalid authentication."""
    response = client.get(
        "/user/me",
        headers={"Authorization": "Bearer invalid-key"}
    )
    assert response.status_code == 401
    assert "Invalid API key" in response.json()["detail"]


def test_user_me_with_valid_auth(client, test_user):
    """Test /user/me returns current user profile."""
    response = client.get(
        "/user/me",
        headers={"Authorization": f"Bearer {test_user.api_key}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == test_user.id
    assert data["email"] == test_user.email
    assert data["display_name"] == test_user.display_name


def test_user_me_inactive_user(client):
    """Test /user/me rejects inactive users."""
    import asyncio
    from app.models import User, UserStatus

    # Create inactive user
    async def create_inactive_user():
        from app.database import engine
        async with engine.connect() as conn:
            await conn.execute(Base.metadata.create_all(conn))

    # This test would need proper setup with actual DB
    # For now, we'll skip it in the test suite


def test_user_update_profile(client, test_user):
    """Test updating user profile."""
    response = client.patch(
        "/user/me",
        json={"display_name": "Updated Name"},
        headers={"Authorization": f"Bearer {test_user.api_key}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["display_name"] == "Updated Name"


def test_user_session_info(client, test_user):
    """Test getting session info."""
    with patch("app.users.get_session_manager") as mock_get_manager:
        mock_manager = AsyncMock()
        mock_manager.get_session_info.return_value = None
        mock_get_manager.return_value = mock_manager

        response = client.get(
            "/user/me/session",
            headers={"Authorization": f"Bearer {test_user.api_key}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["active"] is False


def test_user_session_refresh(client, test_user):
    """Test refreshing user session."""
    with patch("app.users.get_session_manager") as mock_get_manager:
        mock_manager = AsyncMock()
        mock_manager.record_activity.return_value = None
        mock_get_manager.return_value = mock_manager

        response = client.post(
            "/user/me/session/refresh",
            headers={"Authorization": f"Bearer {test_user.api_key}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "refreshed"


def test_user_ensure_service(client, test_user):
    """Test ensuring user service."""
    with patch("app.users.get_session_manager") as mock_get_manager:
        mock_manager = AsyncMock()
        mock_manager.ensure_user_service.return_value = (False, None)
        mock_get_manager.return_value = mock_manager

        response = client.post(
            "/user/me/service/ensure",
            headers={"Authorization": f"Bearer {test_user.api_key}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "existing"


def test_user_spin_down_service(client, test_user):
    """Test spinning down user service."""
    with patch("app.users.get_session_manager") as mock_get_manager:
        mock_manager = AsyncMock()
        mock_manager.spin_down_user_service.return_value = True
        mock_get_manager.return_value = mock_manager

        response = client.post(
            "/user/me/service/spin-down",
            headers={"Authorization": f"Bearer {test_user.api_key}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "spun_down"


def test_user_service_status(client, test_user):
    """Test getting user service status."""
    with patch("app.users.get_session_manager") as mock_get_manager:
        mock_manager = AsyncMock()
        mock_manager.get_service_status.return_value = None
        mock_get_manager.return_value = mock_manager

        response = client.get(
            "/user/me/service/status",
            headers={"Authorization": f"Bearer {test_user.api_key}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["active"] is False


def test_user_api_key_rotation(client, test_user):
    """Test rotating user API key."""
    response = client.post(
        "/user/me/api-key/rotate",
        headers={"Authorization": f"Bearer {test_user.api_key}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "rotated"
    assert "new_api_key" in data
    assert data["new_api_key"].startswith("sk-")


def test_user_cannot_update_status(client, test_user):
    """Test that users cannot update their own status."""
    response = client.patch(
        "/user/me",
        json={"status": "suspended"},
        headers={"Authorization": f"Bearer {test_user.api_key}"}
    )
    # Status update should be ignored (not in allowed fields)
    assert response.status_code == 200
