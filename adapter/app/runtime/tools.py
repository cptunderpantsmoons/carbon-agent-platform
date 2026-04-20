"""Tool registration for pydantic-ai runtime.

Replaces keyword-based MCP augmentation with explicit tool registration.
MCP surfaces are discovered and registered as first-class pydantic-ai tools.
"""
from typing import Callable, Awaitable
import structlog

from pydantic_ai import Tool

from app.mcp_client import get_mcp_client, MCPError
from app.config import get_settings

logger = structlog.get_logger()

# Sensitive tools requiring approval before execution
_SENSITIVE_TOOL_PREFIXES = [
    "legal_draft",
    "financial_output",
    "regulatory_submission",
    "cer_registry",
]


def _is_sensitive(tool_name: str) -> bool:
    tn = tool_name.lower()
    return any(tn.startswith(p) or p in tn for p in _SENSITIVE_TOOL_PREFIXES)


async def discover_mcp_tools() -> list[Tool]:
    """Discover available tools from the MCP gateway and wrap as pydantic-ai Tools."""
    settings = get_settings()
    if not settings.mcp_enabled:
        return []

    mcp = get_mcp_client()
    if not mcp.enabled:
        return []

    try:
        raw_tools = await mcp.list_tools()
    except MCPError as e:
        logger.warning("mcp_discover_failed", error=str(e))
        return []

    pydantic_tools: list[Tool] = []
    for t in raw_tools:
        tool_name = t.name
        tool_desc = t.description or f"Call {tool_name} via MCP"

        # Build an async callable wrapper
        async def _mcp_wrapper(
            *args,
            _tool_name: str = tool_name,
            _mcp=mcp,
            **kwargs,
        ) -> str:
            params = kwargs or (args[0] if args else {})
            if not isinstance(params, dict):
                params = {"input": str(params)}
            result = await _mcp.call_tool(_tool_name, params)
            if result.get("success"):
                return str(result.get("result", ""))
            return f"Tool error: {result.get('error', 'unknown')}"

        # Attach parameter schema if available
        parameters = getattr(t, "parameters", None) or {}

        pydantic_tools.append(
            Tool(
                _mcp_wrapper,
                name=tool_name,
                description=tool_desc,
                takes_ctx=False,
            )
        )
        logger.info("mcp_tool_registered", tool=tool_name, sensitive=_is_sensitive(tool_name))

    return pydantic_tools


async def get_registered_tools(
    tool_policy: str = "auto",
    require_approval: bool = False,
) -> list[Tool]:
    """Get the full tool registry for an agent run.

    Args:
        tool_policy: 'auto', 'disabled', 'require_approval'
        require_approval: Whether to gate sensitive tools

    Returns:
        List of pydantic-ai Tool instances
    """
    if tool_policy == "disabled":
        return []

    tools: list[Tool] = []

    # MCP tools
    mcp_tools = await discover_mcp_tools()
    if require_approval or tool_policy == "require_approval":
        # Wrap sensitive tools with approval gate
        for t in mcp_tools:
            if _is_sensitive(t.name):
                t = _wrap_with_approval(t)
            tools.append(t)
    else:
        tools.extend(mcp_tools)

    return tools


def _wrap_with_approval(tool: Tool) -> Tool:
    """Wrap a tool so it returns an approval request instead of executing."""
    original = tool.function

    async def _approval_gate(*args, **kwargs) -> str:
        return (
            f"[APPROVAL REQUIRED] Tool '{tool.name}' was called but requires "
            f"human approval before execution. Please review and approve in the UI."
        )

    return Tool(
        _approval_gate,
        name=tool.name,
        description=f"{tool.description or ''} (requires approval)",
        takes_ctx=tool.takes_ctx,
    )
