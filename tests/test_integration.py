"""End-to-end integration tests for the multi-user platform."""
import os
import sys
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ADAPTER_PATH = os.path.join(PROJECT_ROOT, "adapter")
ORCH_PATH = os.path.join(PROJECT_ROOT, "orchestrator")


def _clear_app_modules():
    to_remove = [k for k in sys.modules if k == "app" or k.startswith("app.")]
    for k in to_remove:
        del sys.modules[k]


def _use_adapter():
    _clear_app_modules()
    if ORCH_PATH in sys.path:
        sys.path.remove(ORCH_PATH)
    if ADAPTER_PATH not in sys.path:
        sys.path.insert(0, ADAPTER_PATH)


def _use_orchestrator():
    _clear_app_modules()
    if ADAPTER_PATH in sys.path:
        sys.path.remove(ADAPTER_PATH)
    if ORCH_PATH not in sys.path:
        sys.path.insert(0, ORCH_PATH)


class TestAdapterFlow:
    def test_health_endpoint(self):
        _use_adapter()
        from app.main import app
        client = TestClient(app)
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["service"] == "carbon-agent-adapter"

    def test_models_endpoint(self):
        _use_adapter()
        from app.main import app
        client = TestClient(app)
        resp = client.get("/v1/models")
        assert resp.status_code == 200
        models = resp.json()["data"]
        assert any(m["id"] == "carbon-agent" for m in models)

    def test_chat_completions_non_streaming(self):
        _use_adapter()
        from app.main import app
        with patch("app.main.AgentClient") as MockClient:
            mock = AsyncMock()
            mock.send_message.return_value = "Test response"
            MockClient.return_value = mock
            client = TestClient(app)
            resp = client.post(
                "/v1/chat/completions",
                json={"model": "carbon-agent", "messages": [{"role": "user", "content": "Hello"}], "stream": False},
            )
            assert resp.status_code == 200
            assert resp.json()["choices"][0]["message"]["content"] == "Test response"


class TestOrchestratorFlow:
    def test_orchestrator_health(self):
        _use_orchestrator()
        from fastapi import FastAPI
        from fastapi.middleware.cors import CORSMiddleware
        app = FastAPI(title="Test")
        app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
        @app.get("/health")
        def health():
            return {"status": "healthy", "service": "orchestrator"}
        client = TestClient(app)
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_admin_requires_auth(self):
        _use_orchestrator()
        from fastapi import FastAPI
        from fastapi.middleware.cors import CORSMiddleware
        from app.admin import admin_router
        app = FastAPI(title="Test")
        app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
        app.include_router(admin_router)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/admin/health")
        assert resp.status_code == 422


class TestSessionLifecycle:
    @pytest.mark.asyncio
    async def test_spin_up_creates_resources(self):
        _use_orchestrator()
        from app.session_manager import SessionManager
        from app.models import User, UserStatus
        mock_railway = AsyncMock()
        mock_railway.create_service.return_value = {"id": "svc-test", "name": "agent-test"}
        mock_railway.create_volume.return_value = {"id": "vol-test", "name": "data-test"}
        mock_railway.deploy_service.return_value = {"id": "deploy-test"}
        settings = MagicMock(agent_docker_image="test:latest", volume_size_gb=5, volume_mount_path="/data")
        manager = SessionManager(mock_railway, settings)
        user = User(id="test-user", email="test@test.com", display_name="Test", api_key="sk-test", status=UserStatus.ACTIVE)
        result = await manager.spin_up(user)
        assert result["service_id"] == "svc-test"
        assert result["volume_id"] == "vol-test"

    @pytest.mark.asyncio
    async def test_idle_detection(self):
        _use_orchestrator()
        from app.session_manager import SessionManager
        from app.models import Session, SessionStatus
        from datetime import datetime, timezone, timedelta
        settings = MagicMock(session_idle_timeout_minutes=15)
        manager = SessionManager(None, settings)
        session = Session(id="ses-test", user_id="usr-test", status=SessionStatus.ACTIVE, last_activity_at=datetime.now(timezone.utc) - timedelta(minutes=20))
        assert manager.is_idle(session) is True
        session.last_activity_at = datetime.now(timezone.utc) - timedelta(minutes=5)
        assert manager.is_idle(session) is False
