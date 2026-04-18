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

    # Rate limiting — limits-library URI format.
    # memory://   in-process; resets on restart, not shared across replicas (dev/test default)
    # redis://... persists across restarts AND is shared across all replicas (production)
    # Production: set RATE_LIMIT_STORAGE_URI=redis://redis:6379/0
    rate_limit_storage_uri: str = "memory://"

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

    # Clerk Authentication
    clerk_secret_key: str = ""
    clerk_publishable_key: str = ""
    clerk_frontend_api_url: str = ""  # e.g. https://xxx.clerk.accounts.dev
    clerk_webhook_secret: str = ""
    clerk_jwt_public_key: str = ""  # Optional; fetched from JWKS endpoint if absent
    clerk_jwt_issuer: str = ""      # e.g. https://xxx.clerk.accounts.dev -- enables iss verification
    clerk_authorized_origins: str = ""  # Comma-separated list of authorized origins

    # CORS
    cors_allowed_origins: str = ""  # Comma-separated. REQUIRED in production.

    # Scheduler
    health_check_interval_minutes: int = 5
    analytics_interval_minutes: int = 60
    audit_cleanup_interval_hours: int = 24
    audit_retention_days: int = 90
    db_health_check_interval_minutes: int = 10

    # Deployment
    # Set to False in production to rely on Alembic migrations instead of auto-create.
    auto_create_tables: bool = True

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
