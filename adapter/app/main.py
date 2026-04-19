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
from app.models import User
from app.metrics import RequestIDMiddleware, metrics_endpoint

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


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "carbon-agent-adapter"}


# Metrics endpoint for Prometheus scraping
app.add_api_route("/metrics", metrics_endpoint, methods=["GET"])


@app.get("/v1/models")
async def list_models(user: User = Depends(verify_api_key)):
    """List available models (returns carbon-agent for authenticated users)."""
    return {
        "object": "list",
        "data": [
            {
                "id": "carbon-agent",
                "object": "model",
                "created": 1700000000,
                "owned_by": "carbon-agent",
            }
        ],
    }


@app.post("/v1/chat/completions")
async def chat_completions(
    request: ChatCompletionRequest,
    user: User = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    """OpenAI-compatible chat completions endpoint.

    Routes requests to user's specific Docker container and
    fakes SSE streaming if client requested it.
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

    logger.info("chat_request", user_id=user.id, user_email=user.email, stream=request.stream)

    # Route to user's dedicated Docker container or fallback to shared endpoint
    base_url = _get_agent_base_url(user, settings)
    client = AgentClient(
        base_url=base_url,
        api_key=user.api_key,
    )

    # Always call agent non-streaming
    try:
        response_text = await client.send_message(user_message, user_id=user.id)
    except Exception as e:
        logger.error("agent_error", user_id=user.id, error=str(e))
        raise HTTPException(status_code=502, detail=f"Agent error: {str(e)}")

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
        model=settings.model_name,
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
