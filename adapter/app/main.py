"""Carbon Agent OpenAI Adapter — pydantic-ai runtime with compatibility layer.

Provides:
- /v1/chat/completions   (OpenAI-compatible, backward compatible)
- /v1/agent/run          (new internal execution path)
- /v1/models, /v1/user, /health, /metrics
"""

import uuid
from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import StreamingResponse
import structlog

from app.schemas import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionChoice,
    ChatMessage,
)
from app.streaming import fake_stream_response
from app.config import get_settings
from app.auth import verify_api_key
from app.models import User, UserStatus
from app.metrics import RequestIDMiddleware, metrics_endpoint

# New pydantic-ai runtime
from app.runtime import (
    AgentExecutionRequest,
    AgentExecutionResult,
    RuntimeDeps,
    execute_agent_run,
    ChatMessage as RuntimeChatMessage,
)

# Legacy imports — kept during transition, will be removed in Wave 5
from app.agent_client import AgentClient

logger = structlog.get_logger()
app = FastAPI(title="Carbon Agent OpenAI Adapter", version="2.1.0")

# Request ID and metrics middleware
app.add_middleware(RequestIDMiddleware)


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

    Backward-compatible surface. Routes through the new pydantic-ai runtime
    for all providers except the deprecated 'agent-zero' mode, which falls
    back to the legacy AgentClient.
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

    # Legacy Agent Zero path — kept for transition compatibility
    if settings.llm_provider == "agent-zero":
        agent_domain = getattr(settings, "agent_domain", "")
        base_url = (
            f"https://{agent_domain}/agent/{user.id}"
            if agent_domain and user.id
            else settings.agent_api_url
        )
        client = AgentClient(base_url=base_url, api_key=user.api_key)
        try:
            response_text = await client.send_message(user_message, user_id=user.id)
        except Exception as e:
            logger.error("agent_zero_legacy_error", user_id=user.id, error=str(e))
            raise HTTPException(status_code=502, detail=f"Agent error: {str(e)}")

        if request.stream:
            return StreamingResponse(
                fake_stream_response(response_text),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )
        return ChatCompletionResponse(
            model=settings.llm_model_name,
            choices=[
                ChatCompletionChoice(
                    message=ChatMessage(role="assistant", content=response_text)
                )
            ],
        )

    # ── New pydantic-ai runtime path ─────────────────────────────────────────
    trace_id = str(uuid.uuid4())

    runtime_request = AgentExecutionRequest(
        user_id=user.id,
        tenant_id="default",
        conversation_id=None,
        provider=settings.llm_provider,
        model=request.model,
        task_type="chat",
        temperature=request.temperature,
        max_tokens=request.max_tokens,
        stop=request.stop,
        messages=[
            RuntimeChatMessage(
                role=m.role,
                content=m.content,
                name=m.name,
                tool_call_id=m.tool_call_id,
            )
            for m in request.messages
        ],
        stream=request.stream,
    )

    deps = RuntimeDeps.from_request(runtime_request, trace_id=trace_id)

    try:
        result: AgentExecutionResult = await execute_agent_run(runtime_request, deps)
    except Exception as e:
        logger.error(
            "runtime_execution_failed",
            user_id=user.id,
            trace_id=trace_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        raise HTTPException(
            status_code=502,
            detail=f"Runtime execution failed: {str(e)}",
        )

    if request.stream:
        return StreamingResponse(
            fake_stream_response(result.output_text),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    return ChatCompletionResponse(
        model=result.model,
        choices=[
            ChatCompletionChoice(
                message=ChatMessage(role="assistant", content=result.output_text)
            )
        ],
    )


@app.post("/v1/agent/run")
async def agent_run(
    request: AgentExecutionRequest,
    user: User = Depends(verify_api_key),
):
    """New internal execution path for the Intelligence Hub runtime.

    Accepts the normalized AgentExecutionRequest and returns a normalized
    AgentExecutionResult with full observability metadata.
    """
    trace_id = str(uuid.uuid4())
    deps = RuntimeDeps.from_request(request, trace_id=trace_id)

    logger.info(
        "agent_run_request",
        trace_id=trace_id,
        user_id=user.id,
        task_type=request.task_type,
        provider=request.provider,
    )

    try:
        result = await execute_agent_run(request, deps)
    except Exception as e:
        logger.error(
            "agent_run_failed",
            trace_id=trace_id,
            user_id=user.id,
            error=str(e),
            error_type=type(e).__name__,
        )
        raise HTTPException(
            status_code=502,
            detail=f"Agent run failed: {str(e)}",
        )

    return result


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
