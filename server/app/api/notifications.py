"""
Notifications API — FCM device registration and push preferences.

Endpoints:
    POST   /notifications/register-device    — Upsert FCM token for current user
    DELETE /notifications/unregister-device  — Remove token (called on logout)
    PUT    /notifications/preferences        — Toggle push_notifications_enabled

All endpoints require a valid JWT access token (Bearer).
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
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
