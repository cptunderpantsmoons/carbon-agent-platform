"""Tests for LLM provider abstraction layer."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.llm_provider import (
    LLMProvider,
    AgentZeroProvider,
    OpenAIProvider,
    FeatherlessProvider,
    DeepSeekProvider,
    AnthropicProvider,
    create_provider,
)
from app.config import get_settings
from app.runtime.providers import resolve_provider_from_policy


class TestFeatherlessProvider:
    """Test Featherless AI provider implementation."""

    def test_initialization(self):
        """FeatherlessProvider initializes with correct endpoint."""
        provider = FeatherlessProvider(
            api_key="fl-test-key",
            model="meta-llama-3.1-70b-instruct"
        )

        assert provider.model == "meta-llama-3.1-70b-instruct"
        assert provider.client is not None
        assert provider.client.base_url == "https://api.featherless.ai/v1"

    def test_default_model(self):
        """Default model is LLaMA 3.1 70B."""
        provider = FeatherlessProvider(api_key="fl-test-key")
        assert provider.model == "meta-llama-3.1-70b-instruct"

    @pytest.mark.asyncio
    async def test_chat_completion_success(self):
        """Successful chat completion returns response text."""
        # Mock OpenAI response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Hello from Featherless!"

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with patch.object(FeatherlessProvider, '__init__', return_value=None):
            provider = FeatherlessProvider()
            provider.model = "meta-llama-3.1-70b-instruct"
            provider.client = mock_client

            result = await provider.chat_completion(
                messages=[{"role": "user", "content": "Hello!"}],
                temperature=0.7,
            )

            assert result == "Hello from Featherless!"
            mock_client.chat.completions.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_chat_completion_with_max_tokens(self):
        """Chat completion respects max_tokens parameter."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Short response"

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with patch.object(FeatherlessProvider, '__init__', return_value=None):
            provider = FeatherlessProvider()
            provider.model = "test-model"
            provider.client = mock_client

            await provider.chat_completion(
                messages=[{"role": "user", "content": "Test"}],
                max_tokens=100,
            )

            # Verify max_tokens was passed
            call_args = mock_client.chat.completions.create.call_args
            assert call_args[1]["max_tokens"] == 100

    @pytest.mark.asyncio
    async def test_health_check_success(self):
        """Health check succeeds when API is accessible."""
        mock_client = AsyncMock()
        mock_client.models.list = AsyncMock(return_value=["model1", "model2"])

        with patch.object(FeatherlessProvider, '__init__', return_value=None):
            provider = FeatherlessProvider()
            provider.client = mock_client

            result = await provider.health_check()
            assert result is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self):
        """Health check fails when API is unreachable."""
        mock_client = AsyncMock()
        mock_client.models.list = AsyncMock(side_effect=Exception("Connection refused"))

        with patch.object(FeatherlessProvider, '__init__', return_value=None):
            provider = FeatherlessProvider()
            provider.client = mock_client

            result = await provider.health_check()
            assert result is False


class TestDeepSeekProvider:
    """Test DeepSeek provider implementation."""

    def test_initialization(self):
        """DeepSeekProvider initializes with correct endpoint."""
        provider = DeepSeekProvider(
            api_key="sk-deepseek-test-key",
            model="deepseek-chat"
        )

        assert provider.model == "deepseek-chat"
        assert provider.client is not None
        assert provider.client.base_url == "https://api.deepseek.com/v1"

    def test_default_model(self):
        """Default model is deepseek-chat."""
        provider = DeepSeekProvider(api_key="sk-test-key")
        assert provider.model == "deepseek-chat"

    def test_coder_model(self):
        """Can use deepseek-coder model."""
        provider = DeepSeekProvider(
            api_key="sk-test-key",
            model="deepseek-coder"
        )
        assert provider.model == "deepseek-coder"

    @pytest.mark.asyncio
    async def test_chat_completion_success(self):
        """Successful chat completion returns response text."""
        # Mock OpenAI response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Hello from DeepSeek!"

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with patch.object(DeepSeekProvider, '__init__', return_value=None):
            provider = DeepSeekProvider()
            provider.model = "deepseek-chat"
            provider.client = mock_client

            result = await provider.chat_completion(
                messages=[{"role": "user", "content": "Hello!"}],
                temperature=0.7,
            )

            assert result == "Hello from DeepSeek!"
            mock_client.chat.completions.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_chat_completion_with_max_tokens(self):
        """Chat completion respects max_tokens parameter."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Short response"

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with patch.object(DeepSeekProvider, '__init__', return_value=None):
            provider = DeepSeekProvider()
            provider.model = "deepseek-chat"
            provider.client = mock_client

            await provider.chat_completion(
                messages=[{"role": "user", "content": "Test"}],
                max_tokens=100,
            )

            # Verify max_tokens was passed
            call_args = mock_client.chat.completions.create.call_args
            assert call_args[1]["max_tokens"] == 100

    @pytest.mark.asyncio
    async def test_health_check_success(self):
        """Health check succeeds when API is accessible."""
        mock_client = AsyncMock()
        mock_client.models.list = AsyncMock(return_value=["model1", "model2"])

        with patch.object(DeepSeekProvider, '__init__', return_value=None):
            provider = DeepSeekProvider()
            provider.client = mock_client

            result = await provider.health_check()
            assert result is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self):
        """Health check fails when API is unreachable."""
        mock_client = AsyncMock()
        mock_client.models.list = AsyncMock(side_effect=Exception("Connection refused"))

        with patch.object(DeepSeekProvider, '__init__', return_value=None):
            provider = DeepSeekProvider()
            provider.client = mock_client

            result = await provider.health_check()
            assert result is False


class TestOpenAIProvider:
    """Test OpenAI provider implementation."""

    def test_initialization(self):
        """OpenAIProvider initializes correctly."""
        provider = OpenAIProvider(
            api_key="sk-test-key",
            model="gpt-4o"
        )

        assert provider.model == "gpt-4o"
        assert provider.client is not None

    def test_custom_base_url(self):
        """Custom base URL allows OpenAI-compatible endpoints."""
        provider = OpenAIProvider(
            api_key="sk-test-key",
            model="custom-model",
            base_url="https://custom-api.example.com/v1"
        )

        assert provider.client.base_url == "https://custom-api.example.com/v1"

    @pytest.mark.asyncio
    async def test_chat_completion(self):
        """Chat completion returns response from OpenAI."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Hello from OpenAI!"

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with patch.object(OpenAIProvider, '__init__', return_value=None):
            provider = OpenAIProvider()
            provider.model = "gpt-4o"
            provider.client = mock_client

            result = await provider.chat_completion(
                messages=[{"role": "user", "content": "Hello!"}],
            )

            assert result == "Hello from OpenAI!"


class TestAnthropicProvider:
    """Test Anthropic provider implementation."""

    def test_initialization(self):
        """AnthropicProvider initializes with correct headers."""
        provider = AnthropicProvider(
            api_key="sk-ant-test-key",
            model="claude-3-sonnet-20240229"
        )

        assert provider.model == "claude-3-sonnet-20240229"
        assert provider._headers["x-api-key"] == "sk-ant-test-key"
        assert provider._headers["anthropic-version"] == "2023-06-01"

    @pytest.mark.asyncio
    async def test_chat_completion_message_translation(self):
        """Anthropic provider translates OpenAI format to Anthropic format."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "content": [{"text": "Hello from Claude!"}]
        }

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("app.llm_provider.httpx.AsyncClient", return_value=mock_client):
            provider = AnthropicProvider(api_key="test-key")

            result = await provider.chat_completion(
                messages=[
                    {"role": "system", "content": "You are helpful"},
                    {"role": "user", "content": "Hello!"},
                ],
            )

            assert result == "Hello from Claude!"
            mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_check_auth_failure(self):
        """Health check detects authentication failure."""
        mock_response = MagicMock()
        mock_response.status_code = 401  # Unauthorized

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("app.llm_provider.httpx.AsyncClient", return_value=mock_client):
            provider = AnthropicProvider(api_key="invalid-key")

            result = await provider.health_check()
            assert result is False  # 401 means auth failed


class TestAgentZeroProvider:
    """Test Agent Zero provider implementation."""

    def test_initialization(self):
        """AgentZeroProvider initializes with base URL."""
        provider = AgentZeroProvider(
            base_url="http://localhost:5000",
            api_key="test-key"
        )

        assert provider.base_url == "http://localhost:5000"
        assert "Bearer test-key" in provider._headers["Authorization"]

    def test_base_url_trailing_slash_removed(self):
        """Trailing slash is removed from base URL."""
        provider = AgentZeroProvider(
            base_url="http://localhost:5000/",
        )

        assert provider.base_url == "http://localhost:5000"

    @pytest.mark.asyncio
    async def test_chat_completion(self):
        """Chat completion calls Agent Zero API."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"response": "Hello from Agent Zero!"}

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("app.llm_provider.httpx.AsyncClient", return_value=mock_client):
            provider = AgentZeroProvider(base_url="http://localhost:5000")

            result = await provider.chat_completion(
                messages=[{"role": "user", "content": "Hello!"}],
            )

            assert result == "Hello from Agent Zero!"

    @pytest.mark.asyncio
    async def test_health_check(self):
        """Health check verifies Agent Zero API is accessible."""
        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("app.llm_provider.httpx.AsyncClient", return_value=mock_client):
            provider = AgentZeroProvider(base_url="http://localhost:5000")

            result = await provider.health_check()
            assert result is True


class TestProviderFactory:
    """Test provider factory function."""

    def test_create_agent_zero_provider(self):
        """Factory creates AgentZeroProvider for 'agent-zero' type."""
        with patch("app.llm_provider.get_settings") as mock_settings:
            mock_settings.return_value.llm_provider = "agent-zero"
            mock_settings.return_value.llm_base_url = "http://localhost:5000"
            mock_settings.return_value.llm_api_key = ""
            mock_settings.return_value.llm_model_name = "carbon-agent"

            provider = create_provider()
            assert isinstance(provider, AgentZeroProvider)

    def test_create_openai_provider(self):
        """Factory creates OpenAIProvider for 'openai' type."""
        with patch("app.llm_provider.get_settings") as mock_settings:
            mock_settings.return_value.llm_provider = "openai"
            mock_settings.return_value.llm_api_key = "sk-test-key"
            mock_settings.return_value.llm_model_name = "gpt-4o"

            provider = create_provider()
            assert isinstance(provider, OpenAIProvider)

    def test_create_featherless_provider(self):
        """Factory creates FeatherlessProvider for 'featherless' type."""
        with patch("app.llm_provider.get_settings") as mock_settings:
            mock_settings.return_value.llm_provider = "featherless"
            mock_settings.return_value.llm_api_key = "fl-test-key"
            mock_settings.return_value.llm_model_name = "meta-llama-3.1-70b-instruct"

            provider = create_provider()
            assert isinstance(provider, FeatherlessProvider)

    def test_create_deepseek_provider(self):
        """Factory creates DeepSeekProvider for 'deepseek' type."""
        with patch("app.llm_provider.get_settings") as mock_settings:
            mock_settings.return_value.llm_provider = "deepseek"
            mock_settings.return_value.llm_api_key = "sk-deepseek-test-key"
            mock_settings.return_value.llm_model_name = "deepseek-chat"

            provider = create_provider()
            assert isinstance(provider, DeepSeekProvider)

    def test_create_anthropic_provider(self):
        """Factory creates AnthropicProvider for 'anthropic' type."""
        with patch("app.llm_provider.get_settings") as mock_settings:
            mock_settings.return_value.llm_provider = "anthropic"
            mock_settings.return_value.llm_api_key = "sk-ant-test-key"
            mock_settings.return_value.llm_model_name = "claude-3-sonnet-20240229"

            provider = create_provider()
            assert isinstance(provider, AnthropicProvider)

    def test_create_provider_with_explicit_params(self):
        """Factory respects explicit parameters over settings."""
        with patch("app.llm_provider.get_settings") as mock_settings:
            mock_settings.return_value.llm_provider = "agent-zero"

            # Explicit params should override settings
            provider = create_provider(
                provider_type="featherless",
                api_key="fl-explicit-key",
                model="explicit-model"
            )

            assert isinstance(provider, FeatherlessProvider)
            assert provider.model == "explicit-model"

    def test_create_provider_unsupported_type(self):
        """Factory raises ValueError for unsupported provider type."""
        with patch("app.llm_provider.get_settings") as mock_settings:
            mock_settings.return_value.llm_provider = "unsupported-provider"

            with pytest.raises(ValueError) as exc_info:
                create_provider()

            assert "Unsupported LLM provider" in str(exc_info.value)


class TestPolicyRouting:
    """Test provider routing decisions used by the runtime."""

    def test_force_premium_is_deterministic(self):
        """Force premium always picks the same provider order."""
        allowed = ["deepseek", "anthropic", "openai"]
        first = resolve_provider_from_policy(None, "deepseek", allowed, "force_premium")
        second = resolve_provider_from_policy(None, "deepseek", allowed, "force_premium")
        assert first == second == "openai"

    def test_block_premium_chooses_non_premium_fallback(self):
        """Block premium falls back to an allowed non-premium provider."""
        provider = resolve_provider_from_policy("openai", "openai", ["deepseek", "openai"], "block_premium")
        assert provider == "deepseek"

    def test_block_premium_rejects_all_premium_configuration(self):
        """Block premium raises when no non-premium providers are available."""
        with pytest.raises(ValueError):
            resolve_provider_from_policy("openai", "openai", ["openai", "anthropic"], "block_premium")


class TestProviderIntegration:
    """Integration tests for provider switching."""

    @pytest.mark.asyncio
    async def test_complete_workflow_featherless(self):
        """Complete chat workflow using Featherless provider."""
        # Mock settings
        with patch("app.llm_provider.get_settings") as mock_settings:
            mock_settings.return_value.llm_provider = "featherless"
            mock_settings.return_value.llm_api_key = "fl-test-key"
            mock_settings.return_value.llm_model_name = "meta-llama-3.1-70b-instruct"

            # Create provider
            llm = create_provider()
            assert isinstance(llm, FeatherlessProvider)

            # Mock the actual API call
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "Test response"

            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

            with patch.object(FeatherlessProvider, '__init__', return_value=None):
                llm = FeatherlessProvider()
                llm.model = "meta-llama-3.1-70b-instruct"
                llm.client = mock_client

                # Execute chat
                result = await llm.chat_completion(
                    messages=[{"role": "user", "content": "Test message"}],
                    temperature=0.7,
                )

                assert result == "Test response"

    def test_provider_selection_from_env(self):
        """Provider selection respects environment variables."""
        with patch("app.llm_provider.get_settings") as mock_settings:
            # Simulate different .env configurations
            test_cases = [
                ("agent-zero", AgentZeroProvider),
                ("openai", OpenAIProvider),
                ("featherless", FeatherlessProvider),
                ("deepseek", DeepSeekProvider),
                ("anthropic", AnthropicProvider),
            ]

            for provider_type, expected_class in test_cases:
                mock_settings.return_value.llm_provider = provider_type
                mock_settings.return_value.llm_api_key = "test-key"
                mock_settings.return_value.llm_model_name = "test-model"
                mock_settings.return_value.llm_base_url = "http://localhost:5000"

                provider = create_provider()
                assert isinstance(provider, expected_class), f"Failed for {provider_type}"
