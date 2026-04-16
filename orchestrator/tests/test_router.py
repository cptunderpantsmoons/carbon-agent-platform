"""Tests for the dynamic proxy router."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.router import AgentRouter
from app.session_manager import SessionManager
from app.models import User, UserStatus


@pytest.fixture
def mock_session_manager():
    sm = AsyncMock(spec=SessionManager)
    sm.spin_up.return_value = {
        "service_id": "svc-test",
        "volume_id": "vol-test",
        "deployment_id": "deploy-test",
    }
    return sm


@pytest.fixture
def router(mock_session_manager):
    return AgentRouter(mock_session_manager)


class TestResolveUser:
    @pytest.mark.asyncio
    async def test_resolve_user_not_found(self, router):
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=lambda: None))

        with pytest.raises(Exception) as exc_info:
            await router.resolve_user("sk-invalid", mock_db)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_resolve_user_inactive(self, router):
        user = User(
            id="usr-1", email="test@test.com", display_name="Test",
            api_key="sk-test", status=UserStatus.SUSPENDED,
        )
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=lambda: user))

        with pytest.raises(Exception) as exc_info:
            await router.resolve_user("sk-test", mock_db)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_resolve_user_success(self, router):
        user = User(
            id="usr-1", email="test@test.com", display_name="Test",
            api_key="sk-test", status=UserStatus.ACTIVE,
        )
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=lambda: user))

        result = await router.resolve_user("sk-test", mock_db)
        assert result.id == "usr-1"
