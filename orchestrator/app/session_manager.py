"""Session manager for handling Docker container lifecycle and user sessions."""
import asyncio
import weakref
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import structlog

from app.models import User, UserStatus
from app.docker_manager import DockerServiceManager
from app.config import get_settings
from app.database import create_session

logger = structlog.get_logger()


class SessionManager:
    """Manages user sessions and Docker container lifecycle."""

    def __init__(self):
        self._active_sessions: Dict[str, datetime] = {}  # user_id -> last_activity
        # WeakValueDictionary: locks are GC'd automatically when no coroutine holds
        # a strong reference, eliminating the remove-then-recreate race condition.
        self._spin_locks: weakref.WeakValueDictionary[str, asyncio.Lock] = (
            weakref.WeakValueDictionary()
        )
        self._cleanup_task: Optional[asyncio.Task] = None
        self.docker_manager = DockerServiceManager()

    async def start_cleanup_task(self) -> None:
        """Start the background cleanup task for idle sessions."""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_idle_sessions())
            logger.info("session_cleanup_task_started")

    async def stop_cleanup_task(self) -> None:
        """Stop the background cleanup task."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
            logger.info("session_cleanup_task_stopped")

    def _get_lock(self, user_id: str) -> asyncio.Lock:
        """Get or create a lock for a user's session operations.

        Returns the existing lock if one is alive, otherwise creates a new one.
        The caller MUST hold a strong reference to the returned lock for the
        duration of the critical section — WeakValueDictionary only keeps a
        weak reference, so the lock will be GC'd when there are no other refs.
        """
        lock = self._spin_locks.get(user_id)
        if lock is None:
            lock = asyncio.Lock()
            self._spin_locks[user_id] = lock
        return lock

    async def ensure_user_service(
        self,
        db: AsyncSession,
        user_id: str,
    ) -> tuple[bool, Optional[str]]:
        """Ensure the user has an active Docker container.

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
                if user.status == UserStatus.ACTIVE:
                    logger.info(
                        "user_already_has_service",
                        user_id=user_id,
                    )
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
        """Spin up a Docker container for a user.

        Calls DockerManager to create and start the container with
        resource limits and Traefik routing labels.

        Args:
            db: Database session
            user: User object
            user_id: User ID

        Raises:
            Exception: If container creation fails
        """
        env_vars = {
            "USER_ID": user_id,
            "API_KEY": user.api_key,
            "DISPLAY_NAME": user.display_name,
        }

        try:
            result = await self.docker_manager.ensure_user_service(user_id, env_vars)
            logger.info(
                "container_created",
                container_id=result["container_id"],
                user_id=user_id,
            )

            # Update user status
            user.status = UserStatus.ACTIVE

            logger.info("service_spinup_complete", user_id=user_id)

        except Exception as e:
            logger.error("service_spinup_failed", user_id=user_id, error=str(e))
            raise

    async def spin_down_user_service(
        self,
        db: AsyncSession,
        user_id: str,
    ) -> bool:
        """Spin down a user's Docker container.

        Args:
            db: Database session
            user_id: User ID to spin down service for

        Returns:
            True if service was spun down, False if user had no service
        """
        lock = self._get_lock(user_id)

        async with lock:
            try:
                result = await db.execute(select(User).where(User.id == user_id))
                user = result.scalar_one_or_none()

                if not user:
                    logger.error("spin_down_user_not_found", user_id=user_id)
                    return False

                if user.status != UserStatus.ACTIVE:
                    logger.info("spin_down_no_service", user_id=user_id)
                    return False

                await self._spin_down_service(db, user, user_id)
                await db.commit()

                if user_id in self._active_sessions:
                    del self._active_sessions[user_id]

                return True

            except Exception as e:
                logger.error("spin_down_error", user_id=user_id, error=str(e))
                raise
            # No finally/_remove_lock: WeakValueDictionary handles cleanup automatically

    async def _spin_down_service(
        self,
        db: AsyncSession,
        user: User,
        user_id: str,
    ) -> None:
        """Stop and remove the Docker container for a user.

        Args:
            db: Database session
            user: User object
            user_id: User ID

        Raises:
            Exception: If container deletion fails
        """
        try:
            logger.info("stopping_container", user_id=user_id)
            await self.docker_manager.spin_down_user_service(user_id)

            user.status = UserStatus.PENDING

            logger.info("service_spindown_complete", user_id=user_id)

        except Exception as e:
            logger.error("service_spindown_failed", user_id=user_id, error=str(e))
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
        """Get the status of a user's Docker container.

        Args:
            db: Database session
            user_id: User ID to check service status for

        Returns:
            Service status dictionary or None if no service
        """
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if not user or user.status != UserStatus.ACTIVE:
            return None

        try:
            container_status = await self.docker_manager.get_container_status(user_id)
            
            return {
                "user_id": user_id,
                "status": container_status,
                "service_url": f"https://{get_settings().agent_domain}/agent/{user_id}",
            }
        except Exception as e:
            logger.error("get_service_status_error", user_id=user_id, error=str(e))
            return None

    async def _get_db_session(self) -> AsyncSession:
        """Create and return a new async database session.

        Used by the cleanup task which operates independently of request
        lifecycle. Delegates to database.create_session().
        """
        return create_session()

    async def provision_user_background(self, user_id: str) -> bool:
        """Provision a Docker container for a newly registered user.

        Designed to run as a fire-and-forget background task from the Clerk
        webhook handler so the webhook response returns immediately. Creates
        its own database session (independent of the webhook request lifecycle).

        Idempotent: safe to call even if the user already has a service.

        Args:
            user_id: Platform user ID to provision a container for.

        Returns:
            True if a new container was provisioned, False if already existed.

        Raises:
            Exception: Re-raised so asyncio.create_task logs the exception.
        """
        db = create_session()
        try:
            logger.info("starting_user_provisioning", user_id=user_id)
            was_created, _ = await self.ensure_user_service(db, user_id)

            if was_created:
                logger.info("user_provisioned_successfully", user_id=user_id)
            else:
                logger.info("user_already_had_service", user_id=user_id)

            return was_created
        except Exception as e:
            logger.error(
                "user_provisioning_failed",
                user_id=user_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise  # Re-raise so asyncio.create_task logs the exception
        finally:
            await db.close()

    async def spin_down_idle_user(self, user_id: str) -> bool:
        """Spin down an idle user's Docker container.

        Creates its own database session since the cleanup task runs
        independently of request lifecycle.

        Args:
            user_id: User ID to spin down service for

        Returns:
            True if service was spun down, False otherwise
        """
        db = await self._get_db_session()
        try:
            result = await db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()

            if not user:
                logger.error("idle_cleanup_user_not_found", user_id=user_id)
                return False

            if user.status != UserStatus.ACTIVE:
                logger.info("idle_cleanup_no_service", user_id=user_id)
                if user_id in self._active_sessions:
                    del self._active_sessions[user_id]
                return False

            await self._spin_down_service(db, user, user_id)
            await db.commit()

            if user_id in self._active_sessions:
                del self._active_sessions[user_id]

            logger.info("idle_user_spun_down", user_id=user_id)
            return True

        except Exception as e:
            logger.error("idle_spindown_error", user_id=user_id, error=str(e))
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
                idle_users = [
                    uid
                    for uid, last_activity in list(self._active_sessions.items())
                    if (current_time - last_activity) > idle_timeout
                ]

                for user_id in idle_users:
                    try:
                        logger.info("user_idle_spinning_down", user_id=user_id)
                        await self.spin_down_idle_user(user_id)
                    except Exception as e:
                        logger.error("idle_spindown_loop_error", user_id=user_id, error=str(e))

            except asyncio.CancelledError:
                logger.info("session_cleanup_task_cancelled")
                break
            except Exception as e:
                logger.error("session_cleanup_loop_error", error=str(e))
                await asyncio.sleep(60)  # Back off before retrying

    async def get_active_session_count(self) -> int:
        """Get the number of currently active sessions."""
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
