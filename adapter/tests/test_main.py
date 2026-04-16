"""Tests for the adapter FastAPI app."""
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


def test_chat_completions_success():
    with patch("app.main.AgentClient") as MockClient:
        mock_instance = AsyncMock()
        mock_instance.send_message.return_value = "Hello from agent!"
        MockClient.return_value = mock_instance

        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "carbon-agent",
                "messages": [{"role": "user", "content": "Hi!"}],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["object"] == "chat.completion"
        assert data["choices"][0]["message"]["content"] == "Hello from agent!"
