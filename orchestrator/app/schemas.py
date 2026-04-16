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
    api_key: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    display_name: str | None = None
    status: UserStatus | None = None
    config: dict | None = None


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


# --- Railway schemas ---

class RailwayServiceResponse(BaseModel):
    id: str
    name: str
    project_id: str
    updated_at: str | None = None
    status: str | None = None

    model_config = {"from_attributes": True}


class RailwayVolumeResponse(BaseModel):
    id: str
    name: str
    project_id: str
    size: int | None = None
    mount_path: str | None = None

    model_config = {"from_attributes": True}


class RailwayDeploymentResponse(BaseModel):
    id: str
    status: str
    created_at: str | None = None
    updated_at: str | None = None
    domain: dict[str, Any] | None = None
    builder: dict[str, Any] | None = None

    model_config = {"from_attributes": True}


class RailwayServiceCreate(BaseModel):
    name: str
    docker_image: str
    memory: str = "1GB"
    cpu: int = 1
    volume_id: str | None = None
    env_vars: dict[str, str] | None = None


class RailwayVolumeCreate(BaseModel):
    name: str
    size_gb: int = 5
    mount_path: str = "/data"


class RailwayDeploymentCreate(BaseModel):
    service_id: str
    docker_image: str
    env_vars: dict[str, str] | None = None
