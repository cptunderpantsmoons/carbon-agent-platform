"""DBOS durability boundary design for the Carbon agent runtime.

DBOS (https://docs.dbos.dev/) provides durable execution primitives
that wrap Python functions with automatic checkpointing, recovery,
and exactly-once semantics.

Integration scope for v2.0:
- Wrap long-running agent runs so failures mid-run resume from last checkpoint
- Wrap MCP communication steps so external I/O is idempotent
- Decorate non-deterministic custom tools that perform I/O

Usage:
    from dbos import DBOS, SetWorkflowID
    from app.runtime.dbos_design import dbos_init

    dbos_init()  # once at startup

    @DBOS.step()
    async def call_external_api(params):
        ...

    @DBOS.workflow()
    async def durable_agent_run(request, deps):
        step1 = await call_external_api(...)
        step2 = await agent.run(...)
        return step2
"""
from functools import wraps
from typing import Callable, Any
import structlog

logger = structlog.get_logger()

# DBOS is optional in this phase — graceful degradation if not configured
_DBOS_AVAILABLE = False
try:
    from dbos import DBOS
    _DBOS_AVAILABLE = True
except ImportError:
    pass


def dbos_init(config: dict | None = None) -> None:
    """Initialize DBOS with the adapter's Postgres connection.

    Args:
        config: Optional DBOS config override. Defaults to using
                the adapter's DATABASE_URL env var.
    """
    if not _DBOS_AVAILABLE:
        logger.warning("dbos_not_installed_skipping_init")
        return

    from app.config import get_settings
    settings = get_settings()

    dbos_config = config or {
        "name": "carbon-agent-adapter",
        "database": {
            "hostname": _extract_db_host(settings.database_url),
            "port": _extract_db_port(settings.database_url),
            "username": _extract_db_user(settings.database_url),
            "password": _extract_db_password(settings.database_url),
            "dbname": _extract_db_name(settings.database_url),
        },
        "application_database": {
            "hostname": _extract_db_host(settings.database_url),
            "port": _extract_db_port(settings.database_url),
            "username": _extract_db_user(settings.database_url),
            "password": _extract_db_password(settings.database_url),
            "dbname": _extract_db_name(settings.database_url),
        },
    }
    DBOS(dbos_config)
    logger.info("dbos_initialized")


def dbos_start() -> None:
    """Start DBOS (call during FastAPI lifespan startup)."""
    if _DBOS_AVAILABLE:
        DBOS.launch()
        logger.info("dbos_started")


def dbos_stop() -> None:
    """Stop DBOS (call during FastAPI lifespan shutdown)."""
    if _DBOS_AVAILABLE:
        DBOS.shutdown()
        logger.info("dbos_stopped")


def durable_step(name: str | None = None) -> Callable:
    """Decorator for durable steps (idempotent, checkpointed operations).

    Falls back to a no-op wrapper if DBOS is not available.
    """
    def decorator(func: Callable) -> Callable:
        if _DBOS_AVAILABLE:
            return DBOS.step(name=name)(func)

        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)
        return wrapper
    return decorator


def durable_workflow(name: str | None = None) -> Callable:
    """Decorator for durable workflows (long-running, resumable agent runs).

    Falls back to a no-op wrapper if DBOS is not available.
    """
    def decorator(func: Callable) -> Callable:
        if _DBOS_AVAILABLE:
            return DBOS.workflow(name=name)(func)

        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)
        return wrapper
    return decorator


def _extract_db_host(url: str) -> str:
    from urllib.parse import urlparse
    return urlparse(url).hostname or "localhost"


def _extract_db_port(url: str) -> int:
    from urllib.parse import urlparse
    return urlparse(url).port or 5432


def _extract_db_user(url: str) -> str:
    from urllib.parse import urlparse
    return urlparse(url).username or "postgres"


def _extract_db_password(url: str) -> str:
    from urllib.parse import urlparse
    return urlparse(url).password or ""


def _extract_db_name(url: str) -> str:
    from urllib.parse import urlparse
    path = urlparse(url).path or "/"
    return path.lstrip("/") or "postgres"
