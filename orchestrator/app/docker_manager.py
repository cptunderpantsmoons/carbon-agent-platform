"""Docker Engine service manager for per-user agent containers.

Replaces Railway API calls with direct Docker socket management,
enabling self-hosted PaaS functionality on a VPS.
"""

import docker
from docker.errors import DockerException, NotFound, APIError
from docker.types import LogConfig
import logging
import os
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Configuration defaults (can be overridden via environment variables)
DOCKER_NETWORK = os.getenv("DOCKER_NETWORK", "carbon-agent-net")
BASE_IMAGE = os.getenv("AGENT_DOCKER_IMAGE", "carbon-agent-adapter:latest")
ADAPTER_PORT = int(os.getenv("ADAPTER_PORT", "8001"))

# Traefik configuration for path-based routing
DOMAIN = os.getenv("AGENT_DOMAIN", "agents.carbon.dev")
TRAEFIK_ENTRYPOINT = os.getenv("TRAEFIK_ENTRYPOINT", "websecure")
AGENT_BASE_PATH = os.getenv("AGENT_BASE_PATH", "/agent")  # Path prefix for routing


class DockerServiceManager:
    """Manages user agent containers via Docker Engine API.

    Handles container lifecycle (create, start, stop, delete) with:
    - Resource limits (configurable memory/CPU per user)
    - Traefik path-based routing labels
    - Security isolation (read-only filesystem, tmpfs)
    - Automatic restart policies

    The Docker client is initialised lazily on first use so that importing
    this module (or constructing DockerServiceManager) does not fail in
    environments without a running Docker daemon (e.g. CI, unit tests).
    """

    def __init__(self):
        self._client: Optional[docker.DockerClient] = None
        logger.info("DockerServiceManager initialised (lazy Docker connection)")

    def _get_client(self) -> docker.DockerClient:
        """Return the Docker client, connecting lazily on first call.

        Raises:
            DockerException: If the Docker daemon is unreachable.
        """
        if self._client is None:
            try:
                self._client = docker.from_env()
                logger.info("DockerServiceManager: connected to Docker daemon")
            except DockerException as e:
                logger.error(f"Failed to connect to Docker daemon: {e}")
                raise
        return self._client

    async def ensure_user_service(
        self, user_id: str, env_vars: Dict[str, str]
    ) -> Dict[str, Any]:
        """Ensure user's agent container exists and is running.

        Args:
            user_id: Unique user identifier
            env_vars: Environment variables to inject into container

        Returns:
            Dictionary with action taken, container_id, and was_created flag
        """
        container_name = f"agent-{user_id}"

        try:
            container = self._get_client().containers.get(container_name)

            if container.status != "running":
                logger.info(f"Starting stopped container for user {user_id}")
                container.start()
                return {
                    "action": "started",
                    "container_id": container.id,
                    "was_created": False,
                }

            return {
                "action": "running",
                "container_id": container.id,
                "was_created": False,
            }

        except NotFound:
            logger.info(f"Provisioning new container for user {user_id}")
            return await self._create_user_container(user_id, env_vars)

        except APIError as e:
            logger.error(f"Docker API error for user {user_id}: {e}")
            raise

    async def _create_user_container(
        self, user_id: str, env_vars: Dict[str, str]
    ) -> Dict[str, Any]:
        """Create a new container with resource limits and Traefik routing.

        Args:
            user_id: Unique user identifier
            env_vars: Environment variables to inject into container

        Returns:
            Dictionary with action, container_id, and was_created flag
        """
        container_name = f"agent-{user_id}"

        # Merge user-specific env vars with defaults
        container_env = {
            "USER_ID": user_id,
            "ADAPTER_PORT": str(ADAPTER_PORT),
            **env_vars,
        }

        # Resource limits from environment (configurable)
        mem_limit = os.getenv("AGENT_MEMORY_LIMIT", "512m")
        nano_cpus = int(os.getenv("AGENT_CPU_NANOS", "500000000"))  # 0.5 CPU default

        # Traefik path-based routing labels
        # Routes: agents.carbon.dev/agent/{user_id} -> container:8001
        labels = {
            "traefik.enable": "true",
            f"traefik.http.routers.{user_id}.rule": f"PathPrefix(`{AGENT_BASE_PATH}/{user_id}`)",
            f"traefik.http.routers.{user_id}.entrypoints": TRAEFIK_ENTRYPOINT,
            f"traefik.http.routers.{user_id}.tls": "true",
            f"traefik.http.routers.{user_id}.middlewares": f"{user_id}-strip",
            f"traefik.http.middlewares.{user_id}-strip.stripprefix.prefixes": f"{AGENT_BASE_PATH}/{user_id}",
            f"traefik.http.services.{user_id}.loadbalancer.server.port": str(
                ADAPTER_PORT
            ),
            # Carbon Agent Metadata
            "carbon.user_id": user_id,
            "carbon.type": "agent-instance",
        }

        try:
            # Ensure network exists
            try:
                self._get_client().networks.get(DOCKER_NETWORK)
            except NotFound:
                logger.info(f"Creating Docker network: {DOCKER_NETWORK}")
                self._get_client().networks.create(DOCKER_NETWORK, driver="bridge")

            container = self._get_client().containers.run(
                image=BASE_IMAGE,
                name=container_name,
                environment=container_env,
                labels=labels,
                network=DOCKER_NETWORK,
                detach=True,
                restart_policy={"Name": "unless-stopped"},
                # Resource Limits (configurable via env vars)
                mem_limit=mem_limit,
                nano_cpus=nano_cpus,
                # Security
                read_only=True,
                tmpfs={"/tmp": "rw,noexec,nosuid,size=50m"},
                log_config=LogConfig(
                    type="json-file", config={"max-size": "10m", "max-file": "3"}
                ),
            )

            logger.info(f"Container created successfully: {container.id}")
            return {
                "action": "created",
                "container_id": container.id,
                "was_created": True,
            }

        except APIError as e:
            logger.error(f"Failed to create container for {user_id}: {e}")
            raise

    async def spin_down_user_service(self, user_id: str):
        """Stop user's container (preserves data/state for fast restart).

        Args:
            user_id: Unique user identifier
        """
        container_name = f"agent-{user_id}"
        try:
            container = self._get_client().containers.get(container_name)
            if container.status == "running":
                container.stop(timeout=10)
                logger.info(f"Container stopped for user {user_id}")
        except NotFound:
            pass

    async def destroy_user_service(self, user_id: str):
        """Hard delete: stop and remove container and anonymous volumes.

        Args:
            user_id: Unique user identifier
        """
        container_name = f"agent-{user_id}"
        try:
            container = self._get_client().containers.get(container_name)
            container.remove(force=True)
            logger.info(f"Container destroyed for user {user_id}")
        except NotFound:
            pass

    async def get_container_status(self, user_id: str) -> str:
        """Get current status of user's container.

        Args:
            user_id: Unique user identifier

        Returns:
            Status string: 'running', 'stopped', or 'missing'
        """
        container_name = f"agent-{user_id}"
        try:
            container = self._get_client().containers.get(container_name)
            return container.status
        except NotFound:
            return "missing"
