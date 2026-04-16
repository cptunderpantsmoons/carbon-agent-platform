"""Tests for Railway GraphQL API client."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.railway import RailwayClient, get_railway_client
from gql.transport.exceptions import TransportQueryError
import structlog


@pytest.fixture
def mock_settings():
    """Mock settings for Railway configuration."""
    with patch("app.railway.get_settings") as mock:
        settings = MagicMock()
        settings.railway_api_token = "test-token"
        settings.railway_project_id = "test-project-id"
        settings.railway_team_id = "test-team-id"
        settings.railway_environment_id = "test-env-id"
        mock.return_value = settings
        yield settings


@pytest.fixture
def railway_client(mock_settings):
    """Create a Railway client instance with mocked settings."""
    return RailwayClient()


@pytest.mark.asyncio
async def test_railway_client_initialization(mock_settings):
    """Test Railway client initialization with settings."""
    client = RailwayClient()
    assert client.api_token == "test-token"
    assert client.project_id == "test-project-id"
    assert client.team_id == "test-team-id"
    assert client.environment_id == "test-env-id"


@pytest.mark.asyncio
async def test_get_railway_client_singleton():
    """Test that get_railway_client returns a singleton instance."""
    with patch("app.railway.get_settings") as mock_settings:
        settings = MagicMock()
        settings.railway_api_token = "test-token"
        settings.railway_project_id = "test-project-id"
        settings.railway_team_id = "test-team-id"
        settings.railway_environment_id = "test-env-id"
        mock_settings.return_value = settings

        client1 = await get_railway_client()
        client2 = await get_railway_client()

        assert client1 is client2


@pytest.mark.asyncio
async def test_create_service(railway_client):
    """Test creating a Railway service."""
    mock_client = AsyncMock()
    mock_client.execute.return_value = {
        "serviceCreate": {
            "id": "svc-123",
            "name": "test-service",
            "projectId": "test-project-id",
            "updatedAt": "2026-04-16T00:00:00Z"
        }
    }

    with patch.object(railway_client, "_get_client", return_value=mock_client):
        result = await railway_client.create_service(
            name="test-service",
            docker_image="carbon-agent-adapter:latest",
            memory="1GB",
            cpu=1
        )

        assert result["id"] == "svc-123"
        assert result["name"] == "test-service"
        assert result["projectId"] == "test-project-id"
        mock_client.execute.assert_called_once()


@pytest.mark.asyncio
async def test_create_service_with_volume_and_env_vars(railway_client):
    """Test creating a service with volume and environment variables."""
    mock_client = AsyncMock()
    mock_client.execute.return_value = {
        "serviceCreate": {
            "id": "svc-456",
            "name": "test-service-with-vol",
            "projectId": "test-project-id",
            "updatedAt": "2026-04-16T00:00:00Z"
        }
    }

    with patch.object(railway_client, "_get_client", return_value=mock_client):
        result = await railway_client.create_service(
            name="test-service-with-vol",
            docker_image="carbon-agent-adapter:latest",
            memory="2GB",
            cpu=2,
            volume_id="vol-123",
            env_vars={"API_KEY": "secret", "DEBUG": "true"}
        )

        assert result["id"] == "svc-456"
        assert result["name"] == "test-service-with-vol"


@pytest.mark.asyncio
async def test_delete_service(railway_client):
    """Test deleting a Railway service."""
    mock_client = AsyncMock()
    mock_client.execute.return_value = {
        "serviceDelete": {"id": "svc-123"}
    }

    with patch.object(railway_client, "_get_client", return_value=mock_client):
        result = await railway_client.delete_service("svc-123")

        assert result is True
        mock_client.execute.assert_called_once()


@pytest.mark.asyncio
async def test_delete_service_error(railway_client):
    """Test handling errors when deleting a service."""
    mock_client = AsyncMock()
    mock_client.execute.side_effect = TransportQueryError("Service not found")

    with patch.object(railway_client, "_get_client", return_value=mock_client):
        with pytest.raises(TransportQueryError):
            await railway_client.delete_service("non-existent-id")


@pytest.mark.asyncio
async def test_get_service(railway_client):
    """Test getting service details."""
    mock_client = AsyncMock()
    mock_client.execute.return_value = {
        "service": {
            "id": "svc-123",
            "name": "test-service",
            "projectId": "test-project-id",
            "updatedAt": "2026-04-16T00:00:00Z",
            "status": "running",
            "serviceInstances": [
                {"id": "inst-1", "status": "running", "createdAt": "2026-04-16T00:00:00Z"}
            ]
        }
    }

    with patch.object(railway_client, "_get_client", return_value=mock_client):
        result = await railway_client.get_service("svc-123")

        assert result["id"] == "svc-123"
        assert result["name"] == "test-service"
        assert result["status"] == "running"
        assert len(result["serviceInstances"]) == 1


@pytest.mark.asyncio
async def test_create_volume(railway_client):
    """Test creating a Railway volume."""
    mock_client = AsyncMock()
    mock_client.execute.return_value = {
        "volumeCreate": {
            "id": "vol-123",
            "name": "test-volume",
            "projectId": "test-project-id",
            "size": 5
        }
    }

    with patch.object(railway_client, "_get_client", return_value=mock_client):
        result = await railway_client.create_volume(
            name="test-volume",
            size_gb=5,
            mount_path="/data"
        )

        assert result["id"] == "vol-123"
        assert result["name"] == "test-volume"
        assert result["size"] == 5
        mock_client.execute.assert_called_once()


@pytest.mark.asyncio
async def test_create_volume_custom_size(railway_client):
    """Test creating a volume with custom size."""
    mock_client = AsyncMock()
    mock_client.execute.return_value = {
        "volumeCreate": {
            "id": "vol-456",
            "name": "large-volume",
            "projectId": "test-project-id",
            "size": 20
        }
    }

    with patch.object(railway_client, "_get_client", return_value=mock_client):
        result = await railway_client.create_volume(
            name="large-volume",
            size_gb=20,
            mount_path="/custom-data"
        )

        assert result["id"] == "vol-456"
        assert result["size"] == 20


@pytest.mark.asyncio
async def test_delete_volume(railway_client):
    """Test deleting a Railway volume."""
    mock_client = AsyncMock()
    mock_client.execute.return_value = {
        "volumeDelete": {"id": "vol-123"}
    }

    with patch.object(railway_client, "_get_client", return_value=mock_client):
        result = await railway_client.delete_volume("vol-123")

        assert result is True
        mock_client.execute.assert_called_once()


@pytest.mark.asyncio
async def test_get_volume(railway_client):
    """Test getting volume details."""
    mock_client = AsyncMock()
    mock_client.execute.return_value = {
        "volume": {
            "id": "vol-123",
            "name": "test-volume",
            "projectId": "test-project-id",
            "size": 10,
            "mountPath": "/data"
        }
    }

    with patch.object(railway_client, "_get_client", return_value=mock_client):
        result = await railway_client.get_volume("vol-123")

        assert result["id"] == "vol-123"
        assert result["name"] == "test-volume"
        assert result["size"] == 10
        assert result["mountPath"] == "/data"


@pytest.mark.asyncio
async def test_create_deployment(railway_client):
    """Test creating a deployment."""
    mock_client = AsyncMock()
    mock_client.execute.side_effect = [
        None,  # First call for environment variables (returns None)
        {  # Second call for deployment
            "serviceRedeploy": {
                "id": "deploy-123",
                "status": "building",
                "createdAt": "2026-04-16T00:00:00Z"
            }
        }
    ]

    with patch.object(railway_client, "_get_client", return_value=mock_client):
        result = await railway_client.create_deployment(
            service_id="svc-123",
            docker_image="carbon-agent-adapter:latest",
            env_vars={"API_KEY": "test-key"}
        )

        assert result["id"] == "deploy-123"
        assert result["status"] == "building"
        assert mock_client.execute.call_count == 2


@pytest.mark.asyncio
async def test_create_deployment_no_env_vars(railway_client):
    """Test creating a deployment without environment variables."""
    mock_client = AsyncMock()
    mock_client.execute.return_value = {
        "serviceRedeploy": {
            "id": "deploy-456",
            "status": "building",
            "createdAt": "2026-04-16T00:00:00Z"
        }
    }

    with patch.object(railway_client, "_get_client", return_value=mock_client):
        result = await railway_client.create_deployment(
            service_id="svc-123",
            docker_image="carbon-agent-adapter:latest"
        )

        assert result["id"] == "deploy-456"
        assert result["status"] == "building"
        # Should only call redeploy, not set env vars
        assert mock_client.execute.call_count == 1


@pytest.mark.asyncio
async def test_get_deployment(railway_client):
    """Test getting deployment details."""
    mock_client = AsyncMock()
    mock_client.execute.return_value = {
        "deployment": {
            "id": "deploy-123",
            "status": "success",
            "createdAt": "2026-04-16T00:00:00Z",
            "updatedAt": "2026-04-16T00:05:00Z",
            "domain": {
                "id": "dom-123",
                "serviceId": "svc-123",
                "domain": "test-service.up.railway.app"
            },
            "builder": {
                "id": "builder-123",
                "status": "success",
                "createdAt": "2026-04-16T00:00:00Z"
            }
        }
    }

    with patch.object(railway_client, "_get_client", return_value=mock_client):
        result = await railway_client.get_deployment("deploy-123")

        assert result["id"] == "deploy-123"
        assert result["status"] == "success"
        assert result["domain"]["domain"] == "test-service.up.railway.app"
        assert result["builder"]["status"] == "success"


@pytest.mark.asyncio
async def test_list_services(railway_client):
    """Test listing all services in a project."""
    mock_client = AsyncMock()
    mock_client.execute.return_value = {
        "project": {
            "services": [
                {
                    "id": "svc-1",
                    "name": "service-1",
                    "updatedAt": "2026-04-16T00:00:00Z",
                    "status": "running"
                },
                {
                    "id": "svc-2",
                    "name": "service-2",
                    "updatedAt": "2026-04-16T00:00:00Z",
                    "status": "stopped"
                }
            ]
        }
    }

    with patch.object(railway_client, "_get_client", return_value=mock_client):
        result = await railway_client.list_services()

        assert len(result) == 2
        assert result[0]["id"] == "svc-1"
        assert result[1]["id"] == "svc-2"


@pytest.mark.asyncio
async def test_list_services_custom_project(railway_client):
    """Test listing services in a specific project."""
    mock_client = AsyncMock()
    mock_client.execute.return_value = {
        "project": {
            "services": [
                {
                    "id": "svc-3",
                    "name": "service-3",
                    "updatedAt": "2026-04-16T00:00:00Z",
                    "status": "running"
                }
            ]
        }
    }

    with patch.object(railway_client, "_get_client", return_value=mock_client):
        result = await railway_client.list_services(project_id="custom-project-id")

        assert len(result) == 1
        assert result[0]["id"] == "svc-3"


@pytest.mark.asyncio
async def test_list_volumes(railway_client):
    """Test listing all volumes in a project."""
    mock_client = AsyncMock()
    mock_client.execute.return_value = {
        "project": {
            "volumes": [
                {
                    "id": "vol-1",
                    "name": "volume-1",
                    "size": 5,
                    "mountPath": "/data"
                },
                {
                    "id": "vol-2",
                    "name": "volume-2",
                    "size": 10,
                    "mountPath": "/cache"
                }
            ]
        }
    }

    with patch.object(railway_client, "_get_client", return_value=mock_client):
        result = await railway_client.list_volumes()

        assert len(result) == 2
        assert result[0]["id"] == "vol-1"
        assert result[1]["id"] == "vol-2"


@pytest.mark.asyncio
async def test_close_client(railway_client):
    """Test closing the Railway client."""
    mock_client = AsyncMock()
    mock_client.close_async = AsyncMock()

    railway_client._client = mock_client
    await railway_client.close()

    mock_client.close_async.assert_called_once()
    assert railway_client._client is None


@pytest.mark.asyncio
async def test_incomplete_configuration():
    """Test Railway client with incomplete configuration."""
    with patch("app.railway.get_settings") as mock_settings:
        settings = MagicMock()
        settings.railway_api_token = ""
        settings.railway_project_id = ""
        settings.railway_team_id = ""
        settings.railway_environment_id = ""
        mock_settings.return_value = settings

        client = RailwayClient()
        assert client.api_token == ""
        assert client.project_id == ""