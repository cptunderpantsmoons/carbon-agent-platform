"""Dynamic proxy router that maps API keys to agent instances."""
import httpx
import structlog
from fastapi import Request, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import User, Session, SessionStatus, UserStatus
from app.session_manager import SessionManager

logger = structlog.get_logger()


class AgentRouter:
    """Routes OpenAI-compatible requests to the correct agent instance."""

    def __init__(self, session_manager: SessionManager):
        self.session_manager = session_manager

    async def resolve_user(self, api_key: str, db: AsyncSession) -> User:
        """Look up user by API key."""
        result = await db.execute(select(User).where(User.api_key == api_key))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=401, detail="Invalid API key")
        if user.status != UserStatus.ACTIVE:
            raise HTTPException(status_code=403, detail="User account is not active")
        return user

    async def get_or_create_session(
        self, user: User, db: AsyncSession
    ) -> Session:
        """Get the active session for a user, or spin one up."""
        result = await db.execute(
            select(Session)
            .where(Session.user_id == user.id)
            .where(Session.status.in_([SessionStatus.ACTIVE, SessionStatus.SPINNING_UP]))
        )
        session = result.scalar_one_or_none()

        if session and session.status == SessionStatus.ACTIVE:
            return session

        # Need to spin up
        if session and session.status == SessionStatus.SPINNING_UP:
            raise HTTPException(status_code=503, detail="Agent is starting up, please retry")

        # Create new session
        session = Session(
            id=f"ses-{user.id}",
            user_id=user.id,
            status=SessionStatus.SPINNING_UP,
        )
        db.add(session)
        await db.commit()

        try:
            spin_result = await self.session_manager.spin_up(user)
            session.railway_deployment_id = spin_result["deployment_id"]
            session.status = SessionStatus.ACTIVE
            session.internal_url = f"http://{spin_result['service_id']}.railway.internal:8000"
            user.railway_service_id = spin_result["service_id"]
            await db.commit()
        except Exception as e:
            session.status = SessionStatus.ERROR
            session.error_message = str(e)
            await db.commit()
            raise HTTPException(status_code=500, detail=f"Failed to start agent: {str(e)}")

        return session

    async def proxy_request(self, session: Session, request: Request) -> StreamingResponse:
        """Proxy the request to the agent instance."""
        if not session.internal_url:
            raise HTTPException(status_code=503, detail="Agent instance has no URL")

        target_url = f"{session.internal_url}/v1/chat/completions"
        body = await request.body()
        headers = dict(request.headers)
        headers.pop("host", None)
        headers.pop("authorization", None)  # Strip user auth, use internal

        async with httpx.AsyncClient(timeout=300.0) as client:
            async with client.stream('POST', target_url, content=body, headers={'Content-Type': 'application/json'}) as response:
                async def stream_generator():
                    async for chunk in response.aiter_bytes():
                        yield chunk
                return StreamingResponse(stream_generator(), status_code=response.status_code, media_type=response.headers.get('content-type', 'application/json'))
