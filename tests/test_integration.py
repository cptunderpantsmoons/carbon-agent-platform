"""End-to-end integration tests for the platform."""

import os
import sys
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ADAPTER_PATH = os.path.join(PROJECT_ROOT, "adapter")


def _clear_app_modules():
    to_remove = [k for k in sys.modules if k == "app" or k.startswith("app.")]
    for k in to_remove:
        del sys.modules[k]


def _use_adapter():
    _clear_app_modules()
    if ADAPTER_PATH not in sys.path:
        sys.path.insert(0, ADAPTER_PATH)


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
                json={
                    "model": "carbon-agent",
                    "messages": [{"role": "user", "content": "Hello"}],
                    "stream": False,
                },
            )
            assert resp.status_code == 200
            assert resp.json()["choices"][0]["message"]["content"] == "Test response"

    def test_chat_completions_fake_stream(self):
        _use_adapter()
        from app.main import app

        with patch("app.main.AgentClient") as MockClient:
            mock = AsyncMock()
            mock.send_message.return_value = "Hello world"
            MockClient.return_value = mock
            client = TestClient(app)
            resp = client.post(
                "/v1/chat/completions",
                json={
                    "model": "carbon-agent",
                    "messages": [{"role": "user", "content": "Hello"}],
                    "stream": True,
                },
            )
            assert resp.status_code == 200
            assert "data: [DONE]" in resp.text
