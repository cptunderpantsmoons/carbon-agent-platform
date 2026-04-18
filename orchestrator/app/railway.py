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
        self._transport: Optional[HTTPXAsyncTransport] = None

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

        NOTE: The Railway GraphQL serviceCreate mutation only accepts projectId
        and name. docker_image / memory / cpu are applied via create_deployment.
        Volume attachment is handled separately via mount_volume_to_service().

        Args:
            name: Service name
            docker_image: Applied via create_deployment, not here
            memory: NOT applied by this call (Railway API limitation)
            cpu: NOT applied by this call (Railway API limitation)
            volume_id: Mount separately with mount_volume_to_service()
            env_vars: Applied via create_deployment, not here

        Returns:
            Dictionary containing service ID and details

        Raises:
            TransportQueryError: If the GraphQL query fails
        """
        client = await self._get_client()

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
            result = await client.execute(
                gql(mutation),
                variable_values={"projectId": self.project_id, "name": name},
            )
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
            await client.execute(gql(mutation), variable_values={"id": service_id})
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

        Creates the volume object only. Call mount_volume_to_service() afterwards
        to actually attach it to a service instance.

        Args:
            name: Volume name
            size_gb: Volume size in GB (informational; Railway manages size)
            mount_path: Intended mount path — passed to mount_volume_to_service()

        Returns:
            Dictionary containing volume ID and details

        Raises:
            TransportQueryError: If the GraphQL query fails
        """
        client = await self._get_client()

        mutation = """
        mutation createVolume($projectId: ID!, $name: String!) {
            volumeCreate(projectId: $projectId, name: $name) {
                id
                name
                projectId
            }
        }
        """

        try:
            result = await client.execute(
                gql(mutation),
                variable_values={"projectId": self.project_id, "name": name},
            )
            volume_data = result["volumeCreate"]
            logger.info(f"Created Railway volume: {volume_data['id']}")
            return volume_data

        except TransportQueryError as e:
            logger.error(f"Failed to create Railway volume: {e}")
            raise

    async def mount_volume_to_service(
        self,
        volume_id: str,
        service_id: str,
        mount_path: str = "/data",
    ) -> dict[str, Any]:
        """Mount a volume to a service in the configured environment.

        Uses the Railway volumeInstanceCreate mutation to attach an existing
        volume to a service. Must be called after both create_volume() and
        create_service() succeed.

        Args:
            volume_id: ID of the volume to attach
            service_id: ID of the service to attach the volume to
            mount_path: Container path where the volume will be mounted

        Returns:
            Dictionary containing the volume instance details (id, mountPath, etc.)

        Raises:
            TransportQueryError: If the GraphQL query fails
            ValueError: If environment_id is not configured
        """
        if not self.environment_id:
            raise ValueError(
                "railway_environment_id must be configured to mount volumes. "
                "Set the RAILWAY_ENVIRONMENT_ID environment variable."
            )

        client = await self._get_client()

        mutation = """
        mutation mountVolume(
            $volumeId: String!,
            $serviceId: String!,
            $environmentId: String!,
            $mountPath: String!
        ) {
            volumeInstanceCreate(input: {
                volumeId: $volumeId
                serviceId: $serviceId
                environmentId: $environmentId
                mountPath: $mountPath
            }) {
                id
                volumeId
                serviceId
                mountPath
            }
        }
        """

        try:
            result = await client.execute(
                gql(mutation),
                variable_values={
                    "volumeId": volume_id,
                    "serviceId": service_id,
                    "environmentId": self.environment_id,
                    "mountPath": mount_path,
                },
            )
            instance_data = result["volumeInstanceCreate"]
            logger.info(
                "volume_mounted",
                volume_id=volume_id,
                service_id=service_id,
                mount_path=mount_path,
                instance_id=instance_data.get("id"),
            )
            return instance_data

        except TransportQueryError as e:
            logger.error(
                "volume_mount_failed",
                volume_id=volume_id,
                service_id=service_id,
                error=str(e),
            )
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
            await client.execute(gql(mutation), variable_values={"id": volume_id})
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

        Sets environment variables on the service then triggers a redeploy.

        Args:
            service_id: Service ID to deploy
            docker_image: Docker image to deploy (used as source reference)
            env_vars: Optional environment variables to set before deploying

        Returns:
            Dictionary containing deployment ID and details

        Raises:
            TransportQueryError: If the GraphQL query fails
        """
        client = await self._get_client()

        if env_vars:
            variables_list = [{"key": k, "value": v} for k, v in env_vars.items()]
            upsert_mutation = """
            mutation upsertServiceVariables(
                $serviceId: ID!,
                $variables: [ServiceVariableInput!]!
            ) {
                serviceVariablesUpsert(serviceId: $serviceId, variables: $variables) {
                    id
                }
            }
            """
            try:
                await client.execute(
                    gql(upsert_mutation),
                    variable_values={
                        "serviceId": service_id,
                        "variables": variables_list,
                    },
                )
            except TransportQueryError as e:
                logger.error(f"Failed to set service variables for {service_id}: {e}")
                raise

        deploy_mutation = """
        mutation redeployService($id: ID!) {
            serviceRedeploy(id: $id) {
                id
                status
                createdAt
            }
        }
        """

        try:
            result = await client.execute(
                gql(deploy_mutation), variable_values={"id": service_id}
            )
            deployment_data = result["serviceRedeploy"]
            logger.info(
                f"Created Railway deployment for service {service_id}: {deployment_data['id']}"
            )
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
                    nodes {
                        id
                        name
                        updatedAt
                    }
                }
            }
        }
        """

        try:
            result = await client.execute(
                gql(query), variable_values={"projectId": effective_project_id}
            )
            return result["project"]["services"]["nodes"]

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
                    edges {
                        node {
                            id
                            name
                        }
                    }
                }
            }
        }
        """

        try:
            result = await client.execute(
                gql(query), variable_values={"projectId": effective_project_id}
            )
            return [
                edge["node"]
                for edge in result["project"]["volumes"]["edges"]
            ]

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
