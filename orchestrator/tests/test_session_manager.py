"""Tests for session manager."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
from app.session_manager import SessionManager
from app.models import User, Session, UserStatus, SessionStatus


@pytest.fixture
def mock_railway():
    client = AsyncMock()
    client.create_service.return_value = {"id": "svc-001", "name": "agent-user-001"}
    client.deploy_service.return_value = {"id": "deploy-001"}
    client.create_volume.return_value = {"id": "vol-001", "name": "data-user-001"}
    client.get_service_status.return_value = {"status": "ACTIVE"}
    client.delete_service.return_value = {"deleted": True}
    return client


@pytest.fixture
def mock_settings():
    s = MagicMock()
    s.agent_docker_image = "carbon-agent-adapter:latest"
    s.volume_size_gb = 5
    s.volume_mount_path = "/data"
    s.session_idle_timeout_minutes = 15
    s.session_spinup_timeout_seconds = 120
    return s


@pytest.fixture
def session_manager(mock_railway, mock_settings):
    return SessionManager(railway_client=mock_railway, settings=mock_settings)


@pytest.mark.asyncio
async def test_spin_up_creates_service_and_volume(session_manager, mock_railway):
    user = User(
        id="usr-001",
        email="test@example.com",
        display_name="Test",
        api_key="sk-test",
        status=UserStatus.ACTIVE,
    )

    result = await session_manager.spin_up(user)

    mock_railway.create_service.assert_called_once_with("agent-usr-001")
    mock_railway.create_volume.assert_called_once()
    mock_railway.deploy_service.assert_called_once()
    assert result["service_id"] == "svc-001"
    assert result["volume_id"] == "vol-001"


@pytest.mark.asyncio
async def test_spin_up_uses_existing_volume(session_manager, mock_railway):
    user = User(
        id="usr-001",
        email="test@example.com",
        display_name="Test",
        api_key="sk-test",
        status=UserStatus.ACTIVE,
        volume_id="vol-existing",
    )

    result = await session_manager.spin_up(user)

    # Volume should NOT be created if user already has one
    mock_railway.create_volume.assert_not_called()
    assert result["service_id"] == "svc-001"


@pytest.mark.asyncio
async def test_spin_down_removes_service(session_manager, mock_railway):
    result = await session_manager.spin_down(service_id="svc-001")

    mock_railway.delete_service.assert_called_once_with("svc-001")
    assert result["deleted"] is True


@pytest.mark.asyncio
async def test_is_idle_detects_timeout(session_manager, mock_settings):
    session = Session(
        id="ses-001",
        user_id="usr-001",
        status=SessionStatus.ACTIVE,
        last_activity_at=datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc),
    )
    now = datetime(2026, 1, 1, 10, 30, 0, tzinfo=timezone.utc)  # 30 min later

    result = session_manager.is_idle(session, now=now)
    assert result is True


@pytest.mark.asyncio
async def test_is_idle_not_yet(session_manager, mock_settings):
    session = Session(
        id="ses-001",
        user_id="usr-001",
        status=SessionStatus.ACTIVE,
        last_activity_at=datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc),
    )
    now = datetime(2026, 1, 1, 10, 10, 0, tzinfo=timezone.utc)  # 10 min later

    result = session_manager.is_idle(session, now=now)
    assert result is False
