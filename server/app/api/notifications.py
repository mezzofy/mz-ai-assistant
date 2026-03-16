"""
Notifications API — FCM device registration and push preferences.

Endpoints:
    POST   /notifications/register-device    — Upsert FCM token for current user
    DELETE /notifications/unregister-device  — Remove token (called on logout)
    PUT    /notifications/preferences        — Toggle push_notifications_enabled

All endpoints require a valid JWT access token (Bearer).
"""

import logging
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db

logger = logging.getLogger("mezzofy.api.notifications")

router = APIRouter(tags=["notifications"])


# ── DTOs ──────────────────────────────────────────────────────────────────────

class RegisterDeviceRequest(BaseModel):
    device_token: str
    platform: str = "android"


class UnregisterDeviceRequest(BaseModel):
    device_token: str
    platform: str = "android"


class PushPreferenceRequest(BaseModel):
    push_notifications_enabled: bool


class NotificationRecord(BaseModel):
    id: UUID
    title: str
    body: str
    data: Optional[Any] = None
    sent_at: datetime


class NotificationHistoryResponse(BaseModel):
    notifications: list[NotificationRecord]
    count: int


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/register-device")
async def register_device(
    body: RegisterDeviceRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upsert an FCM device token for the current user."""
    if not body.device_token or not body.device_token.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="device_token is required",
        )
    if body.platform not in ("android", "ios"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="platform must be 'android' or 'ios'",
        )

    uid = current_user["user_id"]

    await db.execute(
        text("""
            INSERT INTO user_devices (user_id, device_token, platform)
            VALUES (:uid, :token, :platform)
            ON CONFLICT (device_token)
            DO UPDATE SET
                user_id    = EXCLUDED.user_id,
                platform   = EXCLUDED.platform,
                updated_at = NOW()
        """),
        {"uid": uid, "token": body.device_token, "platform": body.platform},
    )
    await db.commit()

    logger.info(f"Device registered: user={uid} platform={body.platform}")
    return {"registered": True}


@router.delete("/unregister-device")
async def unregister_device(
    body: UnregisterDeviceRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove an FCM device token (called on logout)."""
    uid = current_user["user_id"]

    await db.execute(
        text(
            "DELETE FROM user_devices WHERE device_token = :token AND user_id = :uid"
        ),
        {"token": body.device_token, "uid": uid},
    )
    await db.commit()

    logger.info(f"Device unregistered: user={uid}")
    return {"unregistered": True}


@router.put("/preferences")
async def update_push_preferences(
    body: PushPreferenceRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Toggle push_notifications_enabled for the current user."""
    uid = current_user["user_id"]

    await db.execute(
        text(
            "UPDATE users SET push_notifications_enabled = :val WHERE id = :uid"
        ),
        {"val": body.push_notifications_enabled, "uid": uid},
    )
    await db.commit()

    logger.info(f"Push preference updated: user={uid} enabled={body.push_notifications_enabled}")
    return {"push_notifications_enabled": body.push_notifications_enabled}


@router.get("/history", response_model=NotificationHistoryResponse)
async def get_notification_history(
    limit: int = Query(default=10, ge=1, le=50),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the last N push notifications sent to the current user."""
    uid = current_user["user_id"]
    clamped = min(max(limit, 1), 50)

    result = await db.execute(
        text("""
            SELECT id, title, body, data, sent_at
            FROM notification_log
            WHERE user_id = :uid
            ORDER BY sent_at DESC
            LIMIT :lim
        """),
        {"uid": uid, "lim": clamped},
    )
    rows = result.fetchall()
    records = [
        NotificationRecord(
            id=r.id,
            title=r.title,
            body=r.body,
            data=r.data,
            sent_at=r.sent_at,
        )
        for r in rows
    ]
    return NotificationHistoryResponse(notifications=records, count=len(records))
