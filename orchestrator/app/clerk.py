"""Clerk webhook handler for user lifecycle events."""
import asyncio
import json
import secrets
import uuid

from fastapi import APIRouter, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from svix.webhooks import Webhook, WebhookVerificationError

from app.database import get_session
from app.models import User, AuditLog, UserStatus
from app.config import get_settings
from app.session_manager import get_session_manager
from app.rate_limit import limiter
from slowapi.util import get_remote_address

import structlog

logger = structlog.get_logger(__name__)

clerk_webhook_router = APIRouter(prefix="/webhooks", tags=["clerk-webhooks"])

MAX_BODY_SIZE = 1_048_576  # 1 MiB


def _prepare_webhook_secret(secret: str) -> str:
    """Prepare webhook secret for svix library.
    
    Svix expects the base64-encoded secret. If the secret has the 'whsec_' prefix,
    strip it as svix handles the base64 decoding internally.
    
    Args:
        secret: The webhook secret from environment variable.
        
    Returns:
        The prepared secret for svix Webhook.
    """
    if secret.startswith("whsec_"):
        return secret[6:]  # Strip the prefix
    return secret


def _verify_webhook_signature(
    payload: bytes,
    svix_id: str,
    svix_timestamp: str,
    svix_signature: str,
) -> bool:
    """Verify webhook signature using the Svix standard library.

    Args:
        payload: Raw request body bytes.
        svix_id: svix-id header value.
        svix_timestamp: svix-timestamp header value.
        svix_signature: svix-signature header value.

    Returns:
        True if signature is valid.

    Raises:
        HTTPException: If the secret is not configured or verification fails.
    """
    settings = get_settings()
    webhook_secret = settings.clerk_webhook_secret

    if not webhook_secret:
        logger.error("clerk_webhook_secret_not_configured")
        raise HTTPException(status_code=500, detail="Webhook secret not configured")

    # Prepare secret (strip whsec_ prefix if present)
    prepared_secret = _prepare_webhook_secret(webhook_secret)

    try:
        wh = Webhook(prepared_secret)
        wh.verify(payload, {
            "svix-id": svix_id,
            "svix-timestamp": svix_timestamp,
            "svix-signature": svix_signature,
        })
        return True
    except WebhookVerificationError as e:
        logger.warning("clerk_webhook_invalid_signature", error=str(e))
        return False
    except Exception as e:
        logger.warning("clerk_webhook_signature_verification_failed", error=str(e))
        return False


async def _find_user_by_clerk_id(db: AsyncSession, clerk_user_id: str) -> User | None:
    """Find a user by their Clerk user ID."""
    result = await db.execute(
        select(User).where(User.clerk_user_id == clerk_user_id)
    )
    return result.scalar_one_or_none()


async def _find_user_by_email(db: AsyncSession, email: str) -> User | None:
    """Find a user by email address."""
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


def _generate_api_key() -> str:
    """Generate a new API key in the standard format."""
    return f"sk-{secrets.token_hex(24)}"


async def _create_audit_log(
    db: AsyncSession,
    user_id: str | None,
    action: str,
    details: dict,
    performed_by: str = "clerk_webhook",
) -> AuditLog:
    """Create an audit log entry."""
    log = AuditLog(
        id=str(uuid.uuid4()),
        user_id=user_id,
        action=action,
        details=details,
        performed_by=performed_by,
    )
    db.add(log)
    return log


@clerk_webhook_router.post("/clerk", response_model=None)
@limiter.limit("30/minute", key_func=get_remote_address)
async def handle_clerk_webhook(
    request: Request,
    svix_id: str = Header(default="", alias="svix-id"),
    svix_timestamp: str = Header(default="", alias="svix-timestamp"),
    svix_signature: str = Header(default="", alias="svix-signature"),
):
    """Handle Clerk webhook events for user lifecycle management.

    Supported events:
    - user.created: Auto-provision Carbon Agent user
    - user.updated: Sync email and display name
    - user.deleted: Spin down service and soft-delete user
    """
    # Get the raw body for signature verification
    body = await request.body()

    # Enforce max body size (1 MiB)
    if len(body) > MAX_BODY_SIZE:
        logger.warning("clerk_webhook_payload_too_large", size=len(body))
        raise HTTPException(status_code=413, detail="Payload too large")

    # Require all Svix headers
    if not svix_id or not svix_timestamp or not svix_signature:
        logger.warning("clerk_webhook_missing_svix_headers")
        raise HTTPException(status_code=400, detail="Missing Svix signature headers")

    # Verify webhook signature using Svix
    if not _verify_webhook_signature(body, svix_id, svix_timestamp, svix_signature):
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    # Parse the payload
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        logger.warning("clerk_webhook_invalid_json")
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    event_type = payload.get("type")
    if not event_type:
        logger.warning("clerk_webhook_missing_event_type")
        raise HTTPException(status_code=400, detail="Missing event type")

    data = payload.get("data", {})
    clerk_user_id = data.get("id")

    if not clerk_user_id:
        logger.warning("clerk_webhook_missing_clerk_user_id")
        raise HTTPException(status_code=400, detail="Missing Clerk user ID")

    # Get database session from request state
    db = request.state.db  # type: ignore[attr-defined]

    # Process the event
    if event_type == "user.created":
        return await _handle_user_created(db, data, clerk_user_id)
    elif event_type == "user.updated":
        return await _handle_user_updated(db, data, clerk_user_id)
    elif event_type == "user.deleted":
        return await _handle_user_deleted(db, data, clerk_user_id)
    else:
        logger.info("clerk_webhook_unsupported_event", event_type=event_type)
        return {"status": "ignored", "message": f"Event type {event_type} not handled"}


async def _handle_user_created(
    db: AsyncSession, data: dict, clerk_user_id: str
) -> dict:
    """Handle user.created event - auto-provision Carbon Agent user.

    Idempotent: If user already exists, returns success without creating duplicate.
    """
    # Check if user already exists (idempotency)
    existing_user = await _find_user_by_clerk_id(db, clerk_user_id)
    if existing_user:
        logger.info(
            "clerk_user_already_exists",
            clerk_user_id=clerk_user_id,
            user_id=existing_user.id,
        )
        return {
            "status": "success",
            "message": "User already exists",
            "user_id": existing_user.id,
        }

    # Extract user data from Clerk payload
    email_addresses = data.get("email_addresses", [])
    email = email_addresses[0].get("email_address", "") if email_addresses else ""
    first_name = data.get("first_name", "")
    last_name = data.get("last_name", "")
    display_name = f"{first_name} {last_name}".strip() or email

    if not email:
        logger.warning("clerk_webhook_missing_email", clerk_user_id=clerk_user_id)
        raise HTTPException(status_code=400, detail="Missing email in user data")

    # Check if user exists by email (link existing admin-created user)
    existing_user_by_email = await _find_user_by_email(db, email)
    if existing_user_by_email:
        # Link the Clerk ID to the existing user
        existing_user_by_email.clerk_user_id = clerk_user_id
        if not existing_user_by_email.display_name:
            existing_user_by_email.display_name = display_name

        await _create_audit_log(
            db,
            existing_user_by_email.id,
            "user.linked_to_clerk",
            {"clerk_user_id": clerk_user_id, "email": email},
        )
        await db.commit()  # Single atomic commit: user update + audit log

        logger.info(
            "clerk_user_linked",
            clerk_user_id=clerk_user_id,
            user_id=existing_user_by_email.id,
        )
        return {
            "status": "success",
            "message": "Existing user linked to Clerk",
            "user_id": existing_user_by_email.id,
        }

    # Create new user
    user_id = str(uuid.uuid4())
    api_key = _generate_api_key()

    user = User(
        id=user_id,
        clerk_user_id=clerk_user_id,
        email=email,
        display_name=display_name,
        api_key=api_key,
        status=UserStatus.ACTIVE,
    )
    db.add(user)

    await _create_audit_log(
        db,
        user_id,
        "user.created",
        {
            "clerk_user_id": clerk_user_id,
            "email": email,
            "source": "clerk_webhook",
        },
    )
    await db.commit()

    logger.info(
        "clerk_user_provisioned",
        clerk_user_id=clerk_user_id,
        user_id=user_id,
        email=email,
    )

    # Fire-and-forget Railway provisioning — must not block the webhook response
    # (Clerk expects a 2xx within 5 s). provision_user_background creates its own
    # DB session so it is safe after this request's session is committed.
    asyncio.create_task(
        get_session_manager().provision_user_background(user_id),
        name=f"provision_{user_id}",
    )
    logger.info("railway_provision_task_scheduled", user_id=user_id)

    return {
        "status": "success",
        "message": "User provisioned successfully",
        "user_id": user_id,
    }


async def _handle_user_updated(
    db: AsyncSession, data: dict, clerk_user_id: str
) -> dict:
    """Handle user.updated event - sync email and display name.

    Idempotent: Only updates if data has changed.
    """
    user = await _find_user_by_clerk_id(db, clerk_user_id)
    if not user:
        # Try to find by email if not linked yet
        email_addresses = data.get("email_addresses", [])
        email = email_addresses[0].get("email_address", "") if email_addresses else ""
        if email:
            user = await _find_user_by_email(db, email)
            if user:
                # Link the Clerk ID during update
                user.clerk_user_id = clerk_user_id

    if not user:
        logger.warning(
            "clerk_user_not_found_for_update",
            clerk_user_id=clerk_user_id,
        )
        raise HTTPException(status_code=404, detail="User not found")

    # Update fields from Clerk data
    email_addresses = data.get("email_addresses", [])
    new_email = email_addresses[0].get("email_address", "") if email_addresses else ""
    first_name = data.get("first_name", "")
    last_name = data.get("last_name", "")
    new_display_name = f"{first_name} {last_name}".strip()

    changes = {}
    if new_email and new_email != user.email:
        changes["email"] = {"old": user.email, "new": new_email}
        user.email = new_email

    if new_display_name and new_display_name != user.display_name:
        changes["display_name"] = {"old": user.display_name, "new": new_display_name}
        user.display_name = new_display_name

    if changes:
        await _create_audit_log(
            db,
            user.id,
            "user.updated",
            {"source": "clerk_webhook", "changes": changes},
        )
        await db.commit()

        logger.info(
            "clerk_user_synced",
            clerk_user_id=clerk_user_id,
            user_id=user.id,
            changes=changes,
        )
    else:
        logger.info(
            "clerk_user_no_changes",
            clerk_user_id=clerk_user_id,
            user_id=user.id,
        )

    return {
        "status": "success",
        "message": "User synced successfully",
        "user_id": user.id,
    }


async def _handle_user_deleted(
    db: AsyncSession, data: dict, clerk_user_id: str
) -> dict:
    """Handle user.deleted event - spin down service and soft-delete user.

    Idempotent: If user already soft-deleted, returns success without changes.
    """
    user = await _find_user_by_clerk_id(db, clerk_user_id)
    if not user:
        logger.info(
            "clerk_user_not_found_for_delete",
            clerk_user_id=clerk_user_id,
        )
        return {
            "status": "success",
            "message": "User already deleted or not found",
        }

    if user.status == UserStatus.SUSPENDED:
        # Already soft-deleted
        logger.info(
            "clerk_user_already_deleted",
            clerk_user_id=clerk_user_id,
            user_id=user.id,
        )
        return {
            "status": "success",
            "message": "User already deleted",
            "user_id": user.id,
        }

    # Spin down Railway service if active
    if user.railway_service_id:
        try:
            session_manager = get_session_manager()
            await session_manager.spin_down_user_service(db, user.id)
            logger.info(
                "clerk_user_service_spun_down",
                clerk_user_id=clerk_user_id,
                user_id=user.id,
            )
        except Exception as e:
            logger.error(
                "clerk_user_service_spin_down_failed",
                clerk_user_id=clerk_user_id,
                user_id=user.id,
                error=str(e),
            )

    old_status = user.status.value
    user.status = UserStatus.SUSPENDED
    user.railway_service_id = None
    user.volume_id = None

    await _create_audit_log(
        db,
        user.id,
        "user.deleted",
        {
            "source": "clerk_webhook",
            "old_status": old_status,
            "clerk_user_id": clerk_user_id,
        },
    )
    await db.commit()

    logger.info(
        "clerk_user_soft_deleted",
        clerk_user_id=clerk_user_id,
        user_id=user.id,
        email=user.email,
    )
    return {
        "status": "success",
        "message": "User soft-deleted successfully",
        "user_id": user.id,
    }
