"""Railway GraphQL API client for managing services, volumes, and deployments."""
import httpx
from gql import gql, Client
from gql.transport.httpx import HTTPXAsyncTransport
from gql.transport.exceptions import TransportQueryError
import structlog
from typing import Any, Optional
from app.config import get_settings

logger = structlog.get_logger()


class RailwayClient:
    """Async GraphQL client for Railway API."""

    def __init__(self):
        settings = get_settings()
        self.api_token = settings.railway_api_token
        self.project_id = settings.railway_project_id
        self.team_id = settings.railway_team_id
        self.environment_id = settings.railway_environment_id

        if not all([self.api_token, self.project_id, self.team_id]):
            logger.warning("Railway configuration incomplete. API calls may fail.")

        self._client: Optional[Client] = None
        self._transport: Optional[HTTPAsyncTransport] = None

    async def _get_client(self) -> Client:
        """Get or create the GraphQL client."""
        if self._client is None:
            transport = HTTPXAsyncTransport(
                url="https://backboard.railway.app/graphql/v2",
                headers={"Authorization": f"Bearer {self.api_token}"},
            )
            self._client = Client(transport=transport, fetch_schema_from_transport=False)
        return self._client

    async def close(self) -> None:
        """Close the GraphQL client."""
        if self._client:
            await self._client.close_async()
            self._client = None
            self._transport = None

    async def create_service(
        self,
        name: str,
        docker_image: str,
        memory: str = "1GB",
        cpu: int = 1,
        volume_id: Optional[str] = None,
        env_vars: Optional[dict[str, str]] = None,
    ) -> dict[str, Any]:
        """Create a new Railway service.

        Args:
            name: Service name
            docker_image: Docker image to deploy
            memory: Memory allocation (e.g., "1GB")
            cpu: CPU count
            volume_id: Optional volume ID to mount
            env_vars: Optional environment variables

        Returns:
            Dictionary containing service ID and details

        Raises:
            TransportQueryError: If the GraphQL query fails
        """
        client = await self._get_client()

        # Build variables
        variables = {
            "projectId": self.project_id,
            "name": name,
        }

        # Build GraphQL mutation
        mutation = """
        mutation createService($projectId: ID!, $name: String!) {
            serviceCreate(projectId: $projectId, name: $name) {
                id
                name
                projectId
                updatedAt
            }
        }
        """

        try:
            result = await client.execute(gql(mutation), variable_values=variables)
            service_data = result["serviceCreate"]
            logger.info(f"Created Railway service: {service_data['id']}")
            return service_data

        except TransportQueryError as e:
            logger.error(f"Failed to create Railway service: {e}")
            raise

    async def delete_service(self, service_id: str) -> bool:
        """Delete a Railway service.

        Args:
            service_id: Service ID to delete

        Returns:
            True if successful

        Raises:
            TransportQueryError: If the GraphQL query fails
        """
        client = await self._get_client()

        mutation = """
        mutation deleteService($id: ID!) {
            serviceDelete(id: $id) {
                id
            }
        }
        """

        try:
            result = await client.execute(gql(mutation), variable_values={"id": service_id})
            logger.info(f"Deleted Railway service: {service_id}")
            return True

        except TransportQueryError as e:
            logger.error(f"Failed to delete Railway service {service_id}: {e}")
            raise

    async def get_service(self, service_id: str) -> dict[str, Any]:
        """Get service details.

        Args:
            service_id: Service ID to query

        Returns:
            Dictionary containing service details

        Raises:
            TransportQueryError: If the GraphQL query fails
        """
        client = await self._get_client()

        query = """
        query getService($id: ID!) {
            service(id: $id) {
                id
                name
                projectId
                updatedAt
                status
                serviceInstances {
                    id
                    status
                    createdAt
                }
            }
        }
        """

        try:
            result = await client.execute(gql(query), variable_values={"id": service_id})
            return result["service"]

        except TransportQueryError as e:
            logger.error(f"Failed to get Railway service {service_id}: {e}")
            raise

    async def create_volume(
        self,
        name: str,
        size_gb: int = 5,
        mount_path: str = "/data",
    ) -> dict[str, Any]:
        """Create a new Railway volume.

        Args:
            name: Volume name
            size_gb: Volume size in GB
            mount_path: Mount path in the container

        Returns:
            Dictionary containing volume ID and details

        Raises:
            TransportQueryError: If the GraphQL query fails
        """
        client = await self._get_client()

        # First create the volume
        mutation = """
        mutation createVolume($projectId: ID!, $name: String!) {
            volumeCreate(projectId: $projectId, name: $name) {
                id
                name
                projectId
                size
            }
        }
        """

        try:
            result = await client.execute(
                gql(mutation), variable_values={"projectId": self.project_id, "name": name}
            )
            volume_data = result["volumeCreate"]
            logger.info(f"Created Railway volume: {volume_data['id']}")
            return volume_data

        except TransportQueryError as e:
            logger.error(f"Failed to create Railway volume: {e}")
            raise

    async def delete_volume(self, volume_id: str) -> bool:
        """Delete a Railway volume.

        Args:
            volume_id: Volume ID to delete

        Returns:
            True if successful

        Raises:
            TransportQueryError: If the GraphQL query fails
        """
        client = await self._get_client()

        mutation = """
        mutation deleteVolume($id: ID!) {
            volumeDelete(id: $id) {
                id
            }
        }
        """

        try:
            result = await client.execute(gql(mutation), variable_values={"id": volume_id})
            logger.info(f"Deleted Railway volume: {volume_id}")
            return True

        except TransportQueryError as e:
            logger.error(f"Failed to delete Railway volume {volume_id}: {e}")
            raise

    async def get_volume(self, volume_id: str) -> dict[str, Any]:
        """Get volume details.

        Args:
            volume_id: Volume ID to query

        Returns:
            Dictionary containing volume details

        Raises:
            TransportQueryError: If the GraphQL query fails
        """
        client = await self._get_client()

        query = """
        query getVolume($id: ID!) {
            volume(id: $id) {
                id
                name
                projectId
                size
                mountPath
            }
        }
        """

        try:
            result = await client.execute(gql(query), variable_values={"id": volume_id})
            return result["volume"]

        except TransportQueryError as e:
            logger.error(f"Failed to get Railway volume {volume_id}: {e}")
            raise

    async def create_deployment(
        self,
        service_id: str,
        docker_image: str,
        env_vars: Optional[dict[str, str]] = None,
    ) -> dict[str, Any]:
        """Create a new deployment for a service.

        Args:
            service_id: Service ID to deploy
            docker_image: Docker image to deploy
            env_vars: Optional environment variables

        Returns:
            Dictionary containing deployment ID and details

        Raises:
            TransportQueryError: If the GraphQL query fails
        """
        client = await self._get_client()

        # Build environment variables
        variables_list = []
        if env_vars:
            for key, value in env_vars.items():
                variables_list.append({"key": key, "value": value})

        mutation = """
        mutation upsertServiceVariables($serviceId: ID!, $variables: [ServiceVariableInput!]!) {
            serviceVariablesUpsert(serviceId: $serviceId, variables: $variables) {
                id
            }
        }
        """

        try:
            # First set environment variables
            if variables_list:
                await client.execute(
                    gql(mutation),
                    variable_values={"serviceId": service_id, "variables": variables_list},
                )

            # Then trigger deployment
            deploy_mutation = """
            mutation redeployService($id: ID!) {
                serviceRedeploy(id: $id) {
                    id
                    status
                    createdAt
                }
            }
            """

            result = await client.execute(
                gql(deploy_mutation), variable_values={"id": service_id}
            )
            deployment_data = result["serviceRedeploy"]
            logger.info(f"Created Railway deployment for service {service_id}: {deployment_data['id']}")
            return deployment_data

        except TransportQueryError as e:
            logger.error(f"Failed to create Railway deployment: {e}")
            raise

    async def get_deployment(self, deployment_id: str) -> dict[str, Any]:
        """Get deployment details.

        Args:
            deployment_id: Deployment ID to query

        Returns:
            Dictionary containing deployment details

        Raises:
            TransportQueryError: If the GraphQL query fails
        """
        client = await self._get_client()

        query = """
        query getDeployment($id: ID!) {
            deployment(id: $id) {
                id
                status
                createdAt
                updatedAt
                domain {
                    id
                    serviceId
                    domain
                }
                builder {
                    id
                    status
                    createdAt
                }
            }
        }
        """

        try:
            result = await client.execute(gql(query), variable_values={"id": deployment_id})
            return result["deployment"]

        except TransportQueryError as e:
            logger.error(f"Failed to get Railway deployment {deployment_id}: {e}")
            raise

    async def list_services(
        self, project_id: Optional[str] = None
    ) -> list[dict[str, Any]]:
        """List all services in a project.

        Args:
            project_id: Project ID (defaults to configured project)

        Returns:
            List of service dictionaries

        Raises:
            TransportQueryError: If the GraphQL query fails
        """
        client = await self._get_client()
        effective_project_id = project_id or self.project_id

        query = """
        query getServices($projectId: ID!) {
            project(id: $projectId) {
                services {
                    id
                    name
                    updatedAt
                    status
                }
            }
        }
        """

        try:
            result = await client.execute(
                gql(query), variable_values={"projectId": effective_project_id}
            )
            return result["project"]["services"]

        except TransportQueryError as e:
            logger.error(f"Failed to list Railway services: {e}")
            raise

    async def list_volumes(
        self, project_id: Optional[str] = None
    ) -> list[dict[str, Any]]:
        """List all volumes in a project.

        Args:
            project_id: Project ID (defaults to configured project)

        Returns:
            List of volume dictionaries

        Raises:
            TransportQueryError: If the GraphQL query fails
        """
        client = await self._get_client()
        effective_project_id = project_id or self.project_id

        query = """
        query getVolumes($projectId: ID!) {
            project(id: $projectId) {
                volumes {
                    id
                    name
                    size
                    mountPath
                }
            }
        }
        """

        try:
            result = await client.execute(
                gql(query), variable_values={"projectId": effective_project_id}
            )
            return result["project"]["volumes"]

        except TransportQueryError as e:
            logger.error(f"Failed to list Railway volumes: {e}")
            raise


# Singleton instance for use across the application
_railway_client: Optional[RailwayClient] = None


async def get_railway_client() -> RailwayClient:
    """Get or create the singleton Railway client."""
    global _railway_client
    if _railway_client is None:
        _railway_client = RailwayClient()
    return _railway_client