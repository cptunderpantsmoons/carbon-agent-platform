"""Tests for session manager and Railway service lifecycle."""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from app.session_manager import SessionManager, get_session_manager
from app.models import User, UserStatus


@pytest.fixture
def session_manager():
    """Create a fresh session manager for each test."""
    return SessionManager()


@pytest.fixture
def mock_user():
    """Create a mock user for testing."""
    user = User(
        id="test-user-1",
        email="test@example.com",
        display_name="Test User",
        api_key="test-api-key-123",
        status=UserStatus.PENDING,
        railway_service_id=None,
        volume_id=None,
    )
    return user


@pytest.mark.asyncio
async def test_session_manager_singleton():
    """Test that get_session_manager returns a singleton instance."""
    manager1 = get_session_manager()
    manager2 = get_session_manager()

    assert manager1 is manager2


@pytest.mark.asyncio
async def test_ensure_user_service_creates_new_service(
    session_manager,
    mock_user,
):
    """Test that ensure_user_service creates a new Railway service."""
    # Mock database session
    mock_db = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_db.execute.return_value = mock_result

    # Mock Railway client
    mock_railway_client = AsyncMock()
    mock_railway_client.create_volume.return_value = {"id": "vol-123"}
    mock_railway_client.create_service.return_value = {"id": "svc-123"}
    mock_railway_client.create_deployment.return_value = {"id": "deploy-123"}

    with patch("app.session_manager.get_railway_client", return_value=mock_railway_client):
        with patch("app.session_manager.get_settings") as mock_settings:
            settings = MagicMock()
            settings.volume_size_gb = 5
            settings.volume_mount_path = "/data"
            settings.agent_docker_image = "carbon-agent-adapter:latest"
            settings.agent_default_memory = "1GB"
            settings.agent_default_cpu = 1
            mock_settings.return_value = settings

            was_created, _ = await session_manager.ensure_user_service(mock_db, "test-user-1")

            assert was_created is True
            assert mock_user.railway_service_id == "svc-123"
            assert mock_user.volume_id == "vol-123"
            assert mock_user.status == UserStatus.ACTIVE

            # Verify Railway operations were called
            mock_railway_client.create_volume.assert_called_once()
            mock_railway_client.create_service.assert_called_once()
            mock_railway_client.create_deployment.assert_called_once()


@pytest.mark.asyncio
async def test_ensure_user_service_skips_existing_service(
    session_manager,
    mock_user,
):
    """Test that ensure_user_service skips if service already exists."""
    # Mock user with existing service
    mock_user.railway_service_id = "existing-svc-123"
    mock_user.volume_id = "existing-vol-123"

    # Mock database session
    mock_db = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_db.execute.return_value = mock_result

    # Mock Railway client (should not be called)
    mock_railway_client = AsyncMock()

    with patch("app.session_manager.get_railway_client", return_value=mock_railway_client):
        was_created, _ = await session_manager.ensure_user_service(mock_db, "test-user-1")

        assert was_created is False

        # Verify Railway operations were NOT called
        mock_railway_client.create_volume.assert_not_called()
        mock_railway_client.create_service.assert_not_called()


@pytest.mark.asyncio
async def test_ensure_user_service_handles_nonexistent_user(
    session_manager,
):
    """Test that ensure_user_service handles nonexistent user gracefully."""
    # Mock database session returning None
    mock_db = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

    was_created, service_url = await session_manager.ensure_user_service(mock_db, "nonexistent-user")

    assert was_created is False
    assert service_url is None


@pytest.mark.asyncio
async def test_spin_down_user_service(
    session_manager,
    mock_user,
):
    """Test spinning down a user's Railway service."""
    # Set up user with active service
    mock_user.railway_service_id = "svc-123"
    mock_user.volume_id = "vol-123"
    mock_user.status = UserStatus.ACTIVE

    # Mock database session
    mock_db = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_db.execute.return_value = mock_result

    # Mock Railway client
    mock_railway_client = AsyncMock()
    mock_railway_client.delete_service.return_value = True
    mock_railway_client.delete_volume.return_value = True

    with patch("app.session_manager.get_railway_client", return_value=mock_railway_client):
        result = await session_manager.spin_down_user_service(mock_db, "test-user-1")

        assert result is True
        assert mock_user.railway_service_id is None
        assert mock_user.volume_id is None
        assert mock_user.status == UserStatus.PENDING

        # Verify Railway operations were called
        mock_railway_client.delete_service.assert_called_once_with("svc-123")
        mock_railway_client.delete_volume.assert_called_once_with("vol-123")


@pytest.mark.asyncio
async def test_spin_down_user_service_handles_no_service(
    session_manager,
    mock_user,
):
    """Test spin down when user has no service."""
    # Mock user without service
    mock_user.railway_service_id = None
    mock_user.volume_id = None

    # Mock database session
    mock_db = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_db.execute.return_value = mock_result

    # Mock Railway client (should not be called)
    mock_railway_client = AsyncMock()

    with patch("app.session_manager.get_railway_client", return_value=mock_railway_client):
        result = await session_manager.spin_down_user_service(mock_db, "test-user-1")

        assert result is False

        # Verify Railway operations were NOT called
        mock_railway_client.delete_service.assert_not_called()
        mock_railway_client.delete_volume.assert_not_called()


@pytest.mark.asyncio
async def test_record_activity(session_manager):
    """Test recording user activity."""
    user_id = "test-user-1"

    # Record activity
    await session_manager.record_activity(user_id)

    # Verify activity was recorded
    assert user_id in session_manager._active_sessions
    assert isinstance(session_manager._active_sessions[user_id], datetime)


@pytest.mark.asyncio
async def test_get_service_status(
    session_manager,
    mock_user,
):
    """Test getting service status."""
    # Set up user with active service
    mock_user.railway_service_id = "svc-123"
    mock_user.volume_id = "vol-123"

    # Mock database session
    mock_db = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_db.execute.return_value = mock_result

    # Mock Railway client
    mock_railway_client = AsyncMock()
    mock_railway_client.get_service.return_value = {
        "id": "svc-123",
        "name": "user-test-service",
        "status": "running",
        "updatedAt": "2026-04-16T00:00:00Z",
        "serviceInstances": [
            {"id": "inst-1", "status": "running", "createdAt": "2026-04-16T00:00:00Z"}
        ],
    }

    with patch("app.session_manager.get_railway_client", return_value=mock_railway_client):
        status = await session_manager.get_service_status(mock_db, "test-user-1")

        assert status is not None
        assert status["service_id"] == "svc-123"
        assert status["volume_id"] == "vol-123"
        assert status["status"] == "running"
        assert len(status["instances"]) == 1


@pytest.mark.asyncio
async def test_get_service_status_no_service(
    session_manager,
    mock_user,
):
    """Test getting service status when user has no service."""
    # Mock user without service
    mock_user.railway_service_id = None
    mock_user.volume_id = None

    # Mock database session
    mock_db = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_db.execute.return_value = mock_result

    status = await session_manager.get_service_status(mock_db, "test-user-1")

    assert status is None


@pytest.mark.asyncio
async def test_get_service_status_nonexistent_user(
    session_manager,
):
    """Test getting service status for nonexistent user."""
    # Mock database session returning None
    mock_db = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

    status = await session_manager.get_service_status(mock_db, "nonexistent-user")

    assert status is None


@pytest.mark.asyncio
async def test_get_active_session_count(session_manager):
    """Test getting active session count."""
    # Initially should be 0
    count = await session_manager.get_active_session_count()
    assert count == 0

    # Add some sessions
    await session_manager.record_activity("user-1")
    await session_manager.record_activity("user-2")
    await session_manager.record_activity("user-3")

    count = await session_manager.get_active_session_count()
    assert count == 3


@pytest.mark.asyncio
async def test_get_session_info(session_manager):
    """Test getting session info for a user."""
    user_id = "test-user-1"

    # Record activity
    await session_manager.record_activity(user_id)

    # Get session info
    info = await session_manager.get_session_info(user_id)

    assert info is not None
    assert info["user_id"] == user_id
    assert "last_activity" in info
    assert "idle_seconds" in info
    assert "timeout_seconds" in info


@pytest.mark.asyncio
async def test_get_session_info_no_session(session_manager):
    """Test getting session info for user with no active session."""
    info = await session_manager.get_session_info("nonexistent-user")

    assert info is None


@pytest.mark.asyncio
async def test_cleanup_idle_sessions_background_task(session_manager):
    """Test that cleanup task can be started and stopped."""
    # Start cleanup task
    await session_manager.start_cleanup_task()

    assert session_manager._cleanup_task is not None

    # Stop cleanup task
    await session_manager.stop_cleanup_task()

    assert session_manager._cleanup_task is None


@pytest.mark.asyncio
async def test_concurrent_session_operations(
    session_manager,
    mock_user,
):
    """Test that concurrent operations for same user are serialized."""
    # Mock database session
    mock_db = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_db.execute.return_value = mock_result

    # Mock Railway client
    mock_railway_client = AsyncMock()
    mock_railway_client.create_volume.return_value = {"id": "vol-123"}
    mock_railway_client.create_service.return_value = {"id": "svc-123"}
    mock_railway_client.create_deployment.return_value = {"id": "deploy-123"}

    with patch("app.session_manager.get_railway_client", return_value=mock_railway_client):
        with patch("app.session_manager.get_settings") as mock_settings:
            settings = MagicMock()
            settings.volume_size_gb = 5
            settings.volume_mount_path = "/data"
            settings.agent_docker_image = "carbon-agent-adapter:latest"
            settings.agent_default_memory = "1GB"
            settings.agent_default_cpu = 1
            mock_settings.return_value = settings

            # Start multiple concurrent operations for same user
            tasks = [
                session_manager.ensure_user_service(mock_db, "test-user-1"),
                session_manager.ensure_user_service(mock_db, "test-user-1"),
                session_manager.ensure_user_service(mock_db, "test-user-1"),
            ]

            results = await asyncio.gather(*tasks)

            # Only one should create the service, others should skip
            created_count = sum(1 for was_created, _ in results if was_created)
            assert created_count == 1

            # Verify service was only created once
            mock_railway_client.create_volume.assert_called_once()


@pytest.mark.asyncio
async def test_spin_up_with_env_vars(
    session_manager,
    mock_user,
):
    """Test that service is spun up with correct environment variables."""
    # Mock database session
    mock_db = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_db.execute.return_value = mock_result

    # Mock Railway client
    mock_railway_client = AsyncMock()
    mock_railway_client.create_volume.return_value = {"id": "vol-123"}
    mock_railway_client.create_service.return_value = {"id": "svc-123"}
    mock_railway_client.create_deployment.return_value = {"id": "deploy-123"}

    with patch("app.session_manager.get_railway_client", return_value=mock_railway_client):
        with patch("app.session_manager.get_settings") as mock_settings:
            settings = MagicMock()
            settings.volume_size_gb = 5
            settings.volume_mount_path = "/data"
            settings.agent_docker_image = "carbon-agent-adapter:latest"
            settings.agent_default_memory = "1GB"
            settings.agent_default_cpu = 1
            mock_settings.return_value = settings

            await session_manager.ensure_user_service(mock_db, "test-user-1")

            # Verify deployment was created with correct env vars
            call_args = mock_railway_client.create_deployment.call_args
            env_vars = call_args.kwargs.get("env_vars")

            assert env_vars is not None
            assert env_vars["USER_ID"] == "test-user-1"
            assert env_vars["API_KEY"] == "test-api-key-123"
            assert env_vars["DISPLAY_NAME"] == "Test User"


@pytest.mark.asyncio
async def test_spin_up_failure_cleanup(
    session_manager,
    mock_user,
):
    """Test that partial service creation is cleaned up on failure."""
    # Mock database session
    mock_db = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_db.execute.return_value = mock_result

    # Mock Railway client with partial failure
    mock_railway_client = AsyncMock()
    mock_railway_client.create_volume.return_value = {"id": "vol-123"}
    mock_railway_client.create_service.side_effect = Exception("Service creation failed")

    with patch("app.session_manager.get_railway_client", return_value=mock_railway_client):
        with patch("app.session_manager.get_settings") as mock_settings:
            settings = MagicMock()
            settings.volume_size_gb = 5
            settings.volume_mount_path = "/data"
            settings.agent_docker_image = "carbon-agent-adapter:latest"
            settings.agent_default_memory = "1GB"
            settings.agent_default_cpu = 1
            mock_settings.return_value = settings

            # Should raise exception
            with pytest.raises(Exception, match="Service creation failed"):
                await session_manager.ensure_user_service(mock_db, "test-user-1")

            # Verify volume was cleaned up
            mock_railway_client.delete_volume.assert_called_once_with("vol-123")