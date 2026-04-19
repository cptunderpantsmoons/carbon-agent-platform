"""Comprehensive unit tests for MCP client integration with obot gateway.

Tests cover:
- Connection establishment and error handling
- Tool discovery and registration
- Request/response serialization
- Fallback mechanisms when tools are unavailable
- Timeout and retry behavior
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import httpx

from app.mcp_client import (
    MCPClient,
    MCPTool,
    MCPError,
    MCPTimeoutError,
    MCPConnectionError,
    get_mcp_client,
    reset_mcp_client,
)


class TestMCPClientInitialization:
    """Test MCP client initialization and configuration."""

    def test_default_initialization(self):
        """Client initializes with disabled MCP by default."""
        client = MCPClient()
        assert client.enabled is False
        assert client._base_url == "http://obot-gateway:8080"
        assert client._timeout == 30.0
        assert client._max_retries == 3

    def test_custom_initialization(self):
        """Client accepts custom configuration."""
        client = MCPClient(
            base_url="http://custom-gateway:9090",
            timeout_seconds=60.0,
            max_retries=5,
            enabled=True,
        )
        assert client.enabled is True
        assert client._base_url == "http://custom-gateway:9090"
        assert client._timeout == 60.0
        assert client._max_retries == 5

    def test_enabled_property_setter(self):
        """Enable/disable can be changed after initialization."""
        client = MCPClient(enabled=False)
        assert client.enabled is False
        client.enabled = True
        assert client.enabled is True


class TestMCPClientHealthCheck:
    """Test health check endpoint behavior."""

    @pytest.mark.asyncio
    async def test_health_check_when_disabled(self):
        """Returns disabled status when MCP is not enabled."""
        client = MCPClient(enabled=False)
        result = await client.health_check()
        assert result["status"] == "disabled"
        assert "MCP is disabled" in result["message"]

    @pytest.mark.asyncio
    async def test_health_check_success(self):
        """Returns healthy status when gateway responds."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"version": "1.0.0", "status": "ok"}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response

        with patch.object(MCPClient, '_get_client', return_value=mock_client):
            client = MCPClient(enabled=True)
            result = await client.health_check()

            assert result["status"] == "healthy"
            assert result["gateway"]["version"] == "1.0.0"

    @pytest.mark.asyncio
    async def test_health_check_timeout(self):
        """Returns degraded status on timeout."""
        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.TimeoutException("Connection timed out")

        with patch.object(MCPClient, '_get_client', return_value=mock_client):
            client = MCPClient(enabled=True)
            result = await client.health_check()

            assert result["status"] == "degraded"
            assert "timed out" in result["message"]

    @pytest.mark.asyncio
    async def test_health_check_connection_error(self):
        """Raises MCPConnectionError when gateway unreachable."""
        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.ConnectError("Connection refused")

        with patch.object(MCPClient, '_get_client', return_value=mock_client):
            client = MCPClient(enabled=True)

            with pytest.raises(MCPConnectionError) as exc_info:
                await client.health_check()

            assert "Cannot connect to MCP gateway" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_health_check_http_error(self):
        """Returns degraded status on HTTP errors."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server Error", request=MagicMock(), response=mock_response
        )

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response

        with patch.object(MCPClient, '_get_client', return_value=mock_client):
            client = MCPClient(enabled=True)
            result = await client.health_check()

            assert result["status"] == "degraded"
            assert "HTTP 500" in result["message"]


class TestMCPToolDiscovery:
    """Test tool listing and discovery functionality."""

    @pytest.mark.asyncio
    async def test_list_tools_when_disabled(self):
        """Returns empty list when MCP is disabled."""
        client = MCPClient(enabled=False)
        tools = await client.list_tools()
        assert tools == []

    @pytest.mark.asyncio
    async def test_list_tools_success(self):
        """Successfully retrieves tool list from gateway."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "tools": [
                {
                    "name": "browser_search",
                    "description": "Search the web",
                    "parameters": {"query": "string", "max_results": "integer"}
                },
                {
                    "name": "code_executor",
                    "description": "Execute Python code",
                    "parameters": {"code": "string"}
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response

        with patch.object(MCPClient, '_get_client', return_value=mock_client):
            client = MCPClient(enabled=True)
            tools = await client.list_tools()

            assert len(tools) == 2
            assert tools[0].name == "browser_search"
            assert tools[0].description == "Search the web"
            assert "query" in tools[0].parameters
            assert tools[1].name == "code_executor"

    @pytest.mark.asyncio
    async def test_list_tools_empty_response(self):
        """Handles empty tool list gracefully."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"tools": []}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response

        with patch.object(MCPClient, '_get_client', return_value=mock_client):
            client = MCPClient(enabled=True)
            tools = await client.list_tools()

            assert tools == []

    @pytest.mark.asyncio
    async def test_list_tools_timeout_returns_empty(self):
        """Returns empty list on timeout (no exception)."""
        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.TimeoutException("Request timed out")

        with patch.object(MCPClient, '_get_client', return_value=mock_client):
            client = MCPClient(enabled=True, max_retries=1)
            tools = await client.list_tools()

            # Should return empty list, not raise exception
            assert tools == []

    @pytest.mark.asyncio
    async def test_list_tools_http_error_returns_empty(self):
        """Returns empty list on HTTP error (graceful degradation)."""
        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.HTTPError("Internal server error")

        with patch.object(MCPClient, '_get_client', return_value=mock_client):
            client = MCPClient(enabled=True)
            tools = await client.list_tools()

            assert tools == []

    @pytest.mark.asyncio
    async def test_list_tools_retries_on_timeout(self):
        """Retries with exponential backoff on timeout."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "tools": [{"name": "search", "description": "Search", "parameters": {}}]
        }
        mock_response.raise_for_status = MagicMock()

        call_count = 0
        async def mock_get(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise httpx.TimeoutException("Timeout")
            return mock_response

        mock_client = AsyncMock()
        mock_client.get = mock_get

        with patch.object(MCPClient, '_get_client', return_value=mock_client):
            client = MCPClient(enabled=True, max_retries=3)
            tools = await client.list_tools()

            assert call_count == 3  # All 3 attempts made
            assert len(tools) == 1


class TestMCPToolExecution:
    """Test tool call execution and error handling."""

    @pytest.mark.asyncio
    async def test_call_tool_when_disabled_raises_error(self):
        """Raises MCPError when MCP is disabled."""
        client = MCPClient(enabled=False)

        with pytest.raises(MCPError) as exc_info:
            await client.call_tool("browser_search", {"query": "test"})

        assert "MCP is disabled" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_call_tool_success(self):
        """Successfully calls tool and returns result."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "success": True,
            "result": {"results": ["page1", "page2"]},
            "tool_name": "browser_search"
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response

        with patch.object(MCPClient, '_get_client', return_value=mock_client):
            client = MCPClient(enabled=True)
            result = await client.call_tool(
                "browser_search",
                {"query": "Python async programming"},
                user_id="user-123"
            )

            assert result["success"] is True
            assert "results" in result["result"]
            
            # Verify correct endpoint was called
            mock_client.post.assert_called_once()
            call_args = mock_client.post.call_args
            assert "/api/tools/browser_search" in call_args[0][0]
            assert call_args[1]["json"] == {"query": "Python async programming"}
            assert call_args[1]["headers"]["X-User-ID"] == "user-123"

    @pytest.mark.asyncio
    async def test_call_tool_without_user_id(self):
        """Calls tool without user ID header when not provided."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"success": True, "result": "ok"}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response

        with patch.object(MCPClient, '_get_client', return_value=mock_client):
            client = MCPClient(enabled=True)
            await client.call_tool("search", {"query": "test"})

            call_args = mock_client.post.call_args
            assert call_args[1]["headers"] == {}

    @pytest.mark.asyncio
    async def test_call_tool_timeout_raises_error(self):
        """Raises MCPTimeoutError on tool execution timeout."""
        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.TimeoutException("Request timed out")

        with patch.object(MCPClient, '_get_client', return_value=mock_client):
            client = MCPClient(enabled=True, timeout_seconds=30.0)

            with pytest.raises(MCPTimeoutError) as exc_info:
                await client.call_tool("browser_search", {"query": "test"})

            assert "timed out after 30.0s" in str(exc_info.value)
            assert "browser_search" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_call_tool_http_error_raises_mcp_error(self):
        """Raises MCPError on HTTP errors."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = '{"error": "Tool not found"}'
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Not Found", request=MagicMock(), response=mock_response
        )

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response

        with patch.object(MCPClient, '_get_client', return_value=mock_client):
            client = MCPClient(enabled=True)

            with pytest.raises(MCPError) as exc_info:
                await client.call_tool("nonexistent_tool", {})

            assert "HTTP 404" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_call_tool_connection_error_raises_connection_error(self):
        """Raises MCPConnectionError on connection failures."""
        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.ConnectError("Connection refused")

        with patch.object(MCPClient, '_get_client', return_value=mock_client):
            client = MCPClient(enabled=True)

            with pytest.raises(MCPConnectionError) as exc_info:
                await client.call_tool("browser_search", {"query": "test"})

            assert "Failed to call tool 'browser_search'" in str(exc_info.value)


class TestMCPClientLifecycle:
    """Test client lifecycle management."""

    @pytest.mark.asyncio
    async def test_close_releases_connections(self):
        """Close method properly releases HTTP client."""
        mock_http_client = AsyncMock()

        client = MCPClient(enabled=True)
        client._client = mock_http_client

        await client.close()

        mock_http_client.aclose.assert_called_once()
        assert client._client is None

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Async context manager properly manages lifecycle."""
        async with MCPClient(enabled=True) as client:
            assert client.enabled is True
            assert client._client is None  # Lazy initialization

        # After context exit, client should be cleaned up
        assert client._client is None

    @pytest.mark.asyncio
    async def test_singleton_get_mcp_client(self):
        """get_mcp_client returns singleton instance."""
        await reset_mcp_client()  # Ensure clean state

        client1 = get_mcp_client()
        client2 = get_mcp_client()

        assert client1 is client2  # Same instance

        await reset_mcp_client()  # Cleanup

    @pytest.mark.asyncio
    async def test_reset_mcp_client(self):
        """reset_mcp_client clears singleton and closes connection."""
        mock_http_client = AsyncMock()
        
        client = MCPClient()
        client._client = mock_http_client

        # Manually set the singleton
        import app.mcp_client as mcp_module
        mcp_module._mcp_client = client

        await reset_mcp_client()

        mock_http_client.aclose.assert_called_once()
        assert mcp_module._mcp_client is None


class TestMCPToolSerialization:
    """Test MCP tool data structure serialization."""

    def test_mcp_tool_dataclass(self):
        """MCPTool can be created and accessed."""
        tool = MCPTool(
            name="search",
            description="Search the web",
            parameters={"query": "string", "limit": "integer"}
        )

        assert tool.name == "search"
        assert tool.description == "Search the web"
        assert tool.parameters == {"query": "string", "limit": "integer"}

    def test_mcp_tool_to_dict(self):
        """MCPTool can be converted to dict."""
        tool = MCPTool(
            name="code_exec",
            description="Execute code",
            parameters={"code": "string"}
        )

        tool_dict = {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters
        }

        assert tool_dict["name"] == "code_exec"
        assert "code" in tool_dict["parameters"]

    def test_mcp_tool_from_registry_response(self):
        """MCPTool can be created from registry JSON response."""
        registry_response = {
            "name": "browser_navigate",
            "description": "Navigate to URL",
            "parameters": {
                "url": "string",
                "timeout": "integer"
            }
        }

        tool = MCPTool(
            name=registry_response["name"],
            description=registry_response.get("description", ""),
            parameters=registry_response.get("parameters", {})
        )

        assert tool.name == "browser_navigate"
        assert tool.parameters["url"] == "string"


class TestMCPFallbackMechanisms:
    """Test fallback behavior when tools are unavailable."""

    @pytest.mark.asyncio
    async def test_fallback_when_gateway_unreachable(self):
        """Operations fail gracefully when gateway is down."""
        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.ConnectError("Gateway unreachable")
        mock_client.post.side_effect = httpx.ConnectError("Gateway unreachable")

        with patch.object(MCPClient, '_get_client', return_value=mock_client):
            client = MCPClient(enabled=True)

            # list_tools should return empty list, not raise
            tools = await client.list_tools()
            assert tools == []

            # call_tool should raise MCPConnectionError (catchable)
            with pytest.raises(MCPConnectionError):
                await client.call_tool("search", {"query": "test"})

    @pytest.mark.asyncio
    async def test_fallback_to_agent_zero_when_mcp_fails(self):
        """Pattern for falling back to Agent Zero when MCP unavailable."""
        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.TimeoutException("Timeout")

        with patch.object(MCPClient, '_get_client', return_value=mock_client):
            client = MCPClient(enabled=True)

            # Simulate fallback pattern
            try:
                result = await client.call_tool("search", {"query": "test"})
                tool_result = result.get("result", "")
            except MCPError:
                # Fallback: use Agent Zero directly
                tool_result = ""  # Would call agent_zero.send_message()

            assert tool_result == ""  # Fell back successfully

    @pytest.mark.asyncio
    async def test_partial_tool_availability(self):
        """Some tools available, others not."""
        # Simulate scenario where list_tools succeeds but some calls fail
        mock_tools_response = MagicMock()
        mock_tools_response.json.return_value = {
            "tools": [
                {"name": "search", "description": "Search", "parameters": {}},
                {"name": "browser", "description": "Browser", "parameters": {}}
            ]
        }
        mock_tools_response.raise_for_status = MagicMock()

        mock_call_response = MagicMock()
        mock_call_response.json.return_value = {"success": False, "result": "Tool unavailable"}
        mock_call_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "503", request=MagicMock(), response=MagicMock(status_code=503)
        )

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_tools_response
        mock_client.post.return_value = mock_call_response

        with patch.object(MCPClient, '_get_client', return_value=mock_client):
            client = MCPClient(enabled=True)

            # Tool list succeeds
            tools = await client.list_tools()
            assert len(tools) == 2

            # But individual tool call may fail
            with pytest.raises(MCPError):
                await client.call_tool("browser", {})


class TestMCPIntegrationScenarios:
    """Test realistic integration scenarios."""

    @pytest.mark.asyncio
    async def test_complete_workflow_discover_and_call(self):
        """Complete workflow: list tools, select one, execute."""
        # Setup mock responses
        tools_response = MagicMock()
        tools_response.json.return_value = {
            "tools": [
                {"name": "web_search", "description": "Search web", "parameters": {"q": "string"}}
            ]
        }
        tools_response.raise_for_status = MagicMock()

        call_response = MagicMock()
        call_response.json.return_value = {
            "success": True,
            "result": {"results": ["result1", "result2"]}
        }
        call_response.raise_for_status = MagicMock()

        call_count = 0
        async def mock_get(*args, **kwargs):
            return tools_response
        
        async def mock_post(*args, **kwargs):
            return call_response

        mock_client = AsyncMock()
        mock_client.get = mock_get
        mock_client.post = mock_post

        with patch.object(MCPClient, '_get_client', return_value=mock_client):
            client = MCPClient(enabled=True)

            # Step 1: Discover tools
            tools = await client.list_tools()
            assert len(tools) == 1

            # Step 2: Call selected tool
            result = await client.call_tool(
                tools[0].name,
                {"q": "Python asyncio"}
            )
            assert result["success"] is True
            assert len(result["result"]["results"]) == 2

    @pytest.mark.asyncio
    async def test_concurrent_tool_calls(self):
        """Multiple concurrent tool calls work correctly."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"success": True, "result": "ok"}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response

        with patch.object(MCPClient, '_get_client', return_value=mock_client):
            client = MCPClient(enabled=True)

            # Execute multiple tools concurrently
            results = await asyncio.gather(
                client.call_tool("search", {"q": "python"}),
                client.call_tool("search", {"q": "async"}),
                client.call_tool("search", {"q": "io"}),
            )

            assert len(results) == 3
            assert all(r["success"] for r in results)


def test_mcp_error_exception_hierarchy():
    """Verify exception inheritance for proper error handling."""
    assert issubclass(MCPTimeoutError, MCPError)
    assert issubclass(MCPConnectionError, MCPError)

    # Can catch MCPError to handle all MCP errors
    for error_class in [MCPTimeoutError, MCPConnectionError]:
        try:
            raise error_class("Test error")
        except MCPError:
            pass  # Successfully caught


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
