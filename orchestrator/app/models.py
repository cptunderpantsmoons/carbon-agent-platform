"""ORM models for users and audit logs."""
from datetime import datetime, timezone
from enum import Enum as PyEnum
from sqlalchemy import String, DateTime, Enum, Text, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class UserStatus(str, PyEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    PENDING = "pending"


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(255))
    api_key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    status: Mapped[UserStatus] = mapped_column(Enum(UserStatus), default=UserStatus.PENDING)
    railway_service_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    volume_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(100))
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    performed_by: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
