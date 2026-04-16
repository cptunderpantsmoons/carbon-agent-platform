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


async def fake_stream_response(text: str) -> AsyncGenerator[str, None]:
    """Split complete text into word chunks and yield as SSE stream."""
    completion_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"

    # First chunk: role
    yield create_chunk(completion_id, role="assistant")

    # Split text into words and yield each as a chunk
    words = text.split()
    for word in words:
        # Re-add space that split() removed (except for last word)
        idx = text.find(word)
        suffix = " " if idx + len(word) < len(text) and text[idx + len(word)] == " " else ""
        yield create_chunk(completion_id, content=word + suffix)

    # Final chunk: done
    yield create_chunk(completion_id, finish_reason="stop")
    yield "data: [DONE]\n\n"
