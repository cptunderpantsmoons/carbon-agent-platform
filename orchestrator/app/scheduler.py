"""Scheduler for platform background tasks.

Manages scheduled background tasks for platform management:
- Service health monitoring
- Usage analytics aggregation
- Audit log cleanup
- Database health checks
"""
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
import structlog

from app.models import User, UserStatus, AuditLog
from app.railway import RailwayClient, get_railway_client
from app.config import get_settings
from app.database import init_db, _session_factory

logger = structlog.get_logger()


class Scheduler:
    """Manages scheduled background tasks for platform management."""

    def __init__(self):
        self._tasks: List[asyncio.Task] = []
        self._running = False

    async def start(self) -> None:
        """Start all scheduled background tasks."""
        if self._running:
            logger.warning("Scheduler already running")
            return

        self._running = True
        logger.info("scheduler_starting")

        self._tasks.append(asyncio.create_task(self._health_monitor_loop()))
        self._tasks.append(asyncio.create_task(self._analytics_loop()))
        self._tasks.append(asyncio.create_task(self._audit_cleanup_loop()))
        self._tasks.append(asyncio.create_task(self._db_health_check_loop()))

        logger.info("scheduler_started", task_count=len(self._tasks))

    async def stop(self) -> None:
        """Stop all scheduled background tasks."""
        if not self._running:
            logger.warning("Scheduler not running")
            return

        self._running = False
        logger.info("scheduler_stopping")

        for task in self._tasks:
            task.cancel()

        # Wait for all tasks to complete cancellation
        if self._tasks:
            results = await asyncio.gather(*self._tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, Exception) and not isinstance(result, asyncio.CancelledError):
                    logger.error("scheduler_task_error_during_stop", error=str(result))

        self._tasks.clear()
        logger.info("scheduler_stopped")

    async def _get_db_session(self) -> AsyncSession:
        """Create and return a new async database session."""
        if _session_factory is None:
            init_db()
        return _session_factory()

    # ─── Service Health Monitor ───────────────────────────────────────────────

    async def _health_monitor_loop(self) -> None:
        """Background task that monitors service health at regular intervals."""
        settings = get_settings()
        interval_seconds = settings.health_check_interval_minutes * 60

        logger.info("health_monitor_loop_started", interval_minutes=settings.health_check_interval_minutes)

        while self._running:
            try:
                await asyncio.sleep(interval_seconds)
                if not self._running:
                    break

                await self._check_service_health()

            except asyncio.CancelledError:
                logger.info("health_monitor_loop_cancelled")
                break
            except Exception as e:
                logger.error("health_monitor_loop_error", error=str(e))
                await asyncio.sleep(60)  # Wait before retrying

    async def _check_service_health(self) -> Dict[str, Any]:
        """Check the health of all active Railway services.

        Returns:
            Summary of health check results
        """
        logger.info("health_check_started")

        db = await self._get_db_session()
        results = {
            "total_services": 0,
            "healthy": 0,
            "unhealthy": 0,
            "unreachable": 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        try:
            # Get all users with active railway services
            result = await db.execute(
                select(User).where(User.railway_service_id.isnot(None))
            )
            users_with_services = result.scalars().all()
            results["total_services"] = len(users_with_services)

            railway_client = await get_railway_client()

            for user in users_with_services:
                try:
                    service = await railway_client.get_service(user.railway_service_id)
                    status = service.get("status", "unknown")

                    if status in ("running", "deployed"):
                        results["healthy"] += 1
                    else:
                        results["unhealthy"] += 1
                        logger.warning(
                            "service_unhealthy",
                            user_id=user.id,
                            service_id=user.railway_service_id,
                            status=status,
                        )
                        # Log alert for unhealthy service
                        await self._create_audit_log_entry(
                            db=db,
                            user_id=user.id,
                            action="service_health_alert",
                            details={
                                "service_id": user.railway_service_id,
                                "status": status,
                                "check_time": datetime.now(timezone.utc).isoformat(),
                            },
                            performed_by="scheduler",
                        )

                except Exception as e:
                    results["unreachable"] += 1
                    logger.error(
                        "service_unreachable",
                        user_id=user.id,
                        service_id=user.railway_service_id,
                        error=str(e),
                    )
                    # Log alert for unreachable service
                    await self._create_audit_log_entry(
                        db=db,
                        user_id=user.id,
                        action="service_unreachable",
                        details={
                            "service_id": user.railway_service_id,
                            "error": str(e),
                            "check_time": datetime.now(timezone.utc).isoformat(),
                        },
                        performed_by="scheduler",
                    )

            await db.commit()
            logger.info("health_check_completed", results=results)

        except Exception as e:
            logger.error("health_check_error", error=str(e))
        finally:
            await db.close()

        return results

    # ─── Usage Analytics Aggregator ───────────────────────────────────────────

    async def _analytics_loop(self) -> None:
        """Background task that aggregates usage metrics at regular intervals."""
        settings = get_settings()
        interval_seconds = settings.analytics_interval_minutes * 60

        logger.info("analytics_loop_started", interval_minutes=settings.analytics_interval_minutes)

        while self._running:
            try:
                await asyncio.sleep(interval_seconds)
                if not self._running:
                    break

                await self._aggregate_usage_analytics()

            except asyncio.CancelledError:
                logger.info("analytics_loop_cancelled")
                break
            except Exception as e:
                logger.error("analytics_loop_error", error=str(e))
                await asyncio.sleep(60)  # Wait before retrying

    async def _aggregate_usage_analytics(self) -> Dict[str, Any]:
        """Aggregate usage metrics for the platform.

        Returns:
            Dictionary of aggregated metrics
        """
        logger.info("analytics_aggregation_started")

        db = await self._get_db_session()
        metrics = {
            "total_users": 0,
            "active_users": 0,
            "inactive_users": 0,
            "active_railway_services": 0,
            "total_audit_logs": 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        try:
            # Total users
            total_result = await db.execute(select(func.count(User.id)))
            metrics["total_users"] = total_result.scalar() or 0

            # Active users (have railway service)
            active_result = await db.execute(
                select(func.count(User.id)).where(User.railway_service_id.isnot(None))
            )
            metrics["active_users"] = active_result.scalar() or 0

            # Inactive users (no railway service)
            metrics["inactive_users"] = metrics["total_users"] - metrics["active_users"]

            # Active Railway services count (same as active users currently)
            metrics["active_railway_services"] = metrics["active_users"]

            # Total audit logs
            audit_result = await db.execute(select(func.count(AuditLog.id)))
            metrics["total_audit_logs"] = audit_result.scalar() or 0

            # Calculate average session duration from audit logs
            # This would ideally come from session tracking, but we can estimate
            # from audit log entries per user
            session_activity_count = await db.execute(
                select(func.count(AuditLog.id)).where(
                    AuditLog.action.in_(["session_start", "session_end"])
                )
            )
            metrics["session_activity_events"] = session_activity_count.scalar() or 0

            # Count service spin-up/spin-down events
            spin_up_count = await db.execute(
                select(func.count(AuditLog.id)).where(AuditLog.action == "service_created")
            )
            spin_down_count = await db.execute(
                select(func.count(AuditLog.id)).where(AuditLog.action == "service_deleted")
            )
            metrics["service_spin_ups"] = spin_up_count.scalar() or 0
            metrics["service_spin_downs"] = spin_down_count.scalar() or 0

            # Store metrics in audit log as daily summary
            await self._create_audit_log_entry(
                db=db,
                user_id=None,
                action="analytics_summary",
                details=metrics,
                performed_by="scheduler",
            )

            await db.commit()
            logger.info("analytics_aggregation_completed", metrics=metrics)

        except Exception as e:
            logger.error("analytics_aggregation_error", error=str(e))
        finally:
            await db.close()

        return metrics

    # ─── Audit Log Cleanup ────────────────────────────────────────────────────

    async def _audit_cleanup_loop(self) -> None:
        """Background task that cleans up old audit logs at regular intervals."""
        settings = get_settings()
        interval_seconds = settings.audit_cleanup_interval_hours * 3600

        logger.info("audit_cleanup_loop_started", interval_hours=settings.audit_cleanup_interval_hours)

        while self._running:
            try:
                await asyncio.sleep(interval_seconds)
                if not self._running:
                    break

                await self._cleanup_old_audit_logs()

            except asyncio.CancelledError:
                logger.info("audit_cleanup_loop_cancelled")
                break
            except Exception as e:
                logger.error("audit_cleanup_loop_error", error=str(e))
                await asyncio.sleep(60)  # Wait before retrying

    async def _cleanup_old_audit_logs(self) -> Dict[str, Any]:
        """Delete audit logs older than the configured retention period.

        Preserves critical logs (user deletions, security events).

        Returns:
            Summary of cleanup results
        """
        logger.info("audit_cleanup_started")

        db = await self._get_db_session()
        settings = get_settings()
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=settings.audit_retention_days)

        results = {
            "cutoff_date": cutoff_date.isoformat(),
            "deleted_count": 0,
            "preserved_count": 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        try:
            # Count logs that will be preserved (critical events)
            critical_actions = [
                "user_deleted",
                "security_event",
                "security_alert",
                "permission_change",
                "api_key_revoked",
                "service_health_alert",
                "service_unreachable",
            ]

            preserved_result = await db.execute(
                select(func.count(AuditLog.id)).where(
                    AuditLog.created_at < cutoff_date,
                    AuditLog.action.in_(critical_actions),
                )
            )
            results["preserved_count"] = preserved_result.scalar() or 0

            # Delete non-critical logs older than retention period
            delete_stmt = (
                AuditLog.__table__  # type: ignore
                .delete()
                .where(
                    AuditLog.created_at < cutoff_date,
                    AuditLog.action.notin_(critical_actions),
                )
            )
            delete_result = await db.execute(delete_stmt)
            results["deleted_count"] = delete_result.rowcount  # type: ignore

            # Log the cleanup action itself (this won't be deleted)
            await self._create_audit_log_entry(
                db=db,
                user_id=None,
                action="audit_log_cleanup",
                details=results,
                performed_by="scheduler",
            )

            await db.commit()
            logger.info("audit_cleanup_completed", results=results)

        except Exception as e:
            logger.error("audit_cleanup_error", error=str(e))
        finally:
            await db.close()

        return results

    # ─── Database Health Check ────────────────────────────────────────────────

    async def _db_health_check_loop(self) -> None:
        """Background task that checks database health at regular intervals."""
        settings = get_settings()
        interval_seconds = settings.db_health_check_interval_minutes * 60

        logger.info(
            "db_health_check_loop_started",
            interval_minutes=settings.db_health_check_interval_minutes,
        )

        while self._running:
            try:
                await asyncio.sleep(interval_seconds)
                if not self._running:
                    break

                await self._check_database_health()

            except asyncio.CancelledError:
                logger.info("db_health_check_loop_cancelled")
                break
            except Exception as e:
                logger.error("db_health_check_loop_error", error=str(e))
                await asyncio.sleep(60)  # Wait before retrying

    async def _check_database_health(self) -> Dict[str, Any]:
        """Check database connection and health status.

        Returns:
            Dictionary of health check results
        """
        logger.info("db_health_check_started")

        db = await self._get_db_session()
        health = {
            "connection_ok": False,
            "database_size_bytes": 0,
            "user_count": 0,
            "audit_log_count": 0,
            "orphaned_users": 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        try:
            # Test connection with a simple query
            try:
                await db.execute(text("SELECT 1"))
                health["connection_ok"] = True
            except Exception as e:
                health["connection_error"] = str(e)
                logger.error("db_connection_failed", error=str(e))

            # Check database size (PostgreSQL-specific)
            try:
                size_result = await db.execute(
                    text("SELECT pg_database_size(current_database())")
                )
                health["database_size_bytes"] = size_result.scalar() or 0
            except Exception as e:
                logger.warning("db_size_check_failed", error=str(e))

            # Count users
            user_result = await db.execute(select(func.count(User.id)))
            health["user_count"] = user_result.scalar() or 0

            # Count audit logs
            audit_result = await db.execute(select(func.count(AuditLog.id)))
            health["audit_log_count"] = audit_result.scalar() or 0

            # Check for orphaned records: users with deleted services
            # (status is ACTIVE but railway_service_id is null)
            orphaned_result = await db.execute(
                select(func.count(User.id)).where(
                    User.status == UserStatus.ACTIVE,
                    User.railway_service_id.is_(None),
                )
            )
            health["orphaned_users"] = orphaned_result.scalar() or 0

            if health["orphaned_users"] > 0:
                logger.warning(
                    "orphaned_users_detected",
                    count=health["orphaned_users"],
                    description="Users marked as ACTIVE but without railway services",
                )

            # Log health status
            await self._create_audit_log_entry(
                db=db,
                user_id=None,
                action="db_health_check",
                details=health,
                performed_by="scheduler",
            )

            await db.commit()
            logger.info("db_health_check_completed", health=health)

        except Exception as e:
            logger.error("db_health_check_error", error=str(e))
        finally:
            await db.close()

        return health

    # ─── Helper Methods ───────────────────────────────────────────────────────

    async def _create_audit_log_entry(
        self,
        db: AsyncSession,
        user_id: Optional[str],
        action: str,
        details: Optional[Dict[str, Any]],
        performed_by: str,
    ) -> None:
        """Create an audit log entry.

        Args:
            db: Database session
            user_id: User ID (optional for system actions)
            action: Action type
            details: Action details
            performed_by: Who performed the action
        """
        import uuid

        log_entry = AuditLog(
            id=str(uuid.uuid4()),
            user_id=user_id,
            action=action,
            details=details,
            performed_by=performed_by,
            created_at=datetime.now(timezone.utc),
        )
        db.add(log_entry)

    def get_task_count(self) -> int:
        """Get the number of active background tasks.

        Returns:
            Number of running tasks
        """
        return len(self._tasks)

    def is_running(self) -> bool:
        """Check if the scheduler is running.

        Returns:
            True if scheduler is running
        """
        return self._running


# Singleton instance
_scheduler: Optional[Scheduler] = None


def get_scheduler() -> Scheduler:
    """Get or create the singleton Scheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = Scheduler()
    return _scheduler
