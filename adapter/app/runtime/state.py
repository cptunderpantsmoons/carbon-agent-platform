"""Explicit conversation/session state owned by the adapter.

Replaces Agent Zero's implicit context_id storage with a keyed,
queryable conversation model persisted in Redis (with Postgres
fallback for long-term archival).
"""
import json
import uuid
from datetime import datetime, timezone
from typing import Optional

import structlog
from pydantic import BaseModel

from app.config import get_settings
from app.context_store import get_context_store

logger = structlog.get_logger()


class ConversationMessage(BaseModel):
    role: str
    content: str
    timestamp: datetime
    tool_calls: Optional[list[dict]] = None


class ConversationState(BaseModel):
    conversation_id: str
    user_id: str
    tenant_id: str = "default"
    messages: list[ConversationMessage]
    created_at: datetime
    updated_at: datetime
    metadata: dict = {}


class ConversationStateStore:
    """Redis-backed conversation state with TTL.

    Key pattern: conversation:{user_id}:{conversation_id}
    """

    def __init__(self, redis_url: Optional[str] = None):
        settings = get_settings()
        self._redis_url = redis_url or settings.redis_url
        self._ttl_seconds = 86400 * 7  # 7 days

    def _key(self, user_id: str, conversation_id: str) -> str:
        return f"conversation:{user_id}:{conversation_id}"

    async def create(
        self,
        user_id: str,
        tenant_id: str = "default",
        metadata: Optional[dict] = None,
    ) -> ConversationState:
        conversation_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        state = ConversationState(
            conversation_id=conversation_id,
            user_id=user_id,
            tenant_id=tenant_id,
            messages=[],
            created_at=now,
            updated_at=now,
            metadata=metadata or {},
        )
        await self._save(state)
        logger.info("conversation_created", conversation_id=conversation_id, user_id=user_id)
        return state

    async def get(self, user_id: str, conversation_id: str) -> Optional[ConversationState]:
        store = get_context_store()
        key = self._key(user_id, conversation_id)
        raw = await store.get(key)
        if raw:
            try:
                data = json.loads(raw)
                return ConversationState(**data)
            except Exception as e:
                logger.warning("conversation_deserialize_error", error=str(e), key=key)
        return None

    async def append_messages(
        self,
        user_id: str,
        conversation_id: str,
        messages: list[ConversationMessage],
    ) -> Optional[ConversationState]:
        state = await self.get(user_id, conversation_id)
        if state is None:
            return None
        state.messages.extend(messages)
        state.updated_at = datetime.now(timezone.utc)
        await self._save(state)
        return state

    async def _save(self, state: ConversationState) -> None:
        store = get_context_store()
        key = self._key(state.user_id, state.conversation_id)
        # Convert datetime to ISO strings for JSON
        data = state.model_dump(mode="json")
        await store.set(key, json.dumps(data), ttl=self._ttl_seconds)


# Singleton
_conversation_store: Optional[ConversationStateStore] = None


def get_conversation_state() -> ConversationStateStore:
    global _conversation_store
    if _conversation_store is None:
        _conversation_store = ConversationStateStore()
    return _conversation_store
