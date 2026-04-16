"""Tests for the adapter FastAPI app."""
import json
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
