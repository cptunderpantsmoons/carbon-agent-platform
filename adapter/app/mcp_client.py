"""MCP (Model Context Protocol) client for obot gateway integration.

This module provides an async HTTP client for interacting with obot's MCP gateway,
enabling tool use (browser, search, code execution) through a standardized interface.

The client is designed to fail gracefully — if obot is unavailable or MCP is disabled,
operations return empty results or raise catchable exceptions without breaking the
main chat flow.
"""

from __future__ import annotations

import asyncio
from typing import Any, Optional
from dataclasses import dataclass

import httpx
import structlog


logger = structlog.get_logger()


@dataclass
class MCPTool:
    """Represents an available MCP tool."""

    name: str
    description: str
    parameters: dict[str, Any]


class MCPError(Exception):
    """Base exception for MCP client errors."""

    pass


class MCPTimeoutError(MCPError):
    """Raised when an MCP operation times out."""

    pass


class MCPConnectionError(MCPError):
    """Raised when unable to connect to MCP gateway."""

    pass


class MCPClient:
    """Async client for obot MCP gateway.

    Supports tool discovery and execution with configurable timeouts,
    connection pooling, and graceful degradation when MCP is disabled.

    Usage:
        client = get_mcp_client()
        tools = await client.list_tools()
        result = await client.call_tool("browser_search", {"query": "Python async"})
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        max_retries: Optional[int] = None,
        enabled: Optional[bool] = None,
    ):
        self._enabled = enabled if enabled is not None else False
        self._base_url = base_url or "http://obot-gateway:8080"
        self._timeout = timeout_seconds or 30.0
        self._max_retries = max_retries or 3

        # Lazy initialization — client created on first use
        self._client: Optional[httpx.AsyncClient] = None

    def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client with connection pooling."""
        if self._client is None:
            limits = httpx.Limits(max_connections=10, max_keepalive_connections=5)
            timeout = httpx.Timeout(self._timeout, connect=5.0)
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=timeout,
                limits=limits,
            )
        return self._client

    @property
    def enabled(self) -> bool:
        """Check if MCP is enabled in configuration."""
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        """Enable or disable MCP client."""
        self._enabled = value

    async def health_check(self) -> dict[str, Any]:
        """Check if MCP gateway is reachable and healthy.

        Returns:
            Health status dict with "status" key ("healthy", "degraded", "unavailable").

        Raises:
            MCPConnectionError: If gateway is unreachable (only if MCP enabled).
        """
        if not self._enabled:
            return {"status": "disabled", "message": "MCP is disabled in configuration"}

        client = self._get_client()
        try:
            response = await client.get("/health", timeout=5.0)
            response.raise_for_status()
            data = response.json()
            return {"status": "healthy", "gateway": data}
        except httpx.TimeoutException:
            logger.warning("mcp_health_check_timeout", base_url=self._base_url)
            return {"status": "degraded", "message": "Health check timed out"}
        except httpx.ConnectError as e:
            logger.error(
                "mcp_health_check_failed", error=str(e), base_url=self._base_url
            )
            if self._enabled:
                raise MCPConnectionError(
                    f"Cannot connect to MCP gateway at {self._base_url}"
                ) from e
            return {"status": "unavailable", "message": str(e)}
        except httpx.HTTPStatusError as e:
            logger.error("mcp_health_check_error", status=e.response.status_code)
            return {"status": "degraded", "message": f"HTTP {e.response.status_code}"}

    async def list_tools(self) -> list[MCPTool]:
        """List available MCP tools from the gateway registry.

        Returns:
            List of available tools. Empty list if MCP disabled or unavailable.
        """
        if not self._enabled:
            return []

        client = self._get_client()

        for attempt in range(self._max_retries):
            try:
                response = await client.get("/api/tools")
                response.raise_for_status()
                data = response.json()

                tools = [
                    MCPTool(
                        name=t["name"],
                        description=t.get("description", ""),
                        parameters=t.get("parameters", {}),
                    )
                    for t in data.get("tools", [])
                ]

                logger.info("mcp_tools_listed", count=len(tools))
                return tools

            except httpx.TimeoutException:
                logger.warning("mcp_list_tools_timeout", attempt=attempt + 1)
                if attempt == self._max_retries - 1:
                    return []
                await asyncio.sleep(0.5 * (attempt + 1))  # Exponential backoff

            except httpx.HTTPError as e:
                logger.error("mcp_list_tools_error", error=str(e))
                return []

        return []

    async def call_tool(
        self,
        tool_name: str,
        params: dict[str, Any],
        user_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Call an MCP tool via the gateway.

        Args:
            tool_name: Name of the tool to call (e.g., "browser_search").
            params: Tool-specific parameters.
            user_id: Optional user ID for audit logging and rate limiting.

        Returns:
            Tool execution result with "success" and "result" keys.

        Raises:
            MCPTimeoutError: If tool execution times out.
            MCPError: For other MCP-related errors.
        """
        if not self._enabled:
            raise MCPError("MCP is disabled in configuration")

        client = self._get_client()
        headers = {}
        if user_id:
            headers["X-User-ID"] = user_id

        logger.info("mcp_tool_call_start", tool=tool_name, user_id=user_id)

        try:
            response = await client.post(
                f"/api/tools/{tool_name}",
                json=params,
                headers=headers,
            )
            response.raise_for_status()
            result = response.json()

            logger.info(
                "mcp_tool_call_success",
                tool=tool_name,
                user_id=user_id,
                success=result.get("success", False),
            )
            return result

        except httpx.TimeoutException as e:
            logger.error("mcp_tool_call_timeout", tool=tool_name, timeout=self._timeout)
            raise MCPTimeoutError(
                f"Tool '{tool_name}' timed out after {self._timeout}s"
            ) from e

        except httpx.HTTPStatusError as e:
            logger.error(
                "mcp_tool_call_http_error",
                tool=tool_name,
                status=e.response.status_code,
                response=e.response.text[:200],
            )
            raise MCPError(
                f"Tool '{tool_name}' failed: HTTP {e.response.status_code}"
            ) from e

        except httpx.HTTPError as e:
            logger.error("mcp_tool_call_error", tool=tool_name, error=str(e))
            raise MCPConnectionError(
                f"Failed to call tool '{tool_name}': {str(e)}"
            ) from e

    async def close(self) -> None:
        """Close the HTTP client and release connections."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> MCPClient:
        """Async context manager entry."""
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Async context manager exit."""
        await self.close()


# Singleton instance for application-wide use
_mcp_client: Optional[MCPClient] = None


def get_mcp_client() -> MCPClient:
    """Get or create the singleton MCP client instance.

    Returns:
        Configured MCPClient (may be disabled if MCP_ENABLED=false).
    """
    global _mcp_client
    if _mcp_client is None:
        _mcp_client = MCPClient()
    return _mcp_client


async def reset_mcp_client() -> None:
    """Reset the singleton instance (useful for testing)."""
    global _mcp_client
    if _mcp_client is not None:
        await _mcp_client.close()
    _mcp_client = None
