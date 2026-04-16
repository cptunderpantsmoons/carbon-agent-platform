"""Railway API client using GraphQL."""
import httpx
import structlog
from typing import Any

logger = structlog.get_logger()

RAILWAY_GRAPHQL_URL = "https://backboard.railway.app/graphql/v2"


class RailwayClient:
    """Async client for Railway's GraphQL API."""

    def __init__(self, api_token: str, project_id: str, environment_id: str, team_id: str = ""):
        self.api_token = api_token
        self.project_id = project_id
        self.environment_id = environment_id
        self.team_id = team_id
        self._headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        }

    async def _execute_query(self, query: str, variables: dict | None = None) -> dict[str, Any]:
        payload = {"query": query}
        if variables:
            payload["variables"] = variables

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                RAILWAY_GRAPHQL_URL,
                json=payload,
                headers=self._headers,
            )
            response.raise_for_status()
            data = response.json()
            if "errors" in data:
                raise RuntimeError(f"Railway API error: {data['errors']}")
            return data

    async def create_service(self, name: str) -> dict:
        """Create a new service in the Railway project."""
        query = """
        mutation CreateService($projectId: String!, $name: String!, $teamId: String) {
            serviceCreate(
                input: { projectId: $projectId, name: $name, teamId: $teamId }
            ) {
                id
                name
            }
        }
        """
        variables = {
            "projectId": self.project_id,
            "name": name,
            "teamId": self.team_id or None,
        }
        result = await self._execute_query(query, variables)
        return result["data"]["serviceCreate"]

    async def deploy_service(
        self,
        service_id: str,
        image_url: str,
        env_vars: dict[str, str],
    ) -> dict:
        """Trigger a deployment for a service."""
        query = """
        mutation Deploy($serviceId: String!, $environmentId: String!, $input: DeploymentTriggerInput!) {
            deploymentTrigger(
                serviceId: $serviceId
                environmentId: $environmentId
                input: $input
            ) {
                id
            }
        }
        """
        variables = {
            "serviceId": service_id,
            "environmentId": self.environment_id,
            "input": {
                "image": image_url,
                "variables": {k: {"value": v} for k, v in env_vars.items()},
            },
        }
        result = await self._execute_query(query, variables)
        return result["data"]["deploymentTrigger"]

    async def delete_service(self, service_id: str) -> dict:
        """Delete a service and all its deployments."""
        query = """
        mutation DeleteService($serviceId: String!) {
            serviceDelete(id: $serviceId)
        }
        """
        result = await self._execute_query(query, {"serviceId": service_id})
        return result["data"]["serviceDelete"]

    async def get_service_status(self, service_id: str) -> dict:
        """Get current status of a service instance."""
        query = """
        query ServiceStatus($serviceId: String!, $environmentId: String!) {
            service(id: $serviceId) {
                id
                name
                instances {
                    id
                    status
                }
            }
        }
        """
        result = await self._execute_query(query, {
            "serviceId": service_id,
            "environmentId": self.environment_id,
        })
        service = result["data"]["service"]
        instances = service.get("instances", [])
        status = instances[0]["status"] if instances else "STOPPED"
        return {"id": service["id"], "name": service["name"], "status": status}

    async def create_volume(
        self,
        service_id: str,
        name: str,
        mount_path: str,
        size_mb: int,
    ) -> dict:
        """Create a persistent volume for a service."""
        query = """
        mutation CreateVolume($serviceId: String!, $environmentId: String!, $input: VolumeCreateInput!) {
            volumeCreate(
                serviceId: $serviceId
                environmentId: $environmentId
                input: $input
            ) {
                id
                name
            }
        }
        """
        variables = {
            "serviceId": service_id,
            "environmentId": self.environment_id,
            "input": {
                "name": name,
                "mountPath": mount_path,
                "sizeMB": size_mb,
            },
        }
        result = await self._execute_query(query, variables)
        return result["data"]["volumeCreate"]

    async def update_env_var(self, service_id: str, key: str, value: str) -> dict:
        """Update or create an environment variable for a service."""
        query = """
        mutation UpdateVar($serviceId: String!, $environmentId: String!, $input: VariableInput!) {
            variableUpsert(
                serviceId: $serviceId
                environmentId: $environmentId
                input: $input
            ) {
                id
            }
        }
        """
        variables = {
            "serviceId": service_id,
            "environmentId": self.environment_id,
            "input": {"name": key, "value": value},
        }
        result = await self._execute_query(query, variables)
        return result["data"]["variableUpsert"]
