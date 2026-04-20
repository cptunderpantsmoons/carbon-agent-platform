"""Adapter configuration."""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # ── Runtime LLM Provider Configuration ───────────────────────────────────
    # Primary provider for pydantic-ai runtime
    llm_provider: str = "openai"
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model_name: str = "gpt-4o"
    admin_agent_api_key: str = ""

    # Orchestrator URL for model policy fetching
    orchestrator_url: str = "http://orchestrator:8000"

    # ── Agent Zero Legacy (deprecated, remove after cutover) ─────────────────
    # These fields are kept for one-wave transition compatibility.
    # Do not use in new code. They will be removed in Wave 5.
    agent_api_url: str = "http://localhost:5000"
    agent_api_key: str = ""
    agent_domain: str = "agents.carbon.dev"
    default_lifetime_hours: int = 24
    default_project_name: str = ""
    user_id: str = ""  # Default user ID for standalone mode

    # ── Database ─────────────────────────────────────────────────────────────
    database_url: str = "sqlite+aiosqlite:///./adapter.db"

    # ── Redis ────────────────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/1"

    # ── Server ───────────────────────────────────────────────────────────────
    port: int = 8000
    host: str = "0.0.0.0"

    # ── MCP (Model Context Protocol) ─────────────────────────────────────────
    mcp_enabled: bool = False
    mcp_gateway_url: str = "http://obot-gateway:8080"
    mcp_timeout_seconds: float = 30.0
    mcp_max_retries: int = 3

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "protected_namespaces": ("settings_",),
    }


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    import sys

    print(f"DEBUG config: database_url={settings.database_url}", file=sys.stderr)
    sys.stderr.flush()
    return settings
