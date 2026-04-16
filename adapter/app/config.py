"""Adapter configuration."""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Carbon Agent internal API
    agent_api_url: str = "http://localhost:8000"
    agent_api_key: str = ""

    # User context
    user_id: str = ""
    user_email: str = ""
    user_config: str = "{}"

    # Server
    port: int = 8000
    host: str = "0.0.0.0"

    # LLM info for OpenAI-compatible metadata
    model_name: str = "carbon-agent"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
