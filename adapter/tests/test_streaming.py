"""Tests for SSE streaming formatter."""
import asyncio
import json
from app.streaming import create_chunk, stream_response


def test_create_chunk_with_content():
    chunk = create_chunk("chatcmpl-abc123", content="Hello")
    assert chunk.startswith("data: ")
    assert "Hello" in chunk
    assert "chatcmpl-abc123" in chunk


def test_create_chunk_with_role():
    chunk = create_chunk("chatcmpl-abc123", role="assistant")
    data = json.loads(chunk.strip().replace("data: ", ""))
    assert data["choices"][0]["delta"]["role"] == "assistant"
    assert data["choices"][0]["delta"]["content"] is None


def test_create_chunk_finish():
    chunk = create_chunk("chatcmpl-abc123", finish_reason="stop")
    data = json.loads(chunk.strip().replace("data: ", ""))
    assert data["choices"][0]["finish_reason"] == "stop"


async def test_stream_response_yields_chunks():
    async def content_gen():
        yield "Hello"
        yield " World"

    chunks = []
    async for chunk in stream_response(content_gen()):
        chunks.append(chunk)

    # Should have: role chunk, 2 content chunks, finish chunk, [DONE]
    assert len(chunks) == 5
    assert chunks[-1] == "data: [DONE]\n\n"
    assert "Hello" in chunks[1]
    assert "World" in chunks[2]
