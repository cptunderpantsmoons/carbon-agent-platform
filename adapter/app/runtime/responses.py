"""Normalized request and response models for the agent runtime.

All provider-specific shapes are converted to/from these stable internal
models so the dashboard and other consumers see one payload shape.
"""
from typing import Literal, Optional
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str
    name: Optional[str] = None
    tool_call_id: Optional[str] = None


class ToolCallResult(BaseModel):
    tool_name: str
    tool_call_id: str
    arguments: dict
    output: str
    approved: bool = True
    latency_ms: int = 0


class Citation(BaseModel):
    source: str
    quote: Optional[str] = None
    url: Optional[str] = None


class TokenUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class AgentExecutionRequest(BaseModel):
    user_id: str
    tenant_id: str = "default"
    conversation_id: Optional[str] = None
    routing_mode: Literal["auto", "force_premium", "block_premium"] = "auto"
    provider: Optional[str] = None
    model: Optional[str] = None
    task_type: Literal["chat", "benchmark", "task"] = "chat"
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    stop: list[str] | None = None
    tool_policy: Literal["auto", "disabled", "require_approval"] = "auto"
    messages: list[ChatMessage] = Field(default_factory=list)
    input_items: list[dict] = Field(default_factory=list)
    stream: bool = False


class AgentExecutionResult(BaseModel):
    output_text: str
    structured_output: Optional[dict] = None
    tool_calls: list[ToolCallResult] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    latency_ms: int = 0
    token_usage: TokenUsage = Field(default_factory=TokenUsage)
    provider: str = "unknown"
    model: str = "unknown"
    conversation_id: Optional[str] = None
    trace_id: str = ""
    finish_reason: Optional[str] = None
