"""pydantic-ai agent factories for the Carbon runtime.

- chat_agent: General Hub chat with conversation memory
- benchmark_agent: Single-run evaluation execution
- task_agent: MCP/tool-enabled agentic workflows
"""

import time
import uuid
from datetime import datetime, timezone

import structlog
from pydantic_ai import Agent, ModelSettings
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    UserPromptPart,
)

from .dependencies import RuntimeDeps
from .responses import AgentExecutionRequest, AgentExecutionResult, ChatMessage
from .providers import (
    get_provider_model,
    resolve_provider_and_model,
)
from .tools import get_registered_tools
from .state import get_conversation_state, ConversationMessage
from .normalize import normalize_response
from .policy_client import get_policy_client
from ..temperature_detector import (
    detect_and_apply_temperature,
    detect_task_type,
    get_task_description,
)

logger = structlog.get_logger()


def _convert_messages(history: list[ChatMessage]) -> list[ModelMessage]:
    """Convert our ChatMessage list to pydantic-ai ModelMessage list."""
    result: list[ModelMessage] = []
    for msg in history:
        if msg.role == "user":
            result.append(ModelRequest(parts=[UserPromptPart(content=msg.content)]))
        elif msg.role == "assistant":
            result.append(ModelResponse(parts=[TextPart(content=msg.content)]))
        # system and tool messages are handled via system prompt / tool returns
    return result


def _build_system_prompt(deps: RuntimeDeps, task_type: str, task_desc: str) -> str:
    """Build a system prompt from runtime dependencies."""
    lines = [
        "You are the Corporate Carbon Intelligence Hub agent.",
        f"Task type: {task_desc}",
        f"User: {deps.user.user_id}",
        f"Tenant: {deps.tenant.tenant_id}",
    ]
    if deps.policy.routing_mode != "auto":
        lines.append(f"Routing mode: {deps.policy.routing_mode}")
    return "\n".join(lines)


def _build_model_settings(
    request: AgentExecutionRequest, temperature: float
) -> ModelSettings:
    """Translate OpenAI-style request options into pydantic-ai model settings."""
    settings = ModelSettings()
    settings["temperature"] = temperature
    if request.max_tokens is not None:
        settings["max_tokens"] = request.max_tokens
    if request.stop:
        settings["stop_sequences"] = request.stop
    return settings


async def create_chat_agent(
    request: AgentExecutionRequest,
    deps: RuntimeDeps,
) -> Agent[RuntimeDeps, str]:
    """Create a chat agent configured for general Hub conversation.

    Args:
        request: Execution request
        deps: Runtime dependencies

    Returns:
        Configured pydantic-ai Agent
    """
    # Resolve provider from policy
    provider, model_name = resolve_provider_and_model(
        request.provider,
        request.model,
        deps.policy.default_provider,
        deps.policy.allowed_providers or ["openai"],
        deps.policy.routing_mode,
    )
    model = get_provider_model(provider=provider, model=model_name)

    # Discover and register tools
    tools = await get_registered_tools(
        tool_policy=request.tool_policy,
        require_approval=False,
    )

    agent = Agent(
        model,
        deps_type=RuntimeDeps,
        result_type=str,
        system_prompt=_build_system_prompt(
            deps, request.task_type, "General conversation"
        ),
        tools=tools,
    )

    logger.info(
        "chat_agent_created",
        provider=provider,
        model=model_name,
        user_id=deps.user.user_id,
    )
    return agent


async def create_benchmark_agent(
    request: AgentExecutionRequest,
    deps: RuntimeDeps,
) -> Agent[RuntimeDeps, str]:
    """Create a benchmark agent for comparable single-run evaluation.

    Benchmark runs are isolated: no conversation history, fixed temperature,
    and explicit system prompt.
    """
    provider, model_name = resolve_provider_and_model(
        request.provider,
        request.model,
        deps.policy.default_provider,
        deps.policy.allowed_providers or ["openai"],
        deps.policy.routing_mode,
    )
    model = get_provider_model(provider=provider, model=model_name)

    agent = Agent(
        model,
        deps_type=RuntimeDeps,
        result_type=str,
        system_prompt="You are a benchmark evaluation agent. Respond concisely and accurately.",
    )

    logger.info(
        "benchmark_agent_created",
        provider=provider,
        model=model_name,
        user_id=deps.user.user_id,
    )
    return agent


async def create_task_agent(
    request: AgentExecutionRequest,
    deps: RuntimeDeps,
) -> Agent[RuntimeDeps, str]:
    """Create a task agent for agentic workflows with MCP/tool use."""
    provider, model_name = resolve_provider_and_model(
        request.provider,
        request.model,
        deps.policy.default_provider,
        deps.policy.allowed_providers or ["openai"],
        deps.policy.routing_mode,
    )
    model = get_provider_model(provider=provider, model=model_name)

    # Task agents always get tools, with approval gates
    tools = await get_registered_tools(
        tool_policy=request.tool_policy,
        require_approval=True,
    )

    agent = Agent(
        model,
        deps_type=RuntimeDeps,
        result_type=str,
        system_prompt=_build_system_prompt(
            deps, request.task_type, "Agentic task execution"
        ),
        tools=tools,
    )

    logger.info(
        "task_agent_created",
        provider=provider,
        model=model_name,
        tools_count=len(tools),
        user_id=deps.user.user_id,
    )
    return agent


async def execute_agent_run(
    request: AgentExecutionRequest,
    deps: RuntimeDeps,
) -> AgentExecutionResult:
    """Execute an agent run based on request parameters.

    This is the main entry point for the runtime. It:
    1. Selects the appropriate agent factory
    2. Loads conversation history if needed
    3. Detects temperature/task type
    4. Runs the agent
    5. Persists state
    6. Returns normalized result
    """
    trace_id = deps.observability.trace_id or str(uuid.uuid4())
    start_time = time.monotonic()

    # Fetch model policy from orchestrator (overrides request defaults)
    try:
        policy_client = get_policy_client()
        fetched_policy = await policy_client.fetch_policy(deps.tenant.tenant_id)
        deps.policy.routing_mode = fetched_policy.routing_mode
        deps.policy.default_provider = fetched_policy.default_provider
        deps.policy.allowed_providers = fetched_policy.allowed_providers
        deps.policy.benchmark_mode = fetched_policy.benchmark_mode
        logger.info(
            "policy_fetched_and_applied",
            trace_id=trace_id,
            tenant_id=deps.tenant.tenant_id,
            routing_mode=fetched_policy.routing_mode,
        )
    except Exception as e:
        logger.warning(
            "policy_fetch_failed_using_defaults", trace_id=trace_id, error=str(e)
        )

    # Normalize legacy placeholder model names before agent construction.
    _, resolved_model = resolve_provider_and_model(
        request.provider,
        request.model,
        deps.policy.default_provider,
        deps.policy.allowed_providers or ["openai"],
        deps.policy.routing_mode,
    )
    request.model = resolved_model

    # Temperature detection
    temperature = detect_and_apply_temperature(
        messages=[m.model_dump() for m in request.messages],
        current_temperature=request.temperature,
        provider=deps.policy.default_provider,
    )

    # Task detection
    last_user_message = ""
    for msg in reversed(request.messages):
        if msg.role == "user":
            last_user_message = msg.content
            break
    task_type = detect_task_type(last_user_message)
    task_desc = get_task_description(task_type)

    logger.info(
        "agent_run_start",
        trace_id=trace_id,
        user_id=deps.user.user_id,
        task_type=task_desc,
        temperature=temperature,
        provider=request.provider,
    )

    model_settings = _build_model_settings(request, temperature)

    # Select agent factory
    if request.task_type == "benchmark":
        agent = await create_benchmark_agent(request, deps)
    elif request.task_type == "task":
        agent = await create_task_agent(request, deps)
    else:
        agent = await create_chat_agent(request, deps)

    # Load conversation history for chat/task agents
    message_history: list[ModelMessage] = []
    if request.conversation_id and request.task_type in ("chat", "task"):
        convo_store = get_conversation_state()
        state = await convo_store.get(deps.user.user_id, request.conversation_id)
        if state:
            history = [
                ChatMessage(role=m.role, content=m.content) for m in state.messages
            ]
            message_history = _convert_messages(history)
        else:
            # Auto-create conversation if ID provided but not found
            await convo_store.create(
                user_id=deps.user.user_id,
                tenant_id=deps.tenant.tenant_id,
                metadata={"provider": request.provider, "model": request.model},
            )

    # Build the user prompt from the last user message
    user_prompt = last_user_message
    if not user_prompt and request.messages:
        user_prompt = request.messages[-1].content

    # Run the agent
    try:
        result = await agent.run(
            user_prompt,
            deps=deps,
            message_history=message_history,
            model_settings=model_settings,
        )
    except Exception as e:
        logger.error(
            "agent_run_failed",
            trace_id=trace_id,
            user_id=deps.user.user_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        latency_ms = int((time.monotonic() - start_time) * 1000)
        return AgentExecutionResult(
            output_text=f"Agent execution failed: {e}",
            latency_ms=latency_ms,
            provider=request.provider or deps.policy.default_provider,
            model=request.model or "unknown",
            conversation_id=request.conversation_id,
            trace_id=trace_id,
            finish_reason="error",
        )

    latency_ms = int((time.monotonic() - start_time) * 1000)

    # Persist conversation state
    if request.conversation_id:
        convo_store = get_conversation_state()
        now = datetime.now(timezone.utc)
        new_messages = [
            ConversationMessage(
                role="user",
                content=user_prompt,
                timestamp=now,
            ),
            ConversationMessage(
                role="assistant",
                content=result.data
                if isinstance(result.data, str)
                else str(result.data),
                timestamp=now,
            ),
        ]
        await convo_store.append_messages(
            deps.user.user_id,
            request.conversation_id,
            new_messages,
        )

    # Normalize response
    normalized = normalize_response(
        result=result,
        provider=request.provider or deps.policy.default_provider,
        model=request.model or "unknown",
        conversation_id=request.conversation_id,
        trace_id=trace_id,
        latency_ms=latency_ms,
    )

    logger.info(
        "agent_run_complete",
        trace_id=trace_id,
        user_id=deps.user.user_id,
        latency_ms=latency_ms,
        token_usage=normalized.token_usage.total_tokens,
        tool_calls=len(normalized.tool_calls),
    )

    return normalized
