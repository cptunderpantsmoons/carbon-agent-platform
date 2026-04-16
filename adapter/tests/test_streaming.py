"""Tests for SSE streaming formatter."""
import asyncio
import json
from app.streaming import create_chunk, fake_stream_response


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


async def test_fake_stream_response_yields_word_chunks():
    chunks = []
    async for chunk in fake_stream_response("Hello World Foo"):
        chunks.append(chunk)

    # Should have: role chunk, 3 word chunks, finish chunk, [DONE]
    assert len(chunks) == 6
    assert chunks[-1] == "data: [DONE]\n\n"

    # Verify words appear in content chunks
    content_parts = []
    for c in chunks[1:-2]:
        data = json.loads(c.strip().replace("data: ", ""))
        content = data["choices"][0]["delta"].get("content")
        if content:
            content_parts.append(content.strip())

    assert "Hello" in content_parts
    assert "World" in content_parts
    assert "Foo" in content_parts


def test_fake_stream_response_sync():
    """Run the async test synchronously."""
    asyncio.run(test_fake_stream_response_yields_word_chunks())
