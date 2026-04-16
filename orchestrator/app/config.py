"""Environment configuration for the orchestrator."""
from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    # Railway
    railway_api_token: str = ""
    railway_project_id: str = ""
    railway_team_id: str = ""
    railway_environment_id: str = ""

    # Database
    database_url: str = "postgresql://postgres:postgres@localhost:5432/carbon_platform"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Admin
    admin_agent_api_key: str = ""
    admin_agent_webhook_url: str = ""

    # Session
    session_idle_timeout_minutes: int = 15
    session_max_lifetime_hours: int = 24
    session_spinup_timeout_seconds: int = 120

    # Volumes
    volume_size_gb: int = 5
    volume_mount_path: str = "/data"

    # Agent
    agent_docker_image: str = "carbon-agent-adapter:latest"
    agent_default_memory: str = "1GB"
    agent_default_cpu: int = 1
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

@lru_cache
def get_settings() -> Settings:
    return Settings()
