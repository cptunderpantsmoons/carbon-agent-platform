"""Model policy API endpoints for routing and provider control."""

import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.database import get_session
from app.models import ModelPolicy
from app.schemas import ModelPolicySchema, ModelPolicyUpdate
from app.admin import verify_admin_jwt
from app.models import User

import structlog

logger = structlog.get_logger()
model_policy_router = APIRouter(prefix="/admin", tags=["model-policy"])
public_policy_router = APIRouter(prefix="/v1", tags=["model-policy"])


def _build_default_policy(tenant_id: str) -> ModelPolicy:
    """Create the default policy object for a tenant."""
    return ModelPolicy(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        routing_mode="auto",
        default_provider="featherless",
        allowed_providers=["featherless", "deepseek", "openai", "anthropic"],
        benchmark_mode=True,
    )


async def _get_or_create_policy(
    db: AsyncSession, tenant_id: str = "default"
) -> ModelPolicy:
    """Fetch existing policy or create a default one."""
    result = await db.execute(
        select(ModelPolicy)
        .where(ModelPolicy.tenant_id == tenant_id)
        .order_by(ModelPolicy.created_at.asc())
    )
    policy = result.scalars().first()

    if policy is None:
        policy = _build_default_policy(tenant_id)
        db.add(policy)
        try:
            await db.commit()
            await db.refresh(policy)
            logger.info("model_policy_created", tenant_id=tenant_id)
        except IntegrityError:
            await db.rollback()
            result = await db.execute(
                select(ModelPolicy)
                .where(ModelPolicy.tenant_id == tenant_id)
                .order_by(ModelPolicy.created_at.asc())
            )
            policy = result.scalars().first()
            if policy is None:
                raise

    return policy


async def _get_policy_or_default(
    db: AsyncSession, tenant_id: str = "default"
) -> ModelPolicy:
    """Fetch the current policy without mutating the database."""
    result = await db.execute(
        select(ModelPolicy)
        .where(ModelPolicy.tenant_id == tenant_id)
        .order_by(ModelPolicy.created_at.asc())
    )
    policy = result.scalars().first()
    if policy is not None:
        return policy
    return _build_default_policy(tenant_id)


@model_policy_router.get("/model-policy", response_model=ModelPolicySchema)
async def get_model_policy(
    db: AsyncSession = Depends(get_session),
    admin: User = Depends(verify_admin_jwt),
) -> ModelPolicy:
    """Read the current model policy (admin only)."""
    policy = await _get_or_create_policy(db)
    logger.info("model_policy_read", admin_id=admin.id, tenant_id=policy.tenant_id)
    return policy


@model_policy_router.put("/model-policy", response_model=ModelPolicySchema)
async def update_model_policy(
    update: ModelPolicyUpdate,
    db: AsyncSession = Depends(get_session),
    admin: User = Depends(verify_admin_jwt),
) -> ModelPolicy:
    """Update the model policy (admin only)."""
    policy = await _get_or_create_policy(db)

    if update.routing_mode is not None:
        policy.routing_mode = update.routing_mode
    if update.default_provider is not None:
        policy.default_provider = update.default_provider
    if update.allowed_providers is not None:
        policy.allowed_providers = update.allowed_providers
    if update.benchmark_mode is not None:
        policy.benchmark_mode = update.benchmark_mode

    await db.commit()
    await db.refresh(policy)
    logger.info("model_policy_updated", admin_id=admin.id, tenant_id=policy.tenant_id)
    return policy


@public_policy_router.get("/model-policy/me", response_model=ModelPolicySchema)
async def get_my_model_policy(
    db: AsyncSession = Depends(get_session),
) -> ModelPolicy:
    """Read the model policy for runtime clients without creating rows."""
    policy = await _get_policy_or_default(db)
    return policy
