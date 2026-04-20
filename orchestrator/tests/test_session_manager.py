"""Tests for session manager and Docker container lifecycle."""

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
    """Test that ensure_user_service creates a new Docker container."""
    # Mock database session
    mock_db = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_db.execute.return_value = mock_result

    # Mock Docker manager
    mock_docker = AsyncMock()
    mock_docker.ensure_user_service.return_value = {
        "action": "created",
        "container_id": "abc123def456",
        "was_created": True,
    }

    with patch.object(session_manager, "docker_manager", mock_docker):
        was_created, _ = await session_manager.ensure_user_service(
            mock_db, "test-user-1"
        )

        assert was_created is True
        assert mock_user.status == UserStatus.ACTIVE

        # Verify Docker operations were called
        mock_docker.ensure_user_service.assert_called_once()


@pytest.mark.asyncio
async def test_ensure_user_service_skips_existing_service(
    session_manager,
    mock_user,
):
    """Test that ensure_user_service skips if container already exists."""
    # Mock user with existing active service
    mock_user.status = UserStatus.ACTIVE

    # Mock database session
    mock_db = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_db.execute.return_value = mock_result

    # Mock Docker manager (should not be called)
    mock_docker = AsyncMock()
    mock_docker.get_container_status.return_value = "running"

    with patch.object(session_manager, "docker_manager", mock_docker):
        was_created, _ = await session_manager.ensure_user_service(
            mock_db, "test-user-1"
        )

        assert was_created is False

        # Verify Docker operations were NOT called
        mock_docker.get_container_status.assert_called_once_with("test-user-1")
        mock_docker.ensure_user_service.assert_not_called()


@pytest.mark.asyncio
async def test_ensure_user_service_recreates_missing_active_service(
    session_manager,
    mock_user,
):
    """Test that ensure_user_service reprovisions an active user without a container."""
    mock_user.status = UserStatus.ACTIVE

    mock_db = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_db.execute.return_value = mock_result

    mock_docker = AsyncMock()
    mock_docker.get_container_status.return_value = "missing"
    mock_docker.ensure_user_service.return_value = {
        "action": "created",
        "container_id": "abc123def456",
        "was_created": True,
    }

    with patch.object(session_manager, "docker_manager", mock_docker):
        was_created, _ = await session_manager.ensure_user_service(
            mock_db, "test-user-1"
        )

        assert was_created is True
        assert mock_user.status == UserStatus.ACTIVE
        mock_docker.get_container_status.assert_called_once_with("test-user-1")
        mock_docker.ensure_user_service.assert_called_once()


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

    was_created, service_url = await session_manager.ensure_user_service(
        mock_db, "nonexistent-user"
    )

    assert was_created is False
    assert service_url is None


@pytest.mark.asyncio
async def test_spin_down_user_service(
    session_manager,
    mock_user,
):
    """Test spinning down a user's Docker container."""
    # Set up user with active service
    mock_user.status = UserStatus.ACTIVE

    # Mock database session
    mock_db = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_db.execute.return_value = mock_result

    # Mock Docker manager
    mock_docker = AsyncMock()

    with patch.object(session_manager, "docker_manager", mock_docker):
        result = await session_manager.spin_down_user_service(mock_db, "test-user-1")

        assert result is True
        assert mock_user.status == UserStatus.PENDING

        # Verify Docker operations were called
        mock_docker.spin_down_user_service.assert_called_once_with("test-user-1")


@pytest.mark.asyncio
async def test_spin_down_user_service_handles_no_service(
    session_manager,
    mock_user,
):
    """Test spin down when user has no active container."""
    # Mock user without active service
    mock_user.status = UserStatus.PENDING

    # Mock database session
    mock_db = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_db.execute.return_value = mock_result

    # Mock Docker manager (should not be called)
    mock_docker = AsyncMock()

    with patch.object(session_manager, "docker_manager", mock_docker):
        result = await session_manager.spin_down_user_service(mock_db, "test-user-1")

        assert result is False

        # Verify Docker operations were NOT called
        mock_docker.spin_down_user_service.assert_not_called()


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
    """Test getting container status via Docker manager."""
    # Set up user with active service
    mock_user.status = UserStatus.ACTIVE

    # Mock database session
    mock_db = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_db.execute.return_value = mock_result

    # Mock Docker manager
    mock_docker = AsyncMock()
    mock_docker.get_container_status.return_value = "running"

    with patch.object(session_manager, "docker_manager", mock_docker):
        status = await session_manager.get_service_status(mock_db, "test-user-1")

        assert status is not None
        assert status["status"] == "running"
        assert "service_url" in status


@pytest.mark.asyncio
async def test_get_service_status_no_service(
    session_manager,
    mock_user,
):
    """Test getting service status when user has no active container."""
    # Mock user without active service
    mock_user.status = UserStatus.PENDING

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

    # Mock Docker manager
    mock_docker = AsyncMock()
    mock_docker.get_container_status.return_value = "running"
    mock_docker.ensure_user_service.return_value = {
        "action": "created",
        "container_id": "abc123",
        "was_created": True,
    }

    with patch.object(session_manager, "docker_manager", mock_docker):
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


@pytest.mark.asyncio
async def test_spin_up_failure_cleanup(
    session_manager,
    mock_user,
):
    """Test that container creation failure is handled correctly."""
    # Mock database session
    mock_db = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_db.execute.return_value = mock_result

    # Mock Docker manager with failure
    mock_docker = AsyncMock()
    mock_docker.ensure_user_service.side_effect = Exception("Container creation failed")

    with patch.object(session_manager, "docker_manager", mock_docker):
        # Should raise exception
        with pytest.raises(Exception, match="Container creation failed"):
            await session_manager.ensure_user_service(mock_db, "test-user-1")


@pytest.mark.asyncio
async def test_spin_down_idle_user_success(session_manager, mock_user):
    """Test spinning down an idle user's container with self-created DB session."""
    # Set up user with active service
    mock_user.status = UserStatus.ACTIVE

    # Mock database session
    mock_db = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_db.execute.return_value = mock_result

    # Mock Docker manager
    mock_docker = AsyncMock()

    # Record activity so user is in active sessions
    await session_manager.record_activity("test-user-1")
    assert "test-user-1" in session_manager._active_sessions

    with patch.object(session_manager, "docker_manager", mock_docker):
        with patch.object(session_manager, "_get_db_session", return_value=mock_db):
            result = await session_manager.spin_down_idle_user("test-user-1")

            assert result is True
            assert mock_user.status == UserStatus.PENDING

            # Verify Docker operations were called
            mock_docker.spin_down_user_service.assert_called_once_with("test-user-1")

            # Verify user was removed from active sessions
            assert "test-user-1" not in session_manager._active_sessions

            # Verify DB session was closed
            mock_db.close.assert_called_once()


@pytest.mark.asyncio
async def test_spin_down_idle_user_no_service(session_manager, mock_user):
    """Test spin_down_idle_user when user has no active container."""
    # Mock user without active service
    mock_user.status = UserStatus.PENDING

    # Mock database session
    mock_db = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_db.execute.return_value = mock_result

    # Record activity so user is in active sessions
    await session_manager.record_activity("test-user-1")
    assert "test-user-1" in session_manager._active_sessions

    # Mock Docker manager (should not be called)
    mock_docker = AsyncMock()

    with patch.object(session_manager, "docker_manager", mock_docker):
        with patch.object(session_manager, "_get_db_session", return_value=mock_db):
            result = await session_manager.spin_down_idle_user("test-user-1")

            assert result is False

            # Verify Docker operations were NOT called
            mock_docker.spin_down_user_service.assert_not_called()

            # User should still be removed from active sessions
            assert "test-user-1" not in session_manager._active_sessions


@pytest.mark.asyncio
async def test_spin_down_idle_user_nonexistent(session_manager):
    """Test spin_down_idle_user when user doesn't exist in DB."""
    # Mock database session returning None
    mock_db = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

    with patch.object(session_manager, "_get_db_session", return_value=mock_db):
        result = await session_manager.spin_down_idle_user("nonexistent-user")

        assert result is False
        mock_db.close.assert_called_once()


@pytest.mark.asyncio
async def test_spin_down_idle_user_error_handling(session_manager):
    """Test spin_down_idle_user handles errors gracefully."""
    # Mock database session that raises an error
    mock_db = AsyncMock(spec=AsyncSession)
    mock_db.execute.side_effect = Exception("Database connection failed")

    with patch.object(session_manager, "_get_db_session", return_value=mock_db):
        result = await session_manager.spin_down_idle_user("test-user-1")

        assert result is False
        mock_db.close.assert_called_once()


@pytest.mark.asyncio
async def test_provision_user_background_success(session_manager, mock_user):
    """Test provision_user_background provisions a new user container."""
    # Mock database session
    mock_db = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_db.execute.return_value = mock_result

    # Mock Docker manager
    mock_docker = AsyncMock()
    mock_docker.ensure_user_service.return_value = {
        "action": "created",
        "container_id": "abc123",
        "was_created": True,
    }

    with patch.object(session_manager, "docker_manager", mock_docker):
        with patch("app.session_manager.create_session", return_value=mock_db):
            was_created = await session_manager.provision_user_background("test-user-1")

            assert was_created is True
            mock_db.close.assert_called_once()


@pytest.mark.asyncio
async def test_provision_user_background_already_exists(session_manager, mock_user):
    """Test provision_user_background when user already has a service."""
    # Mock user with active service
    mock_user.status = UserStatus.ACTIVE

    # Mock database session
    mock_db = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_db.execute.return_value = mock_result

    # Mock Docker manager (should not be called)
    mock_docker = AsyncMock()
    mock_docker.get_container_status.return_value = "running"

    with patch.object(session_manager, "docker_manager", mock_docker):
        with patch("app.session_manager.create_session", return_value=mock_db):
            was_created = await session_manager.provision_user_background("test-user-1")

            assert was_created is False
            mock_docker.get_container_status.assert_called_once_with("test-user-1")
            mock_docker.ensure_user_service.assert_not_called()
            mock_db.close.assert_called_once()


@pytest.mark.asyncio
async def test_provision_user_background_failure_raises(session_manager):
    """Test that provision_user_background returns False when user not found."""
    # Explicitly configure mock to return None for user lookup (user not found)
    mock_db = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None  # User not found in DB
    mock_db.execute.return_value = mock_result

    with patch("app.session_manager.create_session", return_value=mock_db):
        result = await session_manager.provision_user_background("nonexistent-user")

        # User not found → ensure_user_service returns (False, None) → returns False
        assert result is False
        mock_db.close.assert_called_once()


@pytest.mark.asyncio
async def test_cleanup_idle_sessions_actually_spins_down_users(
    session_manager, mock_user
):
    """Test that the cleanup task actually spins down idle users."""
    # Set up user with active service
    mock_user.status = UserStatus.ACTIVE

    # Mock database session
    mock_db = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_db.execute.return_value = mock_result

    # Mock Docker manager
    # Set session activity to old time (beyond timeout)
    old_time = datetime.now(timezone.utc) - timedelta(minutes=30)
    session_manager._active_sessions["test-user-1"] = old_time

    # Patch spin_down_idle_user to verify it gets called
    with patch.object(
        session_manager, "spin_down_idle_user", return_value=True
    ) as mock_spin_down:
        # Run one iteration of the cleanup loop manually
        from app.config import get_settings

        settings = get_settings()
        idle_timeout = timedelta(minutes=settings.session_idle_timeout_minutes)
        current_time = datetime.now(timezone.utc)

        idle_users = []
        for user_id, last_activity in list(session_manager._active_sessions.items()):
            idle_time = current_time - last_activity
            if idle_time > idle_timeout:
                idle_users.append(user_id)

        # Verify idle user was identified
        assert "test-user-1" in idle_users

        # Call spin_down_idle_user as the loop would
        for user_id in idle_users:
            await session_manager.spin_down_idle_user(user_id)

        # Verify spin_down_idle_user was called
        mock_spin_down.assert_called_once_with("test-user-1")


@pytest.mark.asyncio
async def test_cleanup_idle_sessions_continues_on_failure(session_manager):
    """Test that cleanup continues processing users even if one fails."""
    # Set up multiple idle users
    old_time = datetime.now(timezone.utc) - timedelta(minutes=30)
    session_manager._active_sessions["user-1"] = old_time
    session_manager._active_sessions["user-2"] = old_time
    session_manager._active_sessions["user-3"] = old_time

    # Mock spin_down_idle_user to fail for user-2 but succeed for others
    async def mock_spin_down(user_id: str) -> bool:
        if user_id == "user-2":
            return False  # Simulate failure
        return True

    with patch.object(
        session_manager, "spin_down_idle_user", side_effect=mock_spin_down
    ):
        from app.config import get_settings

        settings = get_settings()
        idle_timeout = timedelta(minutes=settings.session_idle_timeout_minutes)
        current_time = datetime.now(timezone.utc)

        idle_users = []
        for user_id, last_activity in list(session_manager._active_sessions.items()):
            idle_time = current_time - last_activity
            if idle_time > idle_timeout:
                idle_users.append(user_id)

        # All three should be idle
        assert len(idle_users) == 3

        # Process all idle users - should not break on failure
        results = {}
        for user_id in idle_users:
            results[user_id] = await session_manager.spin_down_idle_user(user_id)

        # user-2 should have failed, others succeeded
        assert results["user-1"] is True
        assert results["user-2"] is False
        assert results["user-3"] is True

        # All three should have been attempted
        assert session_manager.spin_down_idle_user.call_count == 3


@pytest.mark.asyncio
async def test_cleanup_idle_sessions_removes_from_active_sessions(
    session_manager, mock_user
):
    """Test that cleanup removes users from _active_sessions after spin down."""
    # Set up user with active service
    mock_user.status = UserStatus.ACTIVE

    # Mock database session
    mock_db = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_db.execute.return_value = mock_result

    # Mock Docker manager
    mock_docker = AsyncMock()

    # Add user to active sessions
    await session_manager.record_activity("test-user-1")
    assert "test-user-1" in session_manager._active_sessions

    with patch.object(session_manager, "docker_manager", mock_docker):
        with patch.object(session_manager, "_get_db_session", return_value=mock_db):
            result = await session_manager.spin_down_idle_user("test-user-1")

            assert result is True
            # User should be removed from active sessions
            assert "test-user-1" not in session_manager._active_sessions
