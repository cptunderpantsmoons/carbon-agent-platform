"""Tests for the adapter FastAPI app."""

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


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


def test_chat_completions_preserves_openai_request_fields():
    """Test the OpenAI bridge forwards model and generation settings."""
    from app.runtime.responses import AgentExecutionResult, TokenUsage

    mock_result = AgentExecutionResult(
        output_text="Bridge works",
        provider="openai",
        model="gpt-4o-mini",
        token_usage=TokenUsage(prompt_tokens=3, completion_tokens=7, total_tokens=10),
        trace_id="trace-123",
        conversation_id=None,
        finish_reason="stop",
    )

    with patch(
        "app.main.execute_agent_run", new=AsyncMock(return_value=mock_result)
    ) as mock_run:
        response = client.post(
            "/v1/chat/completions",
            headers={"Authorization": "Bearer sk-test"},
            json={
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": "Be concise.", "name": "sys"},
                    {
                        "role": "user",
                        "content": "Hello",
                        "name": "tester",
                        "tool_call_id": "call-123",
                    },
                ],
                "temperature": 0.2,
                "max_tokens": 42,
                "stop": ["END"],
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["model"] == "gpt-4o-mini"
    assert body["choices"][0]["message"]["content"] == "Bridge works"

    runtime_request = mock_run.call_args.args[0]
    assert runtime_request.model == "gpt-4o-mini"
    assert runtime_request.max_tokens == 42
    assert runtime_request.stop == ["END"]
    assert runtime_request.messages[0].name == "sys"
    assert runtime_request.messages[1].name == "tester"
    assert runtime_request.messages[1].tool_call_id == "call-123"
