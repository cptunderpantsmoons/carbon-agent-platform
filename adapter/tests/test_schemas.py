"""Tests for OpenAI-compatible schemas."""

from app.schemas import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionChoice,
    ChatMessage,
    UsageInfo,
)


def test_parse_request():
    data = {
        "model": "gpt-4",
        "messages": [
            {"role": "system", "content": "You are helpful.", "name": "system"},
            {"role": "user", "content": "Hello!", "tool_call_id": "call-1"},
        ],
        "stream": False,
        "max_tokens": 128,
        "stop": ["END"],
    }
    req = ChatCompletionRequest(**data)
    assert len(req.messages) == 2
    assert req.messages[1].role == "user"
    assert req.messages[1].content == "Hello!"
    assert req.stream is False
    assert req.max_tokens == 128
    assert req.stop == ["END"]


def test_build_response():
    response = ChatCompletionResponse(
        choices=[
            ChatCompletionChoice(
                message=ChatMessage(role="assistant", content="Hi there!")
            )
        ]
    )
    assert response.object == "chat.completion"
    assert response.choices[0].message.content == "Hi there!"
    assert response.id.startswith("chatcmpl-")


def test_usage_defaults():
    usage = UsageInfo()
    assert usage.prompt_tokens == 0
    assert usage.total_tokens == 0
