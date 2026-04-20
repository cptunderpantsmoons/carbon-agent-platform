"""Response normalization — convert pydantic-ai results to stable internal shape.

Regardless of whether the underlying provider is OpenAI, Featherless,
DeepSeek, or Anthropic, the dashboard receives one predictable payload.
"""

from typing import Any
import structlog

from pydantic_ai import AgentRunResult

from .responses import AgentExecutionResult, ToolCallResult, TokenUsage

logger = structlog.get_logger()


def normalize_response(
    result: AgentRunResult[Any],
    provider: str,
    model: str,
    conversation_id: str | None,
    trace_id: str,
    latency_ms: int = 0,
) -> AgentExecutionResult:
    """Convert a pydantic-ai AgentRunResult to our normalized AgentExecutionResult.

    Args:
        result: Raw pydantic-ai result
        provider: Resolved provider name
        model: Resolved model name
        conversation_id: Conversation ID if any
        trace_id: Trace ID for observability
        latency_ms: Total request latency

    Returns:
        Normalized AgentExecutionResult
    """
    # Extract text output
    output_text = result.data if isinstance(result.data, str) else str(result.data)

    # Extract token usage if available
    token_usage = TokenUsage()
    if result.usage:
        token_usage = TokenUsage(
            prompt_tokens=result.usage.request_tokens or 0,
            completion_tokens=result.usage.response_tokens or 0,
            total_tokens=result.usage.total_tokens or 0,
        )

    # Extract tool calls from message history if available
    tool_calls: list[ToolCallResult] = []
    if result.all_messages_json:
        for msg in result.all_messages():
            if hasattr(msg, "parts"):
                for part in msg.parts:
                    if part.part_kind == "tool-call":
                        tool_calls.append(
                            ToolCallResult(
                                tool_name=part.tool_name,
                                tool_call_id=part.tool_call_id,
                                arguments=part.args_as_dict()
                                if hasattr(part, "args_as_dict")
                                else {},
                                output="",
                            )
                        )
                    elif part.part_kind == "tool-return":
                        # Match return to last call
                        if tool_calls:
                            tool_calls[-1].output = str(part.content)

    # Structured output detection
    structured_output: dict | None = None
    if isinstance(result.data, dict):
        structured_output = result.data

    return AgentExecutionResult(
        output_text=output_text,
        structured_output=structured_output,
        tool_calls=tool_calls,
        citations=[],  # TODO: extract from result if provider supports it
        latency_ms=latency_ms,
        token_usage=token_usage,
        provider=provider,
        model=model,
        conversation_id=conversation_id,
        trace_id=trace_id,
        finish_reason="stop",
    )
