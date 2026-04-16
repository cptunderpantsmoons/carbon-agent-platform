"""Tests for Railway API client."""
import pytest
from unittest.mock import AsyncMock, patch
from app.railway import RailwayClient


@pytest.fixture
def railway_client():
    return RailwayClient(
        api_token="test-token",
        project_id="proj-123",
        environment_id="env-123",
    )


@pytest.mark.asyncio
async def test_create_service(railway_client):
    mock_response = {
        "data": {
            "serviceCreate": {
                "id": "svc-001",
                "name": "agent-user-001",
            }
        }
    }
    with patch.object(railway_client, "_execute_query", new_callable=AsyncMock) as mock_query:
        mock_query.return_value = mock_response
        result = await railway_client.create_service("agent-user-001")
        assert result["id"] == "svc-001"
        mock_query.assert_called_once()


@pytest.mark.asyncio
async def test_deploy_service(railway_client):
    mock_response = {
        "data": {
            "deploymentTrigger": {
                "id": "deploy-001",
            }
        }
    }
    with patch.object(railway_client, "_execute_query", new_callable=AsyncMock) as mock_query:
        mock_query.return_value = mock_response
        result = await railway_client.deploy_service(
            service_id="svc-001",
            image_url="ghcr.io/carbon-agent/adapter:latest",
            env_vars={"USER_ID": "usr-001"},
        )
        assert result["id"] == "deploy-001"


@pytest.mark.asyncio
async def test_delete_service(railway_client):
    mock_response = {
        "data": {
            "serviceDelete": {"deleted": True}
        }
    }
    with patch.object(railway_client, "_execute_query", new_callable=AsyncMock) as mock_query:
        mock_query.return_value = mock_response
        result = await railway_client.delete_service("svc-001")
        assert result["deleted"] is True


@pytest.mark.asyncio
async def test_get_service_status(railway_client):
    mock_response = {
        "data": {
            "service": {
                "id": "svc-001",
                "name": "agent-user-001",
                "instances": [{
                    "id": "inst-001",
                    "status": "ACTIVE",
                }],
            }
        }
    }
    with patch.object(railway_client, "_execute_query", new_callable=AsyncMock) as mock_query:
        mock_query.return_value = mock_response
        result = await railway_client.get_service_status("svc-001")
        assert result["status"] == "ACTIVE"


@pytest.mark.asyncio
async def test_create_volume(railway_client):
    mock_response = {
        "data": {
            "volumeCreate": {
                "id": "vol-001",
                "name": "data-user-001",
            }
        }
    }
    with patch.object(railway_client, "_execute_query", new_callable=AsyncMock) as mock_query:
        mock_query.return_value = mock_response
        result = await railway_client.create_volume(
            service_id="svc-001",
            name="data-user-001",
            mount_path="/data",
            size_mb=5120,
        )
        assert result["id"] == "vol-001"
