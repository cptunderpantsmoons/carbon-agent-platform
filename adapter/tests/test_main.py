"""Tests for the adapter FastAPI app."""
import json
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch
from app.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_list_models():
    response = client.get("/v1/models")
    assert response.status_code == 200
    data = response.json()
    assert data["object"] == "list"
    assert len(data["data"]) == 1
    assert data["data"][0]["id"] == "carbon-agent"


def test_chat_completions_no_user_message():
    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "carbon-agent",
            "messages": [{"role": "system", "content": "You are helpful."}],
        },
    )
    assert response.status_code == 400


def test_chat_completions_non_streaming():
    with patch("app.main.AgentClient") as MockClient:
        mock_instance = AsyncMock()
        mock_instance.send_message.return_value = "Hello from agent!"
        MockClient.return_value = mock_instance

        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "carbon-agent",
                "messages": [{"role": "user", "content": "Hi!"}],
                "stream": False,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["object"] == "chat.completion"
        assert data["choices"][0]["message"]["content"] == "Hello from agent!"


def test_chat_completions_fake_stream():
    """Verify streaming response fakes SSE format with word chunks."""
    with patch("app.main.AgentClient") as MockClient:
        mock_instance = AsyncMock()
        mock_instance.send_message.return_value = "Hello world from agent"
        MockClient.return_value = mock_instance

        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "carbon-agent",
                "messages": [{"role": "user", "content": "Hi!"}],
                "stream": True,
            },
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"

        # Parse SSE lines
        lines = response.text.strip().split("\n")
        data_lines = [l for l in lines if l.startswith("data: ")]

        # Should have: role chunk, word chunks, finish chunk, [DONE]
        assert len(data_lines) >= 4

        # First data line should have role=assistant
        first = json.loads(data_lines[0][6:])
        assert first["choices"][0]["delta"]["role"] == "assistant"

        # Last data line should be [DONE]
        assert data_lines[-1].strip() == "data: [DONE]"

        # Second-to-last should have finish_reason=stop
        second_last = json.loads(data_lines[-2][6:])
        assert second_last["choices"][0]["finish_reason"] == "stop"

        # Content chunks should contain the words
        content_parts = []
        for dl in data_lines[1:-2]:
            parsed = json.loads(dl[6:])
            content = parsed["choices"][0]["delta"].get("content")
            if content:
                content_parts.append(content)
        full_content = "".join(content_parts)
        assert "Hello" in full_content
        assert "agent" in full_content


def test_context_id_management():
    """Verify context_id get/set methods work."""
    from app.agent_client import AgentClient

    # Initially no context
    assert AgentClient.get_context_id("user-1") is None

    # Set and retrieve
    AgentClient.set_context_id("user-1", "ctx-abc-123")
    assert AgentClient.get_context_id("user-1") == "ctx-abc-123"

    # Different user has no context
    assert AgentClient.get_context_id("user-2") is None

    # Clean up for test isolation
    AgentClient.set_context_id("user-1", "")
