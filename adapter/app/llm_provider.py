"""LLM Provider Abstraction Layer.

Supports multiple LLM backends with a unified interface:
- Agent Zero (default, self-hosted)
- OpenAI
- Featherless AI (OpenAI-compatible)
- DeepSeek (OpenAI-compatible)
- Anthropic (via translation layer)

All providers implement the same interface for seamless swapping.
"""

from abc import ABC, abstractmethod
from typing import Optional

import httpx
import structlog
from openai import AsyncOpenAI

from app.config import get_settings

logger = structlog.get_logger()


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    async def chat_completion(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stream: bool = False,
        **kwargs,
    ) -> str:
        """Send chat completion request and return response text."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if provider is accessible and healthy."""
        pass


class AgentZeroProvider(LLMProvider):
    """Agent Zero self-hosted LLM backend.

    Uses the Agent Zero REST API with context management.
    """

    def __init__(self, base_url: str, api_key: str = ""):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._headers = {
            "Authorization": f"Bearer {self.api_key}" if api_key else "",
            "Content-Type": "application/json",
        }

    async def chat_completion(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stream: bool = False,
        context_id: Optional[str] = None,
        user_id: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Send message to Agent Zero with context management."""
        # Extract last user message
        user_message = messages[-1]["content"] if messages else ""

        payload = {
            "message": user_message,
            "lifetime_hours": 24,
        }
        if context_id:
            payload["context_id"] = context_id

        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(
                f"{self.base_url}/api_message",
                json=payload,
                headers=self._headers,
            )
            response.raise_for_status()
            data = response.json()

        return data.get("response", "")

    async def health_check(self) -> bool:
        """Check Agent Zero API health."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/health")
                return response.status_code == 200
        except Exception:
            return False


class OpenAIProvider(LLMProvider):
    """OpenAI API provider."""

    def __init__(
        self, api_key: str, model: str = "gpt-4o", base_url: Optional[str] = None
    ):
        self.model = model
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,  # Allows custom OpenAI-compatible endpoints
        )

    async def chat_completion(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stream: bool = False,
        **kwargs,
    ) -> str:
        """Send chat completion to OpenAI."""
        params = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens:
            params["max_tokens"] = max_tokens

        response = await self.client.chat.completions.create(**params)
        return response.choices[0].message.content

    async def health_check(self) -> bool:
        """Check OpenAI API access."""
        try:
            await self.client.models.list()
            return True
        except Exception:
            return False


class FeatherlessProvider(LLMProvider):
    """Featherless AI provider (OpenAI-compatible API).

    Featherless AI provides a drop-in replacement for OpenAI's API
    with support for open-source models.

    Usage:
        from openai import AsyncOpenAI
        import os

        client = AsyncOpenAI(
            base_url="https://api.featherless.ai/v1",
            api_key=os.environ['FEATHERLESS_API_KEY']
        )
    """

    def __init__(self, api_key: str, model: str = "meta-llama-3.1-70b-instruct"):
        self.model = model
        self.client = AsyncOpenAI(
            base_url="https://api.featherless.ai/v1",
            api_key=api_key,
        )

    async def chat_completion(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stream: bool = False,
        **kwargs,
    ) -> str:
        """Send chat completion to Featherless AI."""
        params = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens:
            params["max_tokens"] = max_tokens

        response = await self.client.chat.completions.create(**params)
        return response.choices[0].message.content

    async def health_check(self) -> bool:
        """Check Featherless AI API access."""
        try:
            await self.client.models.list()
            return True
        except Exception:
            return False


class DeepSeekProvider(LLMProvider):
    """DeepSeek AI provider (OpenAI-compatible API).

    DeepSeek provides powerful coding and reasoning models with
    an OpenAI-compatible API interface.

    Usage:
        from openai import AsyncOpenAI
        import os

        client = AsyncOpenAI(
            base_url="https://api.deepseek.com/v1",
            api_key=os.environ['DEEPSEEK_API_KEY']
        )
    """

    def __init__(self, api_key: str, model: str = "deepseek-chat"):
        self.model = model
        self.client = AsyncOpenAI(
            base_url="https://api.deepseek.com/v1",
            api_key=api_key,
        )

    async def chat_completion(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stream: bool = False,
        **kwargs,
    ) -> str:
        """Send chat completion to DeepSeek."""
        params = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens:
            params["max_tokens"] = max_tokens

        response = await self.client.chat.completions.create(**params)
        return response.choices[0].message.content

    async def health_check(self) -> bool:
        """Check DeepSeek API access."""
        try:
            await self.client.models.list()
            return True
        except Exception:
            return False


class AnthropicProvider(LLMProvider):
    """Anthropic Claude provider.

    Requires message format translation from OpenAI format to Anthropic format.
    """

    def __init__(self, api_key: str, model: str = "claude-3-sonnet-20240229"):
        self.model = model
        self.api_key = api_key
        self._headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

    async def chat_completion(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stream: bool = False,
        **kwargs,
    ) -> str:
        """Send chat completion to Anthropic Claude."""
        # Translate OpenAI format to Anthropic format
        system_prompt = ""
        anthropic_messages = []

        for msg in messages:
            if msg["role"] == "system":
                system_prompt = msg["content"]
            elif msg["role"] in ["user", "assistant"]:
                anthropic_messages.append(
                    {
                        "role": msg["role"],
                        "content": msg["content"],
                    }
                )

        payload = {
            "model": self.model,
            "messages": anthropic_messages,
            "max_tokens": max_tokens or 4096,
            "temperature": temperature,
        }
        if system_prompt:
            payload["system"] = system_prompt

        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                json=payload,
                headers=self._headers,
            )
            response.raise_for_status()
            data = response.json()

        return data["content"][0]["text"]

    async def health_check(self) -> bool:
        """Check Anthropic API access."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                # Anthropic doesn't have a health endpoint, just test auth
                response = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    json={"model": self.model, "messages": [], "max_tokens": 1},
                    headers=self._headers,
                )
                return response.status_code != 401  # 401 = auth failed
        except Exception:
            return False


def create_provider(
    provider_type: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
) -> LLMProvider:
    """Factory function to create the appropriate LLM provider.

    Args:
        provider_type: One of 'agent-zero', 'openai', 'featherless', 'deepseek', 'anthropic'
        base_url: API base URL (for agent-zero or custom endpoints)
        api_key: API key (for cloud providers)
        model: Model name to use

    Returns:
        Configured LLMProvider instance

    Raises:
        ValueError: If provider_type is not supported
    """
    settings = get_settings()

    # Use provided values or fall back to settings
    p_type = provider_type or settings.llm_provider
    p_url = base_url or settings.llm_base_url
    p_key = api_key or settings.llm_api_key
    p_model = model or settings.llm_model_name

    logger.info("creating_llm_provider", provider=p_type, model=p_model)

    if p_type == "agent-zero":
        return AgentZeroProvider(base_url=p_url, api_key=p_key)
    elif p_type == "openai":
        return OpenAIProvider(api_key=p_key, model=p_model)
    elif p_type == "featherless":
        return FeatherlessProvider(api_key=p_key, model=p_model)
    elif p_type == "deepseek":
        return DeepSeekProvider(api_key=p_key, model=p_model)
    elif p_type == "anthropic":
        return AnthropicProvider(api_key=p_key, model=p_model)
    else:
        raise ValueError(
            f"Unsupported LLM provider: {p_type}. "
            f"Supported: agent-zero, openai, featherless, deepseek, anthropic"
        )
