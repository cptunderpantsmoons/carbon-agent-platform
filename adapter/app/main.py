"""OpenAI-compatible API adapter for Carbon Agent."""
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
import structlog

from app.schemas import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionChoice,
    ChatMessage,
)
from app.agent_client import AgentClient
from app.streaming import stream_response
from app.config import get_settings

logger = structlog.get_logger()
app = FastAPI(title="Carbon Agent OpenAI Adapter", version="1.0.0")


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
    """OpenAI-compatible chat completions endpoint."""
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

    if request.stream:
        content_gen = client.send_message_stream(user_message)
        return StreamingResponse(
            stream_response(content_gen),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    # Non-streaming response
    try:
        response_text = await client.send_message(user_message)
    except Exception as e:
        logger.error("agent_error", error=str(e))
        raise HTTPException(status_code=502, detail=f"Agent error: {str(e)}")

    return ChatCompletionResponse(
        model=settings.model_name,
        choices=[
            ChatCompletionChoice(
                message=ChatMessage(role="assistant", content=response_text)
            )
        ],
    )


@app.post("/v1/chat/completions/{conversation_id}")
async def chat_completions_with_conversation(
    conversation_id: str, request: ChatCompletionRequest
):
    """Chat completions with conversation context."""
    settings = get_settings()
    client = AgentClient()

    user_message = ""
    for msg in reversed(request.messages):
        if msg.role == "user":
            user_message = msg.content
            break

    if not user_message:
        raise HTTPException(status_code=400, detail="No user message found")

    if request.stream:
        content_gen = client.send_message_stream(user_message, conversation_id)
        return StreamingResponse(
            stream_response(content_gen),
            media_type="text/event-stream",
        )

    response_text = await client.send_message(user_message, conversation_id)
    return ChatCompletionResponse(
        model=settings.model_name,
        choices=[
            ChatCompletionChoice(
                message=ChatMessage(role="assistant", content=response_text)
            )
        ],
    )
