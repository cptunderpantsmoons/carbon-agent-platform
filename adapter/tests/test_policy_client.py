"""Tests for the adapter policy client."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.runtime.policy_client import PolicyClient


@pytest.mark.asyncio
async def test_fetch_policy_sends_admin_key_header():
    """The adapter should authenticate policy fetches with the admin key."""
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {
        "routing_mode": "auto",
        "default_provider": "featherless",
        "allowed_providers": ["featherless", "deepseek"],
        "benchmark_mode": True,
    }

    mock_client = MagicMock()
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("app.runtime.policy_client.get_settings") as mock_settings, patch.object(
        PolicyClient, "_get_client", return_value=mock_client
    ):
        mock_settings.return_value = MagicMock(
            orchestrator_url="http://orchestrator:8000",
            admin_agent_api_key="test-admin-key",
        )

        client = PolicyClient()
        policy = await client.fetch_policy("tenant-123")

    assert policy.routing_mode == "auto"
    assert policy.default_provider == "featherless"
    mock_client.get.assert_awaited_once()
    assert mock_client.get.call_args.kwargs["headers"]["X-Admin-Key"] == "test-admin-key"
