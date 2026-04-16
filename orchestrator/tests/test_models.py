"""Tests for ORM models."""
import pytest
from datetime import datetime, timezone
from app.models import User, Session, AuditLog, UserStatus, SessionStatus

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
async def test_create_session(db_session, sample_user_data):
    user = User(**sample_user_data)
    db_session.add(user)
    await db_session.flush()
    session = Session(
        id="ses-001",
        user_id=user.id,
        status=SessionStatus.STOPPED,
    )
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)
    assert session.id == "ses-001"
    assert session.user_id == "usr-001"
    assert session.status == SessionStatus.STOPPED
    assert session.user.email == "test@example.com"

@pytest.mark.asyncio
async def test_create_audit_log(db_session, sample_user_data):
    user = User(**sample_user_data)
    db_session.add(user)
    await db_session.flush()
    log = AuditLog(
        id="log-001",
        user_id=user.id,
        action="session.spin_up",
        details={"session_id": "ses-001"},
        performed_by="admin_agent",
    )
    db_session.add(log)
    await db_session.commit()
    assert log.action == "session.spin_up"
    assert log.performed_by == "admin_agent"
