"""Tests for ORM models."""
import pytest
from datetime import datetime, timezone
from sqlalchemy import select
from app.models import User, Session, AuditLog, UserStatus, SessionStatus


@pytest.mark.asyncio
async def test_create_user(db_session, sample_user_data):
    user = User(**sample_user_data)
    db_session.add(user)
    await db_session.commit()

    result = await db_session.get(User, user.id)
    assert result is not None
    assert result.email == "test@example.com"
    assert result.display_name == "Test User"
    assert result.status == UserStatus.ACTIVE
    assert result.api_key == "sk-test-api-key-12345"


@pytest.mark.asyncio
async def test_user_default_status(db_session):
    user = User(
        id="user-002",
        email="pending@example.com",
        display_name="Pending User",
        api_key="sk-pending-key",
    )
    db_session.add(user)
    await db_session.commit()

    result = await db_session.get(User, user.id)
    assert result.status == UserStatus.PENDING


@pytest.mark.asyncio
async def test_user_timestamps(db_session, sample_user_data):
    user = User(**sample_user_data)
    db_session.add(user)
    await db_session.commit()

    result = await db_session.get(User, user.id)
    assert result.created_at is not None
    assert result.updated_at is not None


@pytest.mark.asyncio
async def test_create_session(db_session, sample_user_data, sample_session_data):
    user = User(**sample_user_data)
    db_session.add(user)
    await db_session.flush()

    session = Session(**sample_session_data)
    db_session.add(session)
    await db_session.commit()

    result = await db_session.get(Session, session.id)
    assert result is not None
    assert result.user_id == "user-001"
    assert result.status == SessionStatus.ACTIVE
    assert result.internal_url == "http://agent-001.internal:8000"
    assert result.public_url == "https://agents.carbon.dev/agent/user-001"


@pytest.mark.asyncio
async def test_session_default_status(db_session, sample_user_data):
    user = User(**sample_user_data)
    db_session.add(user)
    await db_session.flush()

    session = Session(
        id="session-002",
        user_id="user-001",
    )
    db_session.add(session)
    await db_session.commit()

    result = await db_session.get(Session, session.id)
    assert result.status == SessionStatus.STOPPED


@pytest.mark.asyncio
async def test_user_session_relationship(db_session, sample_user_data, sample_session_data):
    user = User(**sample_user_data)
    db_session.add(user)
    await db_session.flush()

    session = Session(**sample_session_data)
    db_session.add(session)
    await db_session.commit()

    sessions_result = await db_session.execute(
        select(Session).where(Session.user_id == "user-001")
    )
    sessions = sessions_result.scalars().all()
    assert len(sessions) == 1
    assert sessions[0].id == "session-001"


@pytest.mark.asyncio
async def test_session_user_back_populates(db_session, sample_user_data, sample_session_data):
    user = User(**sample_user_data)
    db_session.add(user)
    await db_session.flush()

    session = Session(**sample_session_data)
    db_session.add(session)
    await db_session.commit()

    result = await db_session.get(Session, "session-001")
    assert result.user is not None
    assert result.user.email == "test@example.com"


@pytest.mark.asyncio
async def test_create_audit_log(db_session):
    log = AuditLog(
        id="log-001",
        action="user.created",
        details={"email": "test@example.com"},
        performed_by="admin_agent",
    )
    db_session.add(log)
    await db_session.commit()

    result = await db_session.get(AuditLog, log.id)
    assert result is not None
    assert result.action == "user.created"
    assert result.details == {"email": "test@example.com"}
    assert result.performed_by == "admin_agent"
    assert result.created_at is not None


@pytest.mark.asyncio
async def test_audit_log_with_user_id(db_session, sample_user_data):
    user = User(**sample_user_data)
    db_session.add(user)
    await db_session.flush()

    log = AuditLog(
        id="log-002",
        user_id="user-001",
        action="session.started",
        details={"session_id": "session-001"},
        performed_by="system",
    )
    db_session.add(log)
    await db_session.commit()

    result = await db_session.get(AuditLog, log.id)
    assert result.user_id == "user-001"


@pytest.mark.asyncio
async def test_user_config_json(db_session, sample_user_data):
    user = User(**sample_user_data)
    user.config = {"theme": "dark", "model": "gpt-4", "max_tokens": 4096}
    db_session.add(user)
    await db_session.commit()

    result = await db_session.get(User, user.id)
    assert result.config["theme"] == "dark"
    assert result.config["max_tokens"] == 4096


@pytest.mark.asyncio
async def test_session_error_state(db_session, sample_user_data):
    user = User(**sample_user_data)
    db_session.add(user)
    await db_session.flush()

    session = Session(
        id="session-err",
        user_id="user-001",
        status=SessionStatus.ERROR,
        error_message="Failed to deploy: image pull timeout",
    )
    db_session.add(session)
    await db_session.commit()

    result = await db_session.get(Session, "session-err")
    assert result.status == SessionStatus.ERROR
    assert "timeout" in result.error_message


@pytest.mark.asyncio
async def test_multiple_sessions_per_user(db_session, sample_user_data):
    user = User(**sample_user_data)
    db_session.add(user)
    await db_session.flush()

    for i in range(3):
        session = Session(
            id=f"session-multi-{i}",
            user_id="user-001",
            status=SessionStatus.STOPPED,
        )
        db_session.add(session)
    await db_session.commit()

    sessions_result = await db_session.execute(
        select(Session).where(Session.user_id == "user-001")
    )
    sessions = sessions_result.scalars().all()
    assert len(sessions) == 3


@pytest.mark.asyncio
async def test_user_nullable_fields(db_session):
    user = User(
        id="user-minimal",
        email="minimal@example.com",
        display_name="Minimal",
        api_key="sk-min",
    )
    db_session.add(user)
    await db_session.commit()

    result = await db_session.get(User, "user-minimal")
    assert result.config is None


@pytest.mark.asyncio
async def test_session_nullable_fields(db_session, sample_user_data):
    user = User(**sample_user_data)
    db_session.add(user)
    await db_session.flush()

    session = Session(id="session-min", user_id="user-001")
    db_session.add(session)
    await db_session.commit()

    result = await db_session.get(Session, "session-min")
    assert result.container_id is None
    assert result.internal_url is None
    assert result.public_url is None
    assert result.started_at is None
    assert result.stopped_at is None
    assert result.error_message is None
