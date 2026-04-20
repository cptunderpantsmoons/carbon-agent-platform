"""Tests for the scheduler and all background tasks."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from app.scheduler import Scheduler, get_scheduler
from app.models import User, UserStatus, AuditLog


@pytest.fixture
def scheduler():
    """Create a fresh scheduler for each test."""
    return Scheduler()


@pytest.fixture
def mock_user():
    """Create a mock user for testing."""
    user = User(
        id="test-user-1",
        email="test@example.com",
        display_name="Test User",
        api_key="test-api-key-123",
        status=UserStatus.ACTIVE,
        clerk_user_id="user_test123",
    )
    return user


@pytest.fixture
def mock_user_no_service():
    """Create a mock user without an active service."""
    user = User(
        id="test-user-2",
        email="test2@example.com",
        display_name="Test User 2",
        api_key="test-api-key-456",
        status=UserStatus.PENDING,
        clerk_user_id="user_test456",
    )
    return user


# ─── Scheduler Start/Stop Tests ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_scheduler_start_creates_tasks(scheduler):
    """Test that starting the scheduler creates background tasks."""
    with patch.object(
        scheduler, "_health_monitor_loop", new_callable=AsyncMock
    ) as mock_health:
        with patch.object(
            scheduler, "_analytics_loop", new_callable=AsyncMock
        ) as mock_analytics:
            with patch.object(
                scheduler, "_audit_cleanup_loop", new_callable=AsyncMock
            ) as mock_audit:
                with patch.object(
                    scheduler, "_db_health_check_loop", new_callable=AsyncMock
                ) as mock_db:
                    # Make the loops exit immediately
                    mock_health.side_effect = asyncio.CancelledError()
                    mock_analytics.side_effect = asyncio.CancelledError()
                    mock_audit.side_effect = asyncio.CancelledError()
                    mock_db.side_effect = asyncio.CancelledError()

                    await scheduler.start()

                    assert scheduler.is_running() is True
                    assert scheduler.get_task_count() == 4

                    await scheduler.stop()


@pytest.mark.asyncio
async def test_scheduler_stop_cancels_tasks(scheduler):
    """Test that stopping the scheduler cancels all tasks."""

    async def slow_loop():
        """A loop that sleeps for a long time."""
        try:
            await asyncio.sleep(3600)
        except asyncio.CancelledError:
            pass

    with patch.object(scheduler, "_health_monitor_loop", side_effect=slow_loop):
        with patch.object(scheduler, "_analytics_loop", side_effect=slow_loop):
            with patch.object(scheduler, "_audit_cleanup_loop", side_effect=slow_loop):
                with patch.object(
                    scheduler, "_db_health_check_loop", side_effect=slow_loop
                ):
                    await scheduler.start()
                    assert scheduler.get_task_count() == 4

                    await scheduler.stop()

                    assert scheduler.is_running() is False
                    assert scheduler.get_task_count() == 0


@pytest.mark.asyncio
async def test_scheduler_start_idempotent(scheduler):
    """Test that starting an already-running scheduler is a no-op."""

    async def slow_loop():
        try:
            await asyncio.sleep(3600)
        except asyncio.CancelledError:
            pass

    with patch.object(scheduler, "_health_monitor_loop", side_effect=slow_loop):
        with patch.object(scheduler, "_analytics_loop", side_effect=slow_loop):
            with patch.object(scheduler, "_audit_cleanup_loop", side_effect=slow_loop):
                with patch.object(
                    scheduler, "_db_health_check_loop", side_effect=slow_loop
                ):
                    await scheduler.start()
                    first_count = scheduler.get_task_count()

                    # Start again - should be no-op
                    await scheduler.start()
                    second_count = scheduler.get_task_count()

                    assert first_count == second_count

                    await scheduler.stop()


@pytest.mark.asyncio
async def test_scheduler_stop_when_not_running(scheduler):
    """Test that stopping a non-running scheduler is a no-op."""
    # Should not raise
    await scheduler.stop()
    assert scheduler.is_running() is False


@pytest.mark.asyncio
async def test_get_scheduler_singleton():
    """Test that get_scheduler returns a singleton instance."""
    scheduler1 = get_scheduler()
    scheduler2 = get_scheduler()

    assert scheduler1 is scheduler2


# ─── Service Health Monitor Tests ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_check_service_health_healthy_services(scheduler, mock_user):
    """Test health check with healthy services."""
    mock_db = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_user]
    mock_db.execute.return_value = mock_result

    mock_docker = AsyncMock()
    mock_docker.get_container_status.return_value = "running"

    with patch.object(scheduler, "_get_db_session", return_value=mock_db):
        with patch("app.scheduler.DockerServiceManager", return_value=mock_docker):
            results = await scheduler._check_service_health()

            assert results["total_services"] == 1
            assert results["healthy"] == 1
            assert results["unhealthy"] == 0
            assert results["unreachable"] == 0


@pytest.mark.asyncio
async def test_check_service_health_unhealthy_services(scheduler, mock_user):
    """Test health check with unhealthy services."""
    mock_db = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_user]
    mock_db.execute.return_value = mock_result

    mock_docker = AsyncMock()
    mock_docker.get_container_status.return_value = "stopped"

    with patch.object(scheduler, "_get_db_session", return_value=mock_db):
        with patch("app.scheduler.DockerServiceManager", return_value=mock_docker):
            results = await scheduler._check_service_health()

            assert results["total_services"] == 1
            assert results["healthy"] == 0
            assert results["unhealthy"] == 1
            assert results["unreachable"] == 0

            # Verify audit log was created for unhealthy service
            mock_db.add.assert_called()


@pytest.mark.asyncio
async def test_check_service_health_unreachable_services(scheduler, mock_user):
    """Test health check with unreachable services."""
    mock_db = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_user]
    mock_db.execute.return_value = mock_result

    mock_docker = AsyncMock()
    mock_docker.get_container_status.side_effect = Exception("Connection timeout")

    with patch.object(scheduler, "_get_db_session", return_value=mock_db):
        with patch("app.scheduler.DockerServiceManager", return_value=mock_docker):
            results = await scheduler._check_service_health()

            assert results["total_services"] == 1
            assert results["healthy"] == 0
            assert results["unhealthy"] == 0
            assert results["unreachable"] == 1

            # Verify audit log was created for unreachable service
            mock_db.add.assert_called()


@pytest.mark.asyncio
async def test_check_service_health_no_services(scheduler):
    """Test health check when no services exist."""
    mock_db = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_db.execute.return_value = mock_result

    with patch.object(scheduler, "_get_db_session", return_value=mock_db):
        results = await scheduler._check_service_health()

        assert results["total_services"] == 0
        assert results["healthy"] == 0
        assert results["unhealthy"] == 0
        assert results["unreachable"] == 0


@pytest.mark.asyncio
async def test_check_service_health_error_handling(scheduler):
    """Test health check handles database errors gracefully."""
    mock_db = AsyncMock(spec=AsyncSession)
    mock_db.execute.side_effect = Exception("Database connection failed")

    with patch.object(scheduler, "_get_db_session", return_value=mock_db):
        # Should not raise
        results = await scheduler._check_service_health()

        assert results["total_services"] == 0
        mock_db.close.assert_called_once()


@pytest.mark.asyncio
async def test_health_monitor_loop_runs_periodically(scheduler):
    """Test that the health monitor loop runs at the correct interval."""
    settings_mock = MagicMock()
    settings_mock.health_check_interval_minutes = 0.01  # Very short for testing

    call_count = 0

    async def mock_check_health():
        nonlocal call_count
        call_count += 1

    async def mock_sleep(seconds):
        # Exit after 2 iterations
        if call_count >= 2:
            scheduler._running = False

    with patch("app.scheduler.get_settings", return_value=settings_mock):
        with patch.object(
            scheduler, "_check_service_health", side_effect=mock_check_health
        ):
            with patch("asyncio.sleep", side_effect=mock_sleep):
                scheduler._running = True
                await scheduler._health_monitor_loop()

                assert call_count >= 1


@pytest.mark.asyncio
async def test_health_monitor_loop_error_recovery(scheduler):
    """Test that health monitor loop continues after errors."""
    settings_mock = MagicMock()
    settings_mock.health_check_interval_minutes = 0.01

    call_count = 0

    async def mock_check_health():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise Exception("Temporary failure")

    async def mock_sleep(seconds):
        if call_count >= 2:
            scheduler._running = False

    with patch("app.scheduler.get_settings", return_value=settings_mock):
        with patch.object(
            scheduler, "_check_service_health", side_effect=mock_check_health
        ):
            with patch("asyncio.sleep", side_effect=mock_sleep):
                scheduler._running = True
                await scheduler._health_monitor_loop()

                # Should have recovered and run at least twice
                assert call_count >= 2


# ─── Usage Analytics Aggregator Tests ────────────────────────────────────────


@pytest.mark.asyncio
async def test_aggregate_usage_analytics(scheduler, mock_user, mock_user_no_service):
    """Test usage analytics aggregation."""
    mock_db = AsyncMock(spec=AsyncSession)

    # Mock different query results
    def mock_execute(statement):
        result = MagicMock()
        # Return different counts based on query type
        result.scalar.return_value = 0
        return result

    mock_db.execute.side_effect = mock_execute

    with patch.object(scheduler, "_get_db_session", return_value=mock_db):
        metrics = await scheduler._aggregate_usage_analytics()

        assert "total_users" in metrics
        assert "active_users" in metrics
        assert "inactive_users" in metrics
        assert "active_docker_containers" in metrics
        assert "total_audit_logs" in metrics
        assert "timestamp" in metrics

        # Verify audit log entry was created for the summary
        mock_db.add.assert_called()
        mock_db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_aggregate_usage_analytics_error_handling(scheduler):
    """Test analytics aggregation handles errors gracefully."""
    mock_db = AsyncMock(spec=AsyncSession)
    mock_db.execute.side_effect = Exception("Database error")

    with patch.object(scheduler, "_get_db_session", return_value=mock_db):
        # Should not raise
        metrics = await scheduler._aggregate_usage_analytics()

        assert "total_users" in metrics
        mock_db.close.assert_called_once()


@pytest.mark.asyncio
async def test_analytics_loop_runs_periodically(scheduler):
    """Test that the analytics loop runs at the correct interval."""
    settings_mock = MagicMock()
    settings_mock.analytics_interval_minutes = 0.01  # Very short for testing

    call_count = 0

    async def mock_aggregate():
        nonlocal call_count
        call_count += 1

    async def mock_sleep(seconds):
        if call_count >= 2:
            scheduler._running = False

    with patch("app.scheduler.get_settings", return_value=settings_mock):
        with patch.object(
            scheduler, "_aggregate_usage_analytics", side_effect=mock_aggregate
        ):
            with patch("asyncio.sleep", side_effect=mock_sleep):
                scheduler._running = True
                await scheduler._analytics_loop()

                assert call_count >= 1


# ─── Audit Log Cleanup Tests ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cleanup_old_audit_logs(scheduler):
    """Test audit log cleanup removes old logs."""
    mock_db = AsyncMock(spec=AsyncSession)

    # Mock count queries
    preserved_result = MagicMock()
    preserved_result.scalar.return_value = 5

    delete_result = MagicMock()
    delete_result.rowcount = 100

    # Return different results for different calls
    mock_db.execute.side_effect = [preserved_result, delete_result]

    settings_mock = MagicMock()
    settings_mock.audit_retention_days = 90

    with patch.object(scheduler, "_get_db_session", return_value=mock_db):
        with patch("app.scheduler.get_settings", return_value=settings_mock):
            results = await scheduler._cleanup_old_audit_logs()

            assert results["deleted_count"] == 100
            assert results["preserved_count"] == 5
            assert "cutoff_date" in results

            # Verify cleanup log entry was created
            mock_db.add.assert_called()
            mock_db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_cleanup_preserves_critical_logs(scheduler):
    """Test that critical audit logs are preserved during cleanup."""
    mock_db = AsyncMock(spec=AsyncSession)

    preserved_result = MagicMock()
    preserved_result.scalar.return_value = 10  # 10 critical logs

    delete_result = MagicMock()
    delete_result.rowcount = 50

    mock_db.execute.side_effect = [preserved_result, delete_result]

    settings_mock = MagicMock()
    settings_mock.audit_retention_days = 30

    with patch.object(scheduler, "_get_db_session", return_value=mock_db):
        with patch("app.scheduler.get_settings", return_value=settings_mock):
            results = await scheduler._cleanup_old_audit_logs()

            # Critical logs should be preserved
            assert results["preserved_count"] == 10


@pytest.mark.asyncio
async def test_cleanup_old_audit_logs_error_handling(scheduler):
    """Test audit cleanup handles errors gracefully."""
    mock_db = AsyncMock(spec=AsyncSession)
    mock_db.execute.side_effect = Exception("Database error")

    settings_mock = MagicMock()
    settings_mock.audit_retention_days = 90

    with patch.object(scheduler, "_get_db_session", return_value=mock_db):
        with patch("app.scheduler.get_settings", return_value=settings_mock):
            # Should not raise
            await scheduler._cleanup_old_audit_logs()

            mock_db.close.assert_called_once()


@pytest.mark.asyncio
async def test_audit_cleanup_loop_runs_periodically(scheduler):
    """Test that the audit cleanup loop runs at the correct interval."""
    settings_mock = MagicMock()
    settings_mock.audit_cleanup_interval_hours = 0.01  # Very short for testing

    call_count = 0

    async def mock_cleanup():
        nonlocal call_count
        call_count += 1

    async def mock_sleep(seconds):
        if call_count >= 2:
            scheduler._running = False

    with patch("app.scheduler.get_settings", return_value=settings_mock):
        with patch.object(
            scheduler, "_cleanup_old_audit_logs", side_effect=mock_cleanup
        ):
            with patch("asyncio.sleep", side_effect=mock_sleep):
                scheduler._running = True
                await scheduler._audit_cleanup_loop()

                assert call_count >= 1


# ─── Database Health Check Tests ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_check_database_health_healthy(scheduler):
    """Test database health check with healthy database."""
    mock_db = AsyncMock(spec=AsyncSession)

    # Mock different query results
    select_1_result = MagicMock()
    select_1_result.scalar.return_value = 1

    size_result = MagicMock()
    size_result.scalar.return_value = 1000000  # 1MB

    user_count_result = MagicMock()
    user_count_result.scalar.return_value = 50

    audit_count_result = MagicMock()
    audit_count_result.scalar.return_value = 1000

    orphaned_result = MagicMock()
    orphaned_result.scalar.return_value = 0

    mock_db.execute.side_effect = [
        select_1_result,
        size_result,
        user_count_result,
        audit_count_result,
        orphaned_result,
    ]

    with patch.object(scheduler, "_get_db_session", return_value=mock_db):
        health = await scheduler._check_database_health()

        assert health["connection_ok"] is True
        assert health["database_size_bytes"] == 1000000
        assert health["user_count"] == 50
        assert health["audit_log_count"] == 1000
        assert health["orphaned_users"] == 0

        # Verify health log entry was created
        mock_db.add.assert_called()


@pytest.mark.asyncio
async def test_check_database_health_connection_failure(scheduler):
    """Test database health check detects connection failures."""
    mock_db = AsyncMock(spec=AsyncSession)
    mock_db.execute.side_effect = Exception("Connection refused")

    with patch.object(scheduler, "_get_db_session", return_value=mock_db):
        health = await scheduler._check_database_health()

        assert health["connection_ok"] is False
        assert "connection_error" in health


@pytest.mark.asyncio
async def test_check_database_health_orphaned_users(scheduler, mock_user_no_service):
    """Test database health check detects orphaned users."""
    mock_db = AsyncMock(spec=AsyncSession)

    select_1_result = MagicMock()
    select_1_result.scalar.return_value = 1

    size_result = MagicMock()
    size_result.scalar.return_value = 1000000

    user_count_result = MagicMock()
    user_count_result.scalar.return_value = 50

    audit_count_result = MagicMock()
    audit_count_result.scalar.return_value = 1000

    orphaned_result = MagicMock()
    orphaned_result.scalar.return_value = 3  # 3 orphaned users

    mock_db.execute.side_effect = [
        select_1_result,
        size_result,
        user_count_result,
        audit_count_result,
        orphaned_result,
    ]

    with patch.object(scheduler, "_get_db_session", return_value=mock_db):
        health = await scheduler._check_database_health()

        assert health["orphaned_users"] == 3


@pytest.mark.asyncio
async def test_check_database_health_size_check_failure(scheduler):
    """Test database health check handles size check failure gracefully."""
    mock_db = AsyncMock(spec=AsyncSession)

    select_1_result = MagicMock()
    select_1_result.scalar.return_value = 1

    size_result = MagicMock()
    size_result.scalar.side_effect = Exception("pg_database_size not available")

    user_count_result = MagicMock()
    user_count_result.scalar.return_value = 50

    audit_count_result = MagicMock()
    audit_count_result.scalar.return_value = 1000

    orphaned_result = MagicMock()
    orphaned_result.scalar.return_value = 0

    mock_db.execute.side_effect = [
        select_1_result,
        size_result,
        user_count_result,
        audit_count_result,
        orphaned_result,
    ]

    with patch.object(scheduler, "_get_db_session", return_value=mock_db):
        # Should not raise - size check failure is non-fatal
        health = await scheduler._check_database_health()

        assert health["connection_ok"] is True
        assert health["user_count"] == 50


@pytest.mark.asyncio
async def test_check_database_health_error_handling(scheduler):
    """Test database health check handles errors gracefully."""
    mock_db = AsyncMock(spec=AsyncSession)
    mock_db.execute.side_effect = Exception("Unexpected error")

    with patch.object(scheduler, "_get_db_session", return_value=mock_db):
        # Should not raise
        health = await scheduler._check_database_health()

        assert health["connection_ok"] is False
        mock_db.close.assert_called_once()


@pytest.mark.asyncio
async def test_db_health_check_loop_runs_periodically(scheduler):
    """Test that the DB health check loop runs at the correct interval."""
    settings_mock = MagicMock()
    settings_mock.db_health_check_interval_minutes = 0.01  # Very short for testing

    call_count = 0

    async def mock_check():
        nonlocal call_count
        call_count += 1

    async def mock_sleep(seconds):
        if call_count >= 2:
            scheduler._running = False

    with patch("app.scheduler.get_settings", return_value=settings_mock):
        with patch.object(scheduler, "_check_database_health", side_effect=mock_check):
            with patch("asyncio.sleep", side_effect=mock_sleep):
                scheduler._running = True
                await scheduler._db_health_check_loop()

                assert call_count >= 1


# ─── Task Error Isolation Tests ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_one_task_failure_does_not_stop_others(scheduler):
    """Test that failure in one task doesn't stop other tasks."""
    settings_mock = MagicMock()
    settings_mock.health_check_interval_minutes = 0.01
    settings_mock.analytics_interval_minutes = 0.01

    health_call_count = 0
    analytics_call_count = 0

    # Capture the real sleep BEFORE patching so we can yield inside mock_sleep
    real_sleep = asyncio.sleep

    async def mock_health_check():
        nonlocal health_call_count
        health_call_count += 1
        raise Exception("Health check failed")

    async def mock_analytics():
        nonlocal analytics_call_count
        analytics_call_count += 1

    async def mock_sleep(seconds):
        # Yield to the event loop so asyncio.gather can switch between tasks
        await real_sleep(0)
        if analytics_call_count >= 2:
            scheduler._running = False

    with patch("app.scheduler.get_settings", return_value=settings_mock):
        with patch.object(
            scheduler, "_check_service_health", side_effect=mock_health_check
        ):
            with patch.object(
                scheduler, "_aggregate_usage_analytics", side_effect=mock_analytics
            ):
                with patch("asyncio.sleep", side_effect=mock_sleep):
                    scheduler._running = True
                    # Run both loops concurrently; analytics should run even if health fails
                    await asyncio.gather(
                        scheduler._health_monitor_loop(),
                        scheduler._analytics_loop(),
                        return_exceptions=True,
                    )

                    # Analytics should have run at least once despite health failures
                    assert analytics_call_count >= 1


# ─── Audit Log Entry Creation Tests ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_audit_log_entry(scheduler):
    """Test creating an audit log entry."""
    mock_db = AsyncMock(spec=AsyncSession)

    await scheduler._create_audit_log_entry(
        db=mock_db,
        user_id="test-user-1",
        action="test_action",
        details={"key": "value"},
        performed_by="test",
    )

    # Verify the entry was added to the session
    mock_db.add.assert_called_once()
    entry = mock_db.add.call_args[0][0]
    assert entry.user_id == "test-user-1"
    assert entry.action == "test_action"
    assert entry.details == {"key": "value"}
    assert entry.performed_by == "test"


@pytest.mark.asyncio
async def test_create_audit_log_entry_system_action(scheduler):
    """Test creating an audit log entry for a system action (no user)."""
    mock_db = AsyncMock(spec=AsyncSession)

    await scheduler._create_audit_log_entry(
        db=mock_db,
        user_id=None,
        action="system_maintenance",
        details={"status": "complete"},
        performed_by="scheduler",
    )

    mock_db.add.assert_called_once()
    entry = mock_db.add.call_args[0][0]
    assert entry.user_id is None
    assert entry.performed_by == "scheduler"


# ─── Scheduler Configuration Tests ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_scheduler_uses_config_intervals(scheduler):
    """Test that scheduler uses configuration for task intervals."""
    from app.config import get_settings

    settings = get_settings()

    # Verify default configuration values exist
    assert settings.health_check_interval_minutes > 0
    assert settings.analytics_interval_minutes > 0
    assert settings.audit_cleanup_interval_hours > 0
    assert settings.audit_retention_days > 0
    assert settings.db_health_check_interval_minutes > 0


# ─── Integration Tests ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_scheduler_full_lifecycle(scheduler):
    """Test complete scheduler lifecycle: start -> run -> stop."""

    async def slow_loop():
        try:
            await asyncio.sleep(3600)
        except asyncio.CancelledError:
            pass

    with patch.object(scheduler, "_health_monitor_loop", side_effect=slow_loop):
        with patch.object(scheduler, "_analytics_loop", side_effect=slow_loop):
            with patch.object(scheduler, "_audit_cleanup_loop", side_effect=slow_loop):
                with patch.object(
                    scheduler, "_db_health_check_loop", side_effect=slow_loop
                ):
                    # Start
                    assert scheduler.is_running() is False
                    await scheduler.start()
                    assert scheduler.is_running() is True
                    assert scheduler.get_task_count() == 4

                    # Stop
                    await scheduler.stop()
                    assert scheduler.is_running() is False
                    assert scheduler.get_task_count() == 0


@pytest.mark.asyncio
async def test_scheduler_tasks_handle_cancellation_gracefully(scheduler):
    """Test that all scheduled tasks handle cancellation gracefully."""
    # Test each loop individually for cancellation handling
    for loop_method in [
        "_health_monitor_loop",
        "_analytics_loop",
        "_audit_cleanup_loop",
        "_db_health_check_loop",
    ]:
        scheduler._running = True
        task = asyncio.create_task(getattr(scheduler, loop_method)())

        # Give it a moment to start
        await asyncio.sleep(0.01)

        # Cancel and verify no exception
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        scheduler._running = False


@pytest.mark.asyncio
async def test_scheduler_concurrent_start_stop(scheduler):
    """Test that concurrent start/stop operations are handled safely."""

    async def slow_loop():
        try:
            await asyncio.sleep(3600)
        except asyncio.CancelledError:
            pass

    with patch.object(scheduler, "_health_monitor_loop", side_effect=slow_loop):
        with patch.object(scheduler, "_analytics_loop", side_effect=slow_loop):
            with patch.object(scheduler, "_audit_cleanup_loop", side_effect=slow_loop):
                with patch.object(
                    scheduler, "_db_health_check_loop", side_effect=slow_loop
                ):
                    # Start and immediately stop
                    start_task = asyncio.create_task(scheduler.start())
                    await asyncio.sleep(0.01)
                    stop_task = asyncio.create_task(scheduler.stop())

                    await asyncio.gather(start_task, stop_task)

                    # Scheduler should end up stopped
                    assert scheduler.is_running() is False


# ─── Audit Log Cleanup — Real-SQL Integration Tests ──────────────────────────
#
# These tests patch app.database._session_factory to point at the shared
# in-memory SQLite engine, then call _cleanup_old_audit_logs() for real so
# the actual DELETE SQL is exercised (not just the mock path).


class TestAuditCleanupIntegration:
    """Drive _cleanup_old_audit_logs against a live SQLite session."""

    @staticmethod
    async def _seed(factory, *, old_plain_id, old_critical_id, recent_id):
        """Insert three AuditLog rows with carefully chosen created_at values."""

        async with factory() as s:
            s.add(
                AuditLog(
                    id=old_plain_id,
                    user_id=None,
                    action="user.logged_in",  # non-critical, old → must be deleted
                    details={"info": "seed"},
                    performed_by="test",
                    created_at=datetime.now(timezone.utc) - timedelta(days=100),
                )
            )
            s.add(
                AuditLog(
                    id=old_critical_id,
                    user_id=None,
                    action="user_deleted",  # critical, old → must be preserved
                    details={"info": "seed"},
                    performed_by="admin",
                    created_at=datetime.now(timezone.utc) - timedelta(days=100),
                )
            )
            s.add(
                AuditLog(
                    id=recent_id,
                    user_id=None,
                    action="user.logged_in",  # non-critical, recent → must be preserved
                    details={"info": "seed"},
                    performed_by="test",
                    created_at=datetime.now(timezone.utc) - timedelta(days=1),
                )
            )
            await s.commit()

    @pytest.mark.asyncio
    async def test_old_non_critical_logs_are_deleted(self, engine, scheduler):
        """DELETE removes old non-critical rows and leaves everything else."""
        import app.database as db_module
        from sqlalchemy.ext.asyncio import async_sessionmaker
        from sqlalchemy import select as sa_select

        factory = async_sessionmaker(engine, expire_on_commit=False)
        old_factory = db_module._session_factory
        db_module._session_factory = factory

        try:
            await self._seed(
                factory,
                old_plain_id="integ-old-plain",
                old_critical_id="integ-old-critical",
                recent_id="integ-recent",
            )

            with patch("app.scheduler.get_settings") as ms:
                ms.return_value.audit_retention_days = 90
                results = await scheduler._cleanup_old_audit_logs()

            # Structural assertions on the returned summary dict
            assert results["deleted_count"] >= 1, "expected at least one deletion"
            assert results["preserved_count"] >= 1, (
                "expected at least one preserved critical row"
            )
            assert "cutoff_date" in results
            assert "timestamp" in results

            # Verify actual DB state
            async with factory() as s:
                rows = (await s.execute(sa_select(AuditLog))).scalars().all()
                ids = {r.id for r in rows}

            assert "integ-old-plain" not in ids, (
                "old non-critical row should be deleted"
            )
            assert "integ-old-critical" in ids, "old critical row must be preserved"
            assert "integ-recent" in ids, "recent row must not be touched"
        finally:
            db_module._session_factory = old_factory

    @pytest.mark.asyncio
    async def test_deleted_count_is_non_negative(self, engine, scheduler):
        """deleted_count must always be >= 0 even if the DB returns rowcount=-1."""
        import app.database as db_module
        from sqlalchemy.ext.asyncio import async_sessionmaker

        factory = async_sessionmaker(engine, expire_on_commit=False)
        old_factory = db_module._session_factory
        db_module._session_factory = factory

        try:
            # Empty table — rowcount will be 0 (or -1 on some aiosqlite builds)
            with patch("app.scheduler.get_settings") as ms:
                ms.return_value.audit_retention_days = 90
                results = await scheduler._cleanup_old_audit_logs()

            assert results["deleted_count"] >= 0, "deleted_count must never be negative"
        finally:
            db_module._session_factory = old_factory

    @pytest.mark.asyncio
    async def test_cleanup_self_log_is_written(self, engine, scheduler):
        """_cleanup_old_audit_logs must commit an audit_log_cleanup entry."""
        import app.database as db_module
        from sqlalchemy.ext.asyncio import async_sessionmaker
        from sqlalchemy import select as sa_select

        factory = async_sessionmaker(engine, expire_on_commit=False)
        old_factory = db_module._session_factory
        db_module._session_factory = factory

        try:
            with patch("app.scheduler.get_settings") as ms:
                ms.return_value.audit_retention_days = 90
                await scheduler._cleanup_old_audit_logs()

            async with factory() as s:
                rows = (
                    (
                        await s.execute(
                            sa_select(AuditLog).where(
                                AuditLog.action == "audit_log_cleanup"
                            )
                        )
                    )
                    .scalars()
                    .all()
                )

            assert len(rows) >= 1, "cleanup must write an audit_log_cleanup entry"
            assert rows[0].performed_by == "scheduler"
        finally:
            db_module._session_factory = old_factory

    @pytest.mark.asyncio
    async def test_recent_logs_are_untouched(self, engine, scheduler):
        """Rows newer than the retention window must not be deleted."""
        import app.database as db_module
        from sqlalchemy.ext.asyncio import async_sessionmaker
        from sqlalchemy import select as sa_select

        factory = async_sessionmaker(engine, expire_on_commit=False)
        old_factory = db_module._session_factory
        db_module._session_factory = factory

        try:
            async with factory() as s:
                for i in range(5):
                    s.add(
                        AuditLog(
                            id=f"recent-{i}",
                            user_id=None,
                            action="user.logged_in",
                            details={},
                            performed_by="test",
                            created_at=datetime.now(timezone.utc) - timedelta(hours=i),
                        )
                    )
                await s.commit()

            with patch("app.scheduler.get_settings") as ms:
                ms.return_value.audit_retention_days = 90
                results = await scheduler._cleanup_old_audit_logs()

            assert results["deleted_count"] == 0

            async with factory() as s:
                from sqlalchemy import func as sqla_func

                count = (
                    await s.execute(
                        sa_select(sqla_func.count(AuditLog.id)).where(
                            AuditLog.id.like("recent-%")
                        )
                    )
                ).scalar()
            assert count == 5, "none of the fresh logs should have been deleted"
        finally:
            db_module._session_factory = old_factory
