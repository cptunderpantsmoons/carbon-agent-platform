"""Adapter configuration."""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Agent Zero internal API
    agent_api_url: str = "http://localhost:5000"
    agent_api_key: str = ""

    # Per-user container routing via Traefik
    agent_domain: str = "agents.carbon.dev"  # Domain for per-user container routing

    # Agent Zero context defaults
    default_lifetime_hours: int = 24
    default_project_name: str = ""
    user_id: str = ""  # Default user ID for standalone mode

    # Database (shared with orchestrator, SQLite for testing)
    database_url: str = "sqlite+aiosqlite:///./adapter.db"

    # Redis (for context management and caching)
    redis_url: str = "redis://localhost:6379/1"

    # Server
    port: int = 8000
    host: str = "0.0.0.0"

    # LLM info for OpenAI-compatible metadata
    model_name: str = "carbon-agent"

    # MCP (Model Context Protocol) — obot integration
    mcp_enabled: bool = False
    mcp_gateway_url: str = "http://obot-gateway:8080"
    mcp_timeout_seconds: float = 30.0
    mcp_max_retries: int = 3

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "protected_namespaces": ("settings_",)}

@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    import sys
    print(f"DEBUG config: database_url={settings.database_url}", file=sys.stderr)
    sys.stderr.flush()
    return settings
