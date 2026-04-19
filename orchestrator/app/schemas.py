"""Pydantic request/response schemas."""
from datetime import datetime
from typing import Any
from pydantic import BaseModel, EmailStr, Field
from app.models import UserStatus


# --- User schemas ---

class UserCreate(BaseModel):
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=255)
    config: dict | None = None


class UserResponse(BaseModel):
    id: str
    email: str
    display_name: str
    status: UserStatus
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UserWithApiKeyResponse(BaseModel):
    """Response schema that includes the API key.

    Only used for admin user creation and API key rotation,
    where the caller needs to see the key.
    """
    id: str
    email: str
    display_name: str
    status: UserStatus
    api_key: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    display_name: str | None = None
    status: UserStatus | None = None
    config: dict | None = None


class ApiKeyRotateResponse(BaseModel):
    """Response schema for API key rotation.

    Only returned by POST /user/me/api-key/rotate endpoint.
    """
    status: str
    new_api_key: str
    message: str


# --- Admin schemas ---

class AdminCommand(BaseModel):
    command: str = Field(description="Natural language command for admin agent")
    context: dict | None = None


class AdminResponse(BaseModel):
    status: str
    message: str
    data: dict | None = None


# --- Health schemas ---

class PlatformHealth(BaseModel):
    total_users: int
    total_volumes: int


# --- Docker schemas ---

class DockerContainerResponse(BaseModel):
    id: str
    name: str
    status: str
    created_at: str | None = None
    updated_at: str | None = None

    model_config = {"from_attributes": True}


class DockerContainerCreate(BaseModel):
    user_id: str
    docker_image: str
    memory_limit: str = "512m"
    cpu_nanos: int = 500000000
    env_vars: dict[str, str] | None = None
