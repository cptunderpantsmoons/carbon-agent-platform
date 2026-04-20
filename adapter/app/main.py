"""OpenAI-compatible API adapter for Agent Zero."""
from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.schemas import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionChoice,
    ChatMessage,
)
from app.agent_client import AgentClient
from app.streaming import fake_stream_response
from app.config import get_settings
from app.auth import verify_api_key, get_db
from app.models import User, UserStatus
from app.metrics import RequestIDMiddleware, metrics_endpoint
from app.mcp_client import get_mcp_client, MCPError, MCPClient
from app.llm_provider import create_provider, LLMProvider

logger = structlog.get_logger()
app = FastAPI(title="Carbon Agent OpenAI Adapter", version="2.0.0")

# Request ID and metrics middleware
app.add_middleware(RequestIDMiddleware)


def _get_agent_base_url(user: User, settings) -> str:
    """Determine the Agent Zero base URL for a specific user.

    Each user has a dedicated Docker container routed via Traefik.
    The URL pattern is based on the configured agent domain.
    """
    # Per-user container routing via Traefik path-based routing
    # Pattern: https://{agent_domain}/agent/{user_id}
    agent_domain = getattr(settings, 'agent_domain', '')
    if agent_domain and user.id:
        return f"https://{agent_domain}/agent/{user.id}"
    return settings.agent_api_url


async def _try_mcp_tool_enhancement(
    user_message: str,
    user_id: str,
) -> str:
    """Attempt to enhance message with MCP tool results.

    If MCP is enabled and the message appears to require tool use,
    this function discovers and calls appropriate tools, then augments
    the message with tool results for Agent Zero to use.

    If MCP is disabled or unavailable, returns the original message unchanged.

    Args:
        user_message: The user's original message.
        user_id: The authenticated user's ID.

    Returns:
        Original message or augmented message with tool results.
    """
    mcp = get_mcp_client()

    # Early exit if MCP is disabled
    if not mcp.enabled:
        return user_message

    # Tool detection keywords (expand based on your use case)
    tool_keywords = [
        "search", "find", "look up", "research", "browse",
        "execute code", "run code", "python",
        "navigate", "open url", "website",
        "analyze", "process", "extract"
    ]

    # Check if message likely needs tool use
    message_lower = user_message.lower()
    needs_tool = any(keyword in message_lower for keyword in tool_keywords)

    if not needs_tool:
        return user_message

    try:
        # Discover available tools
        tools = await mcp.list_tools()

        if not tools:
            logger.info("mcp_no_tools_available", user_id=user_id)
            return user_message

        # Select appropriate tool based on message content
        selected_tool = _select_tool_for_message(tools, message_lower)

        if selected_tool is None:
            return user_message

        # Execute the tool
        logger.info(
            "mcp_tool_execution_start",
            tool=selected_tool.name,
            user_id=user_id,
        )

        tool_params = _extract_tool_params(selected_tool, user_message)
        result = await mcp.call_tool(
            selected_tool.name,
            tool_params,
            user_id=user_id
        )

        if result.get("success"):
            # Augment message with tool results
            tool_result = result.get("result", "")
            augmented_message = (
                f"{user_message}\n\n"
                f"[Tool: {selected_tool.name}]\n"
                f"Results: {tool_result}"
            )
            logger.info(
                "mcp_tool_augmentation_success",
                tool=selected_tool.name,
                user_id=user_id,
            )
            return augmented_message
        else:
            logger.warning(
                "mcp_tool_execution_failed",
                tool=selected_tool.name,
                user_id=user_id,
                error=result.get("error", "unknown"),
            )
            return user_message

    except MCPError as e:
        # Graceful degradation — continue without tool results
        logger.warning(
            "mcp_tool_error_fallback",
            user_id=user_id,
            error=str(e),
        )
        return user_message
    except Exception as e:
        # Catch-all for unexpected errors
        logger.error(
            "mcp_unexpected_error",
            user_id=user_id,
            error=str(e),
        )
        return user_message


def _select_tool_for_message(
    tools: list,
    message_lower: str,
) -> object | None:
    """Select the most appropriate tool for the given message.

    Args:
        tools: List of available MCPTool objects.
        message_lower: Lowercased user message.

    Returns:
        Best matching tool or None if no match.
    """
    # Simple keyword-based tool selection
    # Can be enhanced with LLM-based tool selection in the future
    tool_selection_rules = {
        "search": ["search", "find", "look up", "research"],
        "browser": ["browse", "navigate", "open url", "website"],
        "code": ["execute code", "run code", "python", "script"],
    }

    for tool in tools:
        tool_name_lower = tool.name.lower()

        # Direct name match
        if tool_name_lower in message_lower:
            return tool

        # Keyword-based match
        for keyword_category, keywords in tool_selection_rules.items():
            if keyword_category in tool_name_lower:
                if any(kw in message_lower for kw in keywords):
                    return tool

    return None


def _extract_tool_params(
    tool: object,
    message: str,
) -> dict:
    """Extract parameters for the selected tool from the user message.

    This is a simple implementation — can be enhanced with regex or LLM extraction.

    Args:
        tool: The selected MCPTool object.
        message: The user's message.

    Returns:
        Dictionary of parameters for the tool.
    """
    # Default parameter extraction
    # For search tools, use the entire message as the query
    if "search" in tool.name.lower():
        return {"query": message, "max_results": 5}

    if "browser" in tool.name.lower():
        # Try to extract URL from message
        import re
        url_match = re.search(r'https?://\S+', message)
        if url_match:
            return {"url": url_match.group(0)}
        return {"query": message}

    if "code" in tool.name.lower():
        return {"code": message}

    # Fallback: pass the entire message as a generic parameter
    return {"input": message}


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "carbon-agent-adapter"}


# Metrics endpoint for Prometheus scraping
app.add_api_route("/metrics", metrics_endpoint, methods=["GET"])


@app.get("/v1/models")
async def list_models(user: User = Depends(verify_api_key)):
    """List available models (returns current LLM provider model)."""
    settings = get_settings()
    
    return {
        "object": "list",
        "data": [
            {
                "id": settings.llm_model_name,
                "object": "model",
                "created": 1700000000,
                "owned_by": settings.llm_provider,
            }
        ],
    }


@app.post("/v1/chat/completions")
async def chat_completions(
    request: ChatCompletionRequest,
    user: User = Depends(verify_api_key),
):
    """OpenAI-compatible chat completions endpoint.

    Routes requests to the configured LLM provider (Agent Zero, OpenAI,
    Featherless AI, or Anthropic) and fakes SSE streaming if client requested it.

    If MCP is enabled, attempts to enhance the message with tool results
    before sending to the LLM provider.
    """
    settings = get_settings()

    # Extract the latest user message
    user_message = ""
    for msg in reversed(request.messages):
        if msg.role == "user":
            user_message = msg.content
            break

    if not user_message:
        raise HTTPException(status_code=400, detail="No user message found")

    logger.info(
        "chat_request",
        user_id=user.id,
        user_email=user.email,
        stream=request.stream,
        llm_provider=settings.llm_provider,
    )

    # Automatically detect optimal temperature based on task type
    temperature = detect_and_apply_temperature(
        messages=[msg.model_dump() for msg in request.messages],
        current_temperature=request.temperature if hasattr(request, 'temperature') else None,
        provider=settings.llm_provider,
    )

    # Detect task type for logging
    task_type = detect_task_type(user_message)
    task_description = get_task_description(task_type)

    logger.info(
        "task_detection",
        user_id=user.id,
        detected_task=task_description,
        auto_temperature=temperature,
    )

    # MCP tool enhancement (optional, fails gracefully)
    if settings.mcp_enabled:
        try:
            user_message = await _try_mcp_tool_enhancement(user_message, user.id)
        except Exception as e:
            logger.error("mcp_enhancement_failed", user_id=user.id, error=str(e))
            # Continue without MCP enhancement

    # Route to appropriate LLM provider
    if settings.llm_provider == "agent-zero":
        # Use Agent Zero with per-user container routing
        base_url = _get_agent_base_url(user, settings)
        client = AgentClient(
            base_url=base_url,
            api_key=user.api_key,
        )
        
        try:
            response_text = await client.send_message(user_message, user_id=user.id)
        except Exception as e:
            logger.error("agent_error", user_id=user.id, error=str(e))
            raise HTTPException(status_code=502, detail=f"Agent error: {str(e)}")
    else:
        # Use cloud LLM provider (OpenAI, Featherless, Anthropic)
        llm = create_provider()
        
        try:
            response_text = await llm.chat_completion(
                messages=[msg.model_dump() for msg in request.messages],
                temperature=request.temperature if hasattr(request, 'temperature') else 0.7,
                max_tokens=request.max_tokens if hasattr(request, 'max_tokens') else None,
                stream=request.stream,
            )
        except Exception as e:
            logger.error(
                "llm_provider_error",
                user_id=user.id,
                provider=settings.llm_provider,
                error=str(e),
            )
            raise HTTPException(
                status_code=502,
                detail=f"LLM provider error ({settings.llm_provider}): {str(e)}"
            )

    if request.stream:
        # Fake-stream the complete response as SSE word chunks
        return StreamingResponse(
            fake_stream_response(response_text),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    # Non-streaming response
    return ChatCompletionResponse(
        model=settings.llm_model_name,
        choices=[
            ChatCompletionChoice(
                message=ChatMessage(role="assistant", content=response_text)
            )
        ],
    )


@app.get("/v1/user")
async def get_user_info(user: User = Depends(verify_api_key)):
    """Get current authenticated user information."""
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "status": user.status,
        "has_service": user.status == UserStatus.ACTIVE,
    }
    }
        ],
    )


@app.get("/v1/user")
async def get_user_info(user: User = Depends(verify_api_key)):
    """Get current authenticated user information."""
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "status": user.status,
        "has_service": user.status == UserStatus.ACTIVE,
    }
