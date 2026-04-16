"""Pydantic request/response schemas."""
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field
from app.models import UserStatus, SessionStatus


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


# --- Session schemas ---

class SessionResponse(BaseModel):
    id: str
    user_id: str
    status: SessionStatus
    internal_url: str | None
    public_url: str | None
    last_activity_at: datetime
    started_at: datetime | None
    stopped_at: datetime | None
    error_message: str | None

    model_config = {"from_attributes": True}


class SessionAction(BaseModel):
    action: str = Field(pattern=r"^(start|stop|restart)$")


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
    active_sessions: int
    idle_sessions: int
    stopped_sessions: int
    error_sessions: int
    total_volumes: int
    estimated_cost_monthly: float


class ServiceHealth(BaseModel):
    service: str
    status: str
    uptime_seconds: int | None = None
    last_check: datetime
