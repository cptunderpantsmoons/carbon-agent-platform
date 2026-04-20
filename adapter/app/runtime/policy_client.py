"""Model policy client — fetches routing policy from the orchestrator.

The orchestrator remains the source of truth for provider/routing decisions.
The adapter fetches policy at runtime and uses it to resolve which LLM
provider and model to use for each request.
"""
from typing import Optional
import structlog
import httpx

from app.config import get_settings
from .dependencies import ModelPolicyContext

logger = structlog.get_logger()


class PolicyClient:
    """Async client for fetching model policy from the orchestrator."""

    def __init__(self, orchestrator_url: Optional[str] = None):
        settings = get_settings()
        self._base_url = (orchestrator_url or settings.orchestrator_url).rstrip("/")
        self._client: Optional[httpx.AsyncClient] = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=10.0)
        return self._client

    async def fetch_policy(self, tenant_id: str = "default") -> ModelPolicyContext:
        """Fetch the current model policy for a tenant.

        Falls back to a permissive default if the orchestrator is unreachable.
        """
        try:
            client = self._get_client()
            response = await client.get(
                f"{self._base_url}/v1/model-policy/me",
                params={"tenant_id": tenant_id},
            )
            response.raise_for_status()
            data = response.json()

            policy = ModelPolicyContext(
                routing_mode=data.get("routing_mode", "auto"),
                default_provider=data.get("default_provider", "openai"),
                allowed_providers=data.get("allowed_providers", ["openai"]),
                benchmark_mode=data.get("benchmark_mode", False),
            )
            logger.info(
                "policy_fetched",
                tenant_id=tenant_id,
                routing_mode=policy.routing_mode,
                default_provider=policy.default_provider,
            )
            return policy

        except httpx.HTTPStatusError as e:
            logger.warning(
                "policy_fetch_http_error",
                tenant_id=tenant_id,
                status=e.response.status_code,
                detail=e.response.text[:200],
            )
        except httpx.RequestError as e:
            logger.warning(
                "policy_fetch_request_error",
                tenant_id=tenant_id,
                error=str(e),
            )
        except Exception as e:
            logger.error(
                "policy_fetch_unexpected_error",
                tenant_id=tenant_id,
                error=str(e),
            )

        # Fallback default
        return ModelPolicyContext()

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None


# Singleton
_policy_client: Optional[PolicyClient] = None


def get_policy_client() -> PolicyClient:
    global _policy_client
    if _policy_client is None:
        _policy_client = PolicyClient()
    return _policy_client
