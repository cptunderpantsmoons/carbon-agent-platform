"""Session manager for handling Railway service lifecycle and user sessions."""
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import structlog

from app.models import User, UserStatus
from app.railway import RailwayClient, get_railway_client
from app.config import get_settings
from app.database import init_db, _session_factory

logger = structlog.get_logger()


class SessionManager:
    """Manages user sessions and Railway service lifecycle."""

    def __init__(self):
        self._active_sessions: Dict[str, datetime] = {}  # user_id -> last_activity
        self._spin_locks: Dict[str, asyncio.Lock] = {}  # user_id -> lock
        self._cleanup_task: Optional[asyncio.Task] = None

    async def start_cleanup_task(self) -> None:
        """Start the background cleanup task for idle sessions."""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_idle_sessions())
            logger.info("Session manager cleanup task started")

    async def stop_cleanup_task(self) -> None:
        """Stop the background cleanup task."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
            logger.info("Session manager cleanup task stopped")

    def _get_lock(self, user_id: str) -> asyncio.Lock:
        """Get or create a lock for a user's session operations."""
        if user_id not in self._spin_locks:
            self._spin_locks[user_id] = asyncio.Lock()
        return self._spin_locks[user_id]

    def _remove_lock(self, user_id: str) -> None:
        """Remove a user's lock when no longer needed."""
        if user_id in self._spin_locks:
            del self._spin_locks[user_id]

    async def ensure_user_service(
        self,
        db: AsyncSession,
        user_id: str,
    ) -> tuple[bool, Optional[str]]:
        """Ensure the user has an active Railway service.

        Args:
            db: Database session
            user_id: User ID to ensure service for

        Returns:
            Tuple of (was_created, service_url)
        """
        lock = self._get_lock(user_id)

        async with lock:
            try:
                # Update last activity
                self._active_sessions[user_id] = datetime.now(timezone.utc)

                # Get user from database
                result = await db.execute(select(User).where(User.id == user_id))
                user = result.scalar_one_or_none()

                if not user:
                    logger.error("user_not_found", user_id=user_id)
                    return False, None

                # Check if user already has a service
                if user.railway_service_id:
                    logger.info("user_already_has_service", user_id=user_id, service_id=user.railway_service_id)
                    return False, None

                # Spin up new service
                logger.info("spinning_up_service", user_id=user_id)
                await self._spin_up_service(db, user, user_id)
                await db.commit()

                return True, None

            except Exception as e:
                logger.error("ensure_user_service_error", user_id=user_id, error=str(e))
                raise

    async def _spin_up_service(
        self,
        db: AsyncSession,
        user: User,
        user_id: str,
    ) -> None:
        """Spin up a Railway service for a user.

        Args:
            db: Database session
            user: User object
            user_id: User ID

        Raises:
            Exception: If service creation fails
        """
        settings = get_settings()
        railway_client = await get_railway_client()

        created_volume_id = None
        created_service_id = None

        try:
            # Create volume for persistent storage
            volume_name = f"user-{user_id}-volume"
            volume_response = await railway_client.create_volume(
                name=volume_name,
                size_gb=settings.volume_size_gb,
                mount_path=settings.volume_mount_path,
            )
            volume_id = volume_response["id"]
            created_volume_id = volume_id
            logger.info(f"Created volume {volume_id} for user {user_id}")

            # Create service
            service_name = f"user-{user_id}-service"
            service_response = await railway_client.create_service(
                name=service_name,
                docker_image=settings.agent_docker_image,
                memory=settings.agent_default_memory,
                cpu=settings.agent_default_cpu,
                volume_id=volume_id,
            )
            service_id = service_response["id"]
            created_service_id = service_id
            logger.info(f"Created service {service_id} for user {user_id}")

            # Create deployment with environment variables
            env_vars = {
                "USER_ID": user_id,
                "API_KEY": user.api_key,
                "DISPLAY_NAME": user.display_name,
            }

            deployment_response = await railway_client.create_deployment(
                service_id=service_id,
                docker_image=settings.agent_docker_image,
                env_vars=env_vars,
            )
            deployment_id = deployment_response["id"]
            logger.info(f"Created deployment {deployment_id} for service {service_id}")

            # Update user with service and volume IDs
            user.railway_service_id = service_id
            user.volume_id = volume_id
            user.status = UserStatus.ACTIVE
            user.updated_at = datetime.now(timezone.utc)

            logger.info(f"Successfully spun up service {service_id} for user {user_id}")

        except Exception as e:
            logger.error(f"Failed to spin up service for user {user_id}: {e}")
            # Cleanup any partially created resources
            if created_service_id:
                try:
                    await railway_client.delete_service(created_service_id)
                    logger.info(f"Cleaned up service {created_service_id}")
                except Exception as cleanup_error:
                    logger.error(f"Failed to cleanup service {created_service_id}: {cleanup_error}")

            if created_volume_id:
                try:
                    await railway_client.delete_volume(created_volume_id)
                    logger.info(f"Cleaned up volume {created_volume_id}")
                except Exception as cleanup_error:
                    logger.error(f"Failed to cleanup volume {created_volume_id}: {cleanup_error}")

            raise

    async def spin_down_user_service(
        self,
        db: AsyncSession,
        user_id: str,
    ) -> bool:
        """Spin down a user's Railway service.

        Args:
            db: Database session
            user_id: User ID to spin down service for

        Returns:
            True if service was spun down, False if user had no service
        """
        lock = self._get_lock(user_id)

        async with lock:
            try:
                # Get user from database
                result = await db.execute(select(User).where(User.id == user_id))
                user = result.scalar_one_or_none()

                if not user:
                    logger.error(f"User not found: {user_id}")
                    return False

                if not user.railway_service_id:
                    logger.info(f"User {user_id} has no service to spin down")
                    return False

                await self._spin_down_service(db, user, user_id)
                await db.commit()

                # Remove from active sessions
                if user_id in self._active_sessions:
                    del self._active_sessions[user_id]

                return True

            except Exception as e:
                logger.error(f"Error spinning down service for {user_id}: {e}")
                raise
            finally:
                self._remove_lock(user_id)

    async def _spin_down_service(
        self,
        db: AsyncSession,
        user: User,
        user_id: str,
    ) -> None:
        """Spin down a Railway service for a user.

        Args:
            db: Database session
            user: User object
            user_id: User ID

        Raises:
            Exception: If service deletion fails
        """
        railway_client = await get_railway_client()

        try:
            service_id = user.railway_service_id
            volume_id = user.volume_id

            # Delete service
            if service_id:
                logger.info(f"Deleting service {service_id} for user {user_id}")
                await railway_client.delete_service(service_id)

            # Delete volume (optionally - for now we delete it)
            if volume_id:
                logger.info(f"Deleting volume {volume_id} for user {user_id}")
                await railway_client.delete_volume(volume_id)

            # Update user record
            user.railway_service_id = None
            user.volume_id = None
            user.status = UserStatus.PENDING
            user.updated_at = datetime.now(timezone.utc)

            logger.info(f"Successfully spun down service for user {user_id}")

        except Exception as e:
            logger.error(f"Failed to spin down service for user {user_id}: {e}")
            raise

    async def record_activity(self, user_id: str) -> None:
        """Record user activity to prevent session timeout.

        Args:
            user_id: User ID to record activity for
        """
        self._active_sessions[user_id] = datetime.now(timezone.utc)

    async def get_service_status(
        self,
        db: AsyncSession,
        user_id: str,
    ) -> Optional[Dict]:
        """Get the status of a user's Railway service.

        Args:
            db: Database session
            user_id: User ID to check service status for

        Returns:
            Service status dictionary or None if no service
        """
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if not user or not user.railway_service_id:
            return None

        railway_client = await get_railway_client()

        try:
            service = await railway_client.get_service(user.railway_service_id)
            return {
                "service_id": user.railway_service_id,
                "volume_id": user.volume_id,
                "status": service.get("status"),
                "updated_at": service.get("updatedAt"),
                "instances": service.get("serviceInstances", []),
            }
        except Exception as e:
            logger.error(f"Error getting service status for {user_id}: {e}")
            return None

    async def _get_db_session(self) -> AsyncSession:
        """Create and return a new async database session.

        This method is used by the cleanup task which operates independently
        of request lifecycle and cannot receive injected sessions.

        Returns:
            A new AsyncSession instance
        """
        if _session_factory is None:
            init_db()
        return _session_factory()

    async def spin_down_idle_user(self, user_id: str) -> bool:
        """Spin down an idle user's Railway service.

        Creates its own database session since the cleanup task runs
        independently of request lifecycle.

        Args:
            user_id: User ID to spin down service for

        Returns:
            True if service was spun down, False otherwise
        """
        db = await self._get_db_session()
        try:
            # Get user from database
            result = await db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()

            if not user:
                logger.error(f"User not found during idle cleanup: {user_id}")
                return False

            if not user.railway_service_id:
                logger.info(f"User {user_id} has no service to spin down during idle cleanup")
                # Still remove from active sessions since they have no service
                if user_id in self._active_sessions:
                    del self._active_sessions[user_id]
                return False

            await self._spin_down_service(db, user, user_id)
            await db.commit()

            # Remove from active sessions
            if user_id in self._active_sessions:
                del self._active_sessions[user_id]

            logger.info(f"Successfully spun down idle user {user_id}")
            return True

        except Exception as e:
            logger.error(f"Error spinning down idle user {user_id}: {e}")
            return False
        finally:
            await db.close()

    async def _cleanup_idle_sessions(self) -> None:
        """Background task to clean up idle sessions."""
        settings = get_settings()
        idle_timeout = timedelta(minutes=settings.session_idle_timeout_minutes)

        while True:
            try:
                await asyncio.sleep(60)  # Check every minute

                current_time = datetime.now(timezone.utc)
                idle_users = []

                # Find idle users
                for user_id, last_activity in list(self._active_sessions.items()):
                    idle_time = current_time - last_activity
                    if idle_time > idle_timeout:
                        idle_users.append(user_id)

                # Spin down services for idle users
                for user_id in idle_users:
                    try:
                        logger.info(f"User {user_id} idle, spinning down service")
                        await self.spin_down_idle_user(user_id)
                    except Exception as e:
                        # Log error but continue processing other users
                        logger.error(f"Failed to spin down idle user {user_id}: {e}")

            except asyncio.CancelledError:
                logger.info("Cleanup task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in cleanup task: {e}")
                await asyncio.sleep(60)  # Wait before retrying

    async def get_active_session_count(self) -> int:
        """Get the number of currently active sessions.

        Returns:
            Number of active sessions
        """
        return len(self._active_sessions)

    async def get_session_info(self, user_id: str) -> Optional[Dict]:
        """Get information about a user's session.

        Args:
            user_id: User ID to get session info for

        Returns:
            Session info dictionary or None if no active session
        """
        if user_id not in self._active_sessions:
            return None

        last_activity = self._active_sessions[user_id]
        settings = get_settings()
        idle_timeout = timedelta(minutes=settings.session_idle_timeout_minutes)

        return {
            "user_id": user_id,
            "last_activity": last_activity,
            "idle_seconds": (datetime.now(timezone.utc) - last_activity).total_seconds(),
            "timeout_seconds": idle_timeout.total_seconds(),
        }


# Singleton instance for use across the application
_session_manager: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    """Get or create the singleton SessionManager instance."""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager