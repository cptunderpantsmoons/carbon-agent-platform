"""Typed dependency containers for pydantic-ai runtime.

These are injected into agent runs via RunContext so every tool,
callback, and model call has access to user, tenant, policy,
tool registry, and observability context.
"""

from dataclasses import dataclass
from typing import Optional
import structlog

from app.config import get_settings

logger = structlog.get_logger()


@dataclass
class UserContext:
    user_id: str
    email: Optional[str] = None
    display_name: Optional[str] = None
    api_key: Optional[str] = None


@dataclass
class TenantContext:
    tenant_id: str = "default"


@dataclass
class ModelPolicyContext:
    routing_mode: str = "auto"
    default_provider: str = "openai"
    allowed_providers: list[str] | None = None
    benchmark_mode: bool = False

    def __post_init__(self):
        if self.allowed_providers is None:
            self.allowed_providers = ["openai", "featherless", "deepseek", "anthropic"]


@dataclass
class ToolRegistryContext:
    available_tools: list[dict] | None = None
    approval_gates: list[str] | None = None
    mcp_enabled: bool = False

    def __post_init__(self):
        if self.available_tools is None:
            self.available_tools = []
        if self.approval_gates is None:
            self.approval_gates = [
                "legal_draft",
                "financial_output",
                "regulatory_submission",
                "cer_registry",
            ]


@dataclass
class ObservabilityContext:
    trace_id: str = ""
    request_id: str = ""
    logger: Optional[object] = None

    def __post_init__(self):
        if self.logger is None:
            self.logger = logger.bind(
                trace_id=self.trace_id,
                request_id=self.request_id,
            )


@dataclass
class RuntimeDeps:
    """Complete dependency bundle passed to every agent run."""

    user: UserContext
    tenant: TenantContext
    policy: ModelPolicyContext
    tools: ToolRegistryContext
    observability: ObservabilityContext
    conversation_id: Optional[str] = None

    @classmethod
    def from_request(
        cls, request, trace_id: str = "", request_id: str = ""
    ) -> "RuntimeDeps":
        """Build RuntimeDeps from an AgentExecutionRequest."""
        settings = get_settings()
        return cls(
            user=UserContext(
                user_id=request.user_id,
                api_key=getattr(settings, "llm_api_key", None),
            ),
            tenant=TenantContext(tenant_id=request.tenant_id),
            policy=ModelPolicyContext(
                routing_mode=request.routing_mode,
                default_provider=getattr(settings, "llm_provider", "openai"),
            ),
            tools=ToolRegistryContext(
                mcp_enabled=getattr(settings, "mcp_enabled", False),
            ),
            observability=ObservabilityContext(
                trace_id=trace_id,
                request_id=request_id,
            ),
            conversation_id=request.conversation_id,
        )
