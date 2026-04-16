"""SSE streaming response formatter for OpenAI-compatible format."""
import json
import uuid
from datetime import datetime
from typing import AsyncGenerator
from app.schemas import ChatCompletionChunk, StreamChoice, DeltaContent


def create_chunk(
    completion_id: str,
    content: str | None = None,
    role: str | None = None,
    finish_reason: str | None = None,
    model: str = "carbon-agent",
) -> str:
    """Format a single SSE chunk in OpenAI streaming format."""
    chunk = ChatCompletionChunk(
        id=completion_id,
        created=int(datetime.now().timestamp()),
        model=model,
        choices=[
            StreamChoice(
                delta=DeltaContent(content=content, role=role),
                finish_reason=finish_reason,
            )
        ],
    )
    return f"data: {chunk.model_dump_json()}\n\n"


async def stream_response(content_generator: AsyncGenerator) -> AsyncGenerator[str, None]:
    """Convert an async content generator into SSE-formatted stream."""
    completion_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"

    # First chunk: role
    yield create_chunk(completion_id, role="assistant")

    # Content chunks
    async for chunk_text in content_generator:
        if chunk_text:
            yield create_chunk(completion_id, content=chunk_text)

    # Final chunk: done
    yield create_chunk(completion_id, finish_reason="stop")
    yield "data: [DONE]\n\n"
