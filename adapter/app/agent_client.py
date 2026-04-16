"""HTTP client to communicate with the Carbon Agent internal API."""
import httpx
import structlog
from app.config import get_settings

logger = structlog.get_logger()


class AgentClient:
    """Async client for the Carbon Agent internal API."""

    def __init__(self, base_url: str | None = None, api_key: str | None = None):
        settings = get_settings()
        self.base_url = base_url or settings.agent_api_url
        self.api_key = api_key or settings.agent_api_key
        self._headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def send_message(self, message: str, conversation_id: str | None = None) -> str:
        """Send a message to Carbon Agent and get the response."""
        payload = {
            "message": message,
            "user_id": get_settings().user_id,
            "conversation_id": conversation_id,
        }

        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(
                f"{self.base_url}/api/chat",
                json=payload,
                headers=self._headers,
            )
            response.raise_for_status()
            data = response.json()
            return data.get("response", "")

    async def send_message_stream(self, message: str, conversation_id: str | None = None):
        """Send a message and stream the response."""
        payload = {
            "message": message,
            "user_id": get_settings().user_id,
            "conversation_id": conversation_id,
            "stream": True,
        }

        async with httpx.AsyncClient(timeout=300.0) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/api/chat",
                json=payload,
                headers=self._headers,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        chunk = line[6:]
                        if chunk.strip() == "[DONE]":
                            break
                        yield chunk
