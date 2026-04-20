"""Carbon Agent Runtime — pydantic-ai based agent execution layer.

Replaces the legacy Agent Zero client with typed dependencies,
structured outputs, explicit tool registration, and normalized
responses across all LLM providers.
"""

from .dependencies import (
    UserContext,
    TenantContext,
    ModelPolicyContext,
    ToolRegistryContext,
    ObservabilityContext,
    RuntimeDeps,
)
from .responses import (
    AgentExecutionRequest,
    AgentExecutionResult,
    ChatMessage,
    ToolCallResult,
    Citation,
    TokenUsage,
)
from .agents import (
    create_chat_agent,
    create_benchmark_agent,
    create_task_agent,
    execute_agent_run,
)
from .state import ConversationState, get_conversation_state
from .normalize import normalize_response

__all__ = [
    "UserContext",
    "TenantContext",
    "ModelPolicyContext",
    "ToolRegistryContext",
    "ObservabilityContext",
    "RuntimeDeps",
    "AgentExecutionRequest",
    "AgentExecutionResult",
    "ChatMessage",
    "ToolCallResult",
    "Citation",
    "TokenUsage",
    "create_chat_agent",
    "create_benchmark_agent",
    "create_task_agent",
    "execute_agent_run",
    "ConversationState",
    "get_conversation_state",
    "normalize_response",
]
