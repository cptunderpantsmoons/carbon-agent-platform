"""Pydantic request/response schemas."""
from datetime import datetime
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
