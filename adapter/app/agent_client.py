"""HTTP client to communicate with Agent Zero's REST API."""
import httpx
import structlog
from app.config import get_settings
from app.context_store import get_context_store

logger = structlog.get_logger()


class AgentClient:
    """Async client for the Agent Zero REST API.

    Supports per-user context management through Redis-backed context store,
    with automatic fallback to in-memory storage when Redis is unavailable.
    """

    def __init__(self, base_url: str | None = None, api_key: str | None = None):
        settings = get_settings()
        self.base_url = base_url or settings.agent_api_url
        self.api_key = api_key or settings.agent_api_key
        self._headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def send_message(self, message: str, user_id: str | None = None) -> str:
        """Send a message to Agent Zero and get the full response.

        Uses the Redis-backed context store for multi-turn conversations.
        Context IDs are persisted with a TTL matching the default_lifetime_hours
        setting, and are shared across adapter replicas.

        Args:
            message: The user's message text.
            user_id: Optional user ID for per-user context tracking.

        Returns:
            The agent's response text.
        """
        settings = get_settings()
        effective_user_id = user_id or settings.user_id

        # Look up context_id from Redis-backed store
        context_store = get_context_store()
        context_id = await context_store.get(effective_user_id) if effective_user_id else None

        payload = {
            "message": message,
            "lifetime_hours": settings.default_lifetime_hours,
        }
        if context_id:
            payload["context_id"] = context_id
        if settings.default_project_name:
            payload["project_name"] = settings.default_project_name

        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(
                f"{self.base_url}/api_message",
                json=payload,
                headers=self._headers,
            )
            response.raise_for_status()
            data = response.json()

        # Persist context_id for multi-turn conversations
        returned_context_id = data.get("context_id")
        if returned_context_id and effective_user_id:
            await context_store.set(effective_user_id, returned_context_id)

        return data.get("response", "")

    @staticmethod
    async def get_context_id(user_id: str) -> str | None:
        """Get the stored context_id for a user.

        Args:
            user_id: The user ID to look up.

        Returns:
            The context_id string, or None if not found.
        """
        store = get_context_store()
        return await store.get(user_id)

    @staticmethod
    async def set_context_id(user_id: str, context_id: str) -> None:
        """Manually set the context_id for a user.

        Args:
            user_id: The user ID to set context for.
            context_id: The context_id to store.
        """
        store = get_context_store()
        await store.set(user_id, context_id)