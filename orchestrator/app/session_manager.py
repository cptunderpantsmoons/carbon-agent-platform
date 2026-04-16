"""Manages agent session lifecycle: spin up, spin down, idle detection."""
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any

import structlog

logger = structlog.get_logger()


class SessionManager:
    """Handles Railway service lifecycle for per-user agent instances."""

    def __init__(self, railway_client, settings):
        self.railway = railway_client
        self.settings = settings

    async def spin_up(self, user) -> dict[str, Any]:
        """Spin up a new agent instance for a user.

        Creates Railway service, optional volume (if not exists), and triggers deployment.
        Returns dict with service_id, volume_id, deployment_id.
        """
        service_name = f"agent-{user.id}"

        logger.info("spinning_up_agent", user_id=user.id, service_name=service_name)

        # 1. Create Railway service
        service = await self.railway.create_service(service_name)
        service_id = service["id"]

        # 2. Create volume only if user doesn't already have one
        volume_id = user.volume_id
        if not volume_id:
            volume_name = f"data-{user.id}"
            volume = await self.railway.create_volume(
                service_id=service_id,
                name=volume_name,
                mount_path=self.settings.volume_mount_path,
                size_mb=self.settings.volume_size_gb * 1024,
            )
            volume_id = volume["id"]
            logger.info("volume_created", volume_id=volume_id, user_id=user.id)

        # 3. Set environment variables
        env_vars = {
            "USER_ID": user.id,
            "USER_EMAIL": user.email,
            "USER_CONFIG": str(user.config or {}),
            "VOLUME_MOUNT_PATH": self.settings.volume_mount_path,
        }

        # 4. Deploy the adapter image
        deployment = await self.railway.deploy_service(
            service_id=service_id,
            image_url=self.settings.agent_docker_image,
            env_vars=env_vars,
        )

        logger.info("agent_deployed", service_id=service_id, deployment_id=deployment["id"])

        return {
            "service_id": service_id,
            "volume_id": volume_id,
            "deployment_id": deployment["id"],
        }

    async def spin_down(self, service_id: str) -> dict[str, Any]:
        """Spin down an agent instance, deleting the service but preserving the volume.

        Volumes are preserved for data persistence across spin-up/down cycles.
        """
        logger.info("spinning_down_agent", service_id=service_id)

        result = await self.railway.delete_service(service_id)

        logger.info("agent_stopped", service_id=service_id, result=result)
        return result

    def is_idle(self, session, now: datetime | None = None) -> bool:
        """Check if a session has exceeded the idle timeout."""
        if now is None:
            now = datetime.now(timezone.utc)

        if session.last_activity_at is None:
            return True

        timeout = timedelta(minutes=self.settings.session_idle_timeout_minutes)
        return (now - session.last_activity_at) > timeout

    async def check_health(self, service_id: str) -> dict[str, Any]:
        """Check the health of a running agent instance."""
        status = await self.railway.get_service_status(service_id)
        return {
            "service_id": service_id,
            "status": status.get("status", "UNKNOWN"),
            "healthy": status.get("status") == "ACTIVE",
        }
