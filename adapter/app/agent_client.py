"""HTTP client to communicate with Agent Zero's REST API."""
import httpx
import structlog
from app.config import get_settings

logger = structlog.get_logger()

# In-memory mapping of user_id -> context_id for multi-turn conversations.
# WARNING: This is process-local state. With multiple uvicorn workers or
# replicas, conversations that hit different processes will lose context.
# TODO: Replace with a shared store (Redis, DB) for production multi-replica deployments.
_context_map: dict[str, str] = {}


class AgentClient:
    """Async client for the Agent Zero REST API."""

    def __init__(self, base_url: str | None = None, api_key: str | None = None):
        settings = get_settings()
        self.base_url = base_url or settings.agent_api_url
        self.api_key = api_key or settings.agent_api_key
        self._headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def send_message(self, message: str, user_id: str | None = None) -> str:
        """Send a message to Agent Zero and get the full response."""
        settings = get_settings()
        effective_user_id = user_id or settings.user_id
        context_id = _context_map.get(effective_user_id)

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

        # Persist context_id for multi-turn
        returned_context_id = data.get("context_id")
        if returned_context_id and effective_user_id:
            _context_map[effective_user_id] = returned_context_id

        return data.get("response", "")

    @staticmethod
    def get_context_id(user_id: str) -> str | None:
        """Get the stored context_id for a user."""
        return _context_map.get(user_id)

    @staticmethod
    def set_context_id(user_id: str, context_id: str) -> None:
        """Manually set the context_id for a user."""
        _context_map[user_id] = context_id
