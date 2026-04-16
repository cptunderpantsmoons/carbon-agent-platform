"""Adapter configuration."""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Agent Zero internal API
    agent_api_url: str = "http://localhost:5000"
    agent_api_key: str = ""

    # Per-user Railway service routing
    railway_service_url_template: str = ""  # e.g. "https://{service_id}.up.railway.app"

    # Agent Zero context defaults
    default_lifetime_hours: int = 24
    default_project_name: str = ""
    user_id: str = ""  # Default user ID for standalone mode

    # Database (shared with orchestrator, SQLite for testing)
    database_url: str = "sqlite+aiosqlite:///./test.db"

    # Server
    port: int = 8000
    host: str = "0.0.0.0"

    # LLM info for OpenAI-compatible metadata
    model_name: str = "carbon-agent"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "protected_namespaces": ("settings_",)}

@lru_cache
def get_settings() -> Settings:
    return Settings()
