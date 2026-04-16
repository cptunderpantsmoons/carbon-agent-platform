"""OpenAI-compatible API adapter for Agent Zero."""
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
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

logger = structlog.get_logger()
app = FastAPI(title="Carbon Agent OpenAI Adapter", version="2.0.0")


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "carbon-agent-adapter"}


@app.get("/v1/models")
async def list_models():
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
async def chat_completions(request: ChatCompletionRequest):
    """OpenAI-compatible chat completions endpoint.

    Always calls Agent Zero (non-streaming), then fakes SSE stream
    if the client requested streaming.
    """
    settings = get_settings()
    client = AgentClient()

    # Extract the latest user message
    user_message = ""
    for msg in reversed(request.messages):
        if msg.role == "user":
            user_message = msg.content
            break

    if not user_message:
        raise HTTPException(status_code=400, detail="No user message found")

    logger.info("chat_request", user_id=settings.user_id, stream=request.stream)

    # Always call agent non-streaming
    try:
        response_text = await client.send_message(user_message)
    except Exception as e:
        logger.error("agent_error", error=str(e))
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
