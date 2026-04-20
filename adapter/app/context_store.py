"""Redis-backed context store for multi-turn conversation persistence.

Replaces the in-memory _context_map with Redis when available,
falling back to an in-memory dict for development/testing without Redis.

Redis provides:
- Persistence across uvicorn worker restarts
- Shared state between replicas
- TTL-based expiration (matches default_lifetime_hours)
- Atomic operations
"""

import structlog
from app.config import get_settings

logger = structlog.get_logger(__name__)


class ContextStore:
    """Context store that uses Redis when available, falls back to in-memory dict.

    Redis is used for production deployments where multiple adapter replicas
    need to share conversation context. In development or when Redis is
    unavailable, the store falls back to an in-memory dictionary.

    Keys are stored with a TTL matching the default_lifetime_hours setting,
    ensuring stale context IDs are automatically cleaned up.
    """

    def __init__(self, redis_url: str = "", ttl_hours: int = 24):
        self._memory: dict[str, str] = {}
        self._redis_client = None
        self._redis_url = redis_url
        self._ttl_seconds = ttl_hours * 3600
        self._redis_available: bool | None = None

    async def _get_redis(self):
        """Lazily initialize and return Redis client, or None if unavailable."""
        if self._redis_available is False:
            return None

        if self._redis_client is None and self._redis_url:
            try:
                import redis.asyncio as redis_async

                self._redis_client = redis_async.from_url(
                    self._redis_url, decode_responses=True
                )
                await self._redis_client.ping()
                self._redis_available = True
                logger.info("context_store_redis_connected", redis_url=self._redis_url)
            except Exception as e:
                logger.warning(
                    "context_store_redis_unavailable_falling_back_to_memory",
                    error=str(e),
                )
                self._redis_available = False
                self._redis_client = None
                return None

        return self._redis_client

    async def get(self, user_id: str) -> str | None:
        """Retrieve the stored context_id for a user.

        Args:
            user_id: The user ID to look up.

        Returns:
            The context_id string, or None if not found.
        """
        r = await self._get_redis()
        if r:
            try:
                value = await r.get(f"context:{user_id}")
                return value
            except Exception as e:
                logger.warning(
                    "context_store_redis_get_error",
                    user_id=user_id,
                    error=str(e),
                )
                # Fall through to in-memory lookup

        return self._memory.get(user_id)

    async def set(self, user_id: str, context_id: str) -> None:
        """Store a context_id for a user with TTL-based expiration.

        Args:
            user_id: The user ID to store the context for.
            context_id: The context_id from the agent response.
        """
        r = await self._get_redis()
        if r:
            try:
                await r.setex(f"context:{user_id}", self._ttl_seconds, context_id)
                # Also update in-memory for fast local reads
                self._memory[user_id] = context_id
                return
            except Exception as e:
                logger.warning(
                    "context_store_redis_set_error",
                    user_id=user_id,
                    error=str(e),
                )
                # Fall through to in-memory storage

        self._memory[user_id] = context_id

    async def delete(self, user_id: str) -> None:
        """Remove stored context for a user.

        Args:
            user_id: The user ID to remove context for.
        """
        r = await self._get_redis()
        if r:
            try:
                await r.delete(f"context:{user_id}")
            except Exception:
                pass

        self._memory.pop(user_id, None)

    async def close(self) -> None:
        """Close the Redis connection pool if it was opened."""
        if self._redis_client:
            try:
                await self._redis_client.close()
            except Exception:
                pass
            self._redis_client = None


# --- Module-level singleton ---

_context_store: ContextStore | None = None


def get_context_store() -> ContextStore:
    """Get or create the singleton ContextStore instance."""
    global _context_store
    if _context_store is None:
        settings = get_settings()
        _context_store = ContextStore(
            redis_url=settings.redis_url,
            ttl_hours=settings.default_lifetime_hours,
        )
    return _context_store
