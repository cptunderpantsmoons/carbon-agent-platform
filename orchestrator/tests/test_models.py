"""Tests for ORM models."""
import pytest
from app.models import User, AuditLog, UserStatus


@pytest.mark.asyncio
async def test_create_user(db_session, sample_user_data):
    user = User(**sample_user_data)
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    assert user.id == "usr-001"
    assert user.email == "test@example.com"
    assert user.status == UserStatus.ACTIVE
    assert user.created_at is not None


@pytest.mark.asyncio
async def test_create_audit_log(db_session, sample_user_data):
    user = User(**sample_user_data)
    db_session.add(user)
    await db_session.flush()
    log = AuditLog(
        id="log-001",
        user_id=user.id,
        action="user.created",
        details={"email": "test@example.com"},
        performed_by="admin_agent",
    )
    db_session.add(log)
    await db_session.commit()
    assert log.action == "user.created"
    assert log.performed_by == "admin_agent"
