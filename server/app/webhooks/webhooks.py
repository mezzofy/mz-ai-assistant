"""
Webhooks API — inbound event webhooks from external systems.

Endpoints:
    POST /webhooks/mezzofy          — Events from Mezzofy platform
    POST /webhooks/teams            — Adaptive card actions / @mentions from MS Teams bot
    POST /webhooks/custom/{source}  — Generic webhooks from Zapier, GitHub, Stripe, etc.

Security:
    /webhooks/mezzofy:  HMAC-SHA256 signature in X-Webhook-Signature header
    /webhooks/teams:    MS Bot Framework verification token
    /webhooks/custom:   HMAC-SHA256 signature in X-Webhook-Signature header

Design contract:
    All endpoints MUST:
    1. Verify signature/token (reject with 401/403 if invalid)
    2. Parse and validate payload
    3. Record event in webhook_events table
    4. Enqueue a Celery task (non-blocking)
    5. Return HTTP 200 immediately (< 3 seconds)
    Celery workers handle all heavy processing asynchronously.
"""

import hashlib
import hmac
import json
import logging
import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.core.database import AsyncSessionLocal
from app.core.dependencies import require_role

logger = logging.getLogger("mezzofy.api.webhooks")
router = APIRouter(tags=["webhooks"])


# ── Signature verification helpers ────────────────────────────────────────────

def _get_webhook_secret() -> str:
    """Return the shared HMAC secret for webhook signature verification."""
    return os.getenv("WEBHOOK_SECRET", "")


def _verify_hmac_signature(body: bytes, signature_header: str) -> bool:
    """
    Verify HMAC-SHA256 webhook signature.

    Expected header format: "sha256=<hex_digest>"
    Returns True if signature is valid, False otherwise.
    """
    secret = _get_webhook_secret()
    if not secret:
        # No secret configured — accept all (development mode)
        logger.warning("WEBHOOK_SECRET not set — signature verification skipped")
        return True

    if not signature_header:
        return False

    # Support "sha256=<hex>" format
    if signature_header.startswith("sha256="):
        expected_sig = signature_header[7:]
    else:
        expected_sig = signature_header

    computed = hmac.new(
        secret.encode("utf-8"),
        body,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(computed, expected_sig)


def _verify_teams_token(auth_header: str) -> bool:
    """
    Verify MS Teams bot authorization token.

    Teams sends: Authorization: Bearer <bot_token>
    For Phase 6, we validate the token matches TEAMS_BOT_SECRET env var.
    Production should use the full MS Bot Framework JWT validation.
    """
    teams_secret = os.getenv("TEAMS_BOT_SECRET", "")
    if not teams_secret:
        logger.warning("TEAMS_BOT_SECRET not set — Teams token verification skipped")
        return True

    if not auth_header or not auth_header.startswith("Bearer "):
        return False

    token = auth_header[7:]
    # Constant-time comparison
    return hmac.compare_digest(token, teams_secret)


# ── DB helpers ────────────────────────────────────────────────────────────────

async def _record_webhook_event(
    db: AsyncSession,
    source: str,
    event_type: str,
    payload: dict,
    task_id: str | None = None,
) -> str:
    """Insert a record into webhook_events and return the event UUID."""
    event_id = str(uuid.uuid4())
    await db.execute(
        text(
            """
            INSERT INTO webhook_events
              (id, source, event_type, payload, status, task_id, created_at)
            VALUES
              (:id, :source, :event_type, :payload, 'received', :task_id, :now)
            """
        ),
        {
            "id": event_id,
            "source": source,
            "event_type": event_type,
            "payload": json.dumps(payload),
            "task_id": task_id,
            "now": datetime.now(timezone.utc),
        },
    )
    return event_id


# ── POST /webhooks/mezzofy ────────────────────────────────────────────────────

@router.post("/mezzofy", status_code=status.HTTP_200_OK)
async def mezzofy_webhook(request: Request):
    """
    Handle Mezzofy platform events.

    Supported events:
      customer_signed_up, customer_churned, order_completed,
      support_ticket_created, feature_released

    Authentication: HMAC-SHA256 signature in X-Webhook-Signature header.
    Returns 200 immediately; Celery processes asynchronously.
    """
    # Read raw body for HMAC verification
    body = await request.body()
    sig_header = request.headers.get("X-Webhook-Signature", "")

    if not _verify_hmac_signature(body, sig_header):
        logger.warning("Mezzofy webhook: invalid HMAC signature")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature",
        )

    # Parse payload
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Webhook body must be valid JSON",
        )

    event_type = payload.get("event", "")
    if not event_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing 'event' field in webhook payload",
        )

    # Record event and enqueue Celery task
    from app.tasks.webhook_tasks import handle_mezzofy_event

    async with AsyncSessionLocal() as db:
        event_id = await _record_webhook_event(db, "mezzofy", event_type, payload)
        await db.commit()

    celery_task = handle_mezzofy_event.delay(event_id, event_type, payload)

    # Update record with Celery task ID
    async with AsyncSessionLocal() as db:
        await db.execute(
            text("UPDATE webhook_events SET task_id = :tid WHERE id = :id"),
            {"tid": celery_task.id, "id": event_id},
        )
        await db.commit()

    logger.info(
        f"Mezzofy webhook received: event={event_type!r} event_id={event_id} "
        f"celery_task={celery_task.id}"
    )
    return {
        "received": True,
        "event_type": event_type,
        "event_id": event_id,
        "task_id": celery_task.id,
    }


# ── POST /webhooks/teams ──────────────────────────────────────────────────────

@router.post("/teams", status_code=status.HTTP_200_OK)
async def teams_webhook(request: Request):
    """
    Handle Microsoft Teams bot events (@mentions, adaptive card actions).

    The Teams Bot Framework sends webhook events when a user @mentions the
    Mezzofy AI bot in a channel. The bot processes the message through the
    Gateway → Router → Agent pipeline and replies to the channel.

    Authentication: Bearer token in Authorization header (TEAMS_BOT_SECRET).
    Returns 200 immediately; Celery processes asynchronously.
    """
    auth_header = request.headers.get("Authorization", "")
    if not _verify_teams_token(auth_header):
        logger.warning("Teams webhook: invalid bot token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Teams bot authorization",
        )

    body = await request.body()
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Webhook body must be valid JSON",
        )

    # Extract Teams activity type
    activity_type = payload.get("type", "message")
    if activity_type not in ("message", "invoke"):
        # Non-message activity (e.g. conversationUpdate) — acknowledge and ignore
        return {"received": True, "processed": False, "reason": f"activity_type={activity_type!r}"}

    # Record event
    from app.tasks.webhook_tasks import handle_teams_mention

    async with AsyncSessionLocal() as db:
        event_id = await _record_webhook_event(db, "teams", activity_type, payload)
        await db.commit()

    celery_task = handle_teams_mention.delay(event_id, payload)

    async with AsyncSessionLocal() as db:
        await db.execute(
            text("UPDATE webhook_events SET task_id = :tid WHERE id = :id"),
            {"tid": celery_task.id, "id": event_id},
        )
        await db.commit()

    logger.info(
        f"Teams webhook received: type={activity_type!r} event_id={event_id} "
        f"celery_task={celery_task.id}"
    )
    return {
        "received": True,
        "event_id": event_id,
        "task_id": celery_task.id,
    }


# ── POST /webhooks/custom/{source} ────────────────────────────────────────────

@router.post("/custom/{source}", status_code=status.HTTP_200_OK)
async def custom_webhook(source: str, request: Request):
    """
    Handle custom webhook events from any external service (Zapier, GitHub, Stripe, etc.)

    The source path parameter identifies the sending service.
    Authentication: HMAC-SHA256 signature in X-Webhook-Signature header.
    Returns 200 immediately; Celery processes asynchronously.
    """
    # Validate source — alphanumeric + hyphens only
    if not source or not source.replace("-", "").isalnum():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid source identifier. Use alphanumeric characters and hyphens only.",
        )

    body = await request.body()
    sig_header = request.headers.get("X-Webhook-Signature", "")

    if not _verify_hmac_signature(body, sig_header):
        logger.warning(f"Custom webhook [{source}]: invalid HMAC signature")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature",
        )

    try:
        payload = json.loads(body) if body else {}
    except json.JSONDecodeError:
        # Some services send form-encoded or plain text — wrap in dict
        payload = {"raw": body.decode("utf-8", errors="replace")}

    # Record event and enqueue task
    from app.tasks.webhook_tasks import handle_custom_event

    async with AsyncSessionLocal() as db:
        event_id = await _record_webhook_event(db, source, "custom", payload)
        await db.commit()

    celery_task = handle_custom_event.delay(event_id, source, payload)

    async with AsyncSessionLocal() as db:
        await db.execute(
            text("UPDATE webhook_events SET task_id = :tid WHERE id = :id"),
            {"tid": celery_task.id, "id": event_id},
        )
        await db.commit()

    logger.info(
        f"Custom webhook received: source={source!r} event_id={event_id} "
        f"celery_task={celery_task.id}"
    )
    return {
        "received": True,
        "source": source,
        "event_id": event_id,
        "task_id": celery_task.id,
    }


# ── GET /webhooks/events (audit — admin only) ─────────────────────────────────

@router.get("/events")
async def list_webhook_events(
    limit: int = 50,
    offset: int = 0,
    source: str | None = None,
    status_filter: str | None = None,
    current_user: dict = Depends(require_role("admin", "executive")),
):
    """
    List webhook event history. Admin and executive roles only.

    Query params:
        limit, offset: pagination
        source: filter by source (mezzofy, teams, custom/*)
        status_filter: filter by status (received, processing, completed, failed)
    """

    query = (
        "SELECT id, source, event_type, status, task_id, error_msg, created_at, processed_at "
        "FROM webhook_events"
    )
    params: dict = {"limit": limit, "offset": offset}
    conditions = []

    if source:
        conditions.append("source = :source")
        params["source"] = source
    if status_filter:
        conditions.append("status = :status_filter")
        params["status_filter"] = status_filter

    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY created_at DESC LIMIT :limit OFFSET :offset"

    async with AsyncSessionLocal() as db:
        result = await db.execute(text(query), params)
        rows = result.fetchall()

    return {
        "events": [
            {
                "id": row.id,
                "source": row.source,
                "event_type": row.event_type,
                "status": row.status,
                "task_id": row.task_id,
                "error_msg": row.error_msg,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "processed_at": row.processed_at.isoformat() if row.processed_at else None,
            }
            for row in rows
        ],
        "count": len(rows),
    }
