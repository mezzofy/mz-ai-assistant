"""
MS OAuth API — Delegated (per-user) Microsoft account OAuth 2.0 flow.

Endpoints:
    GET    /ms/auth/url         — Generate Microsoft login URL for the user
    POST   /ms/auth/callback    — Exchange auth code for tokens and store them
    GET    /ms/auth/status      — Check if user has a connected MS account
    DELETE /ms/auth/disconnect  — Remove stored MS tokens for the user

All endpoints require a valid JWT access token (Bearer).

Flow:
    Mobile app calls GET /ms/auth/url
        → opens auth_url in in-app browser
        → Microsoft redirects to msalauth://callback?code=...&state=...
        → app extracts code + state params
        → calls POST /ms/auth/callback with {code, state}
        → tokens stored encrypted; user is "connected"
"""

import logging
import os
from datetime import datetime, timezone, timedelta

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, DBSession
from app.core.config import MS365_DELEGATED_SCOPES, MS365_DELEGATED_REDIRECT_URI

logger = logging.getLogger("mezzofy.api.ms_oauth")

router = APIRouter(tags=["ms-oauth"])

_GRAPH_ME = "https://graph.microsoft.com/v1.0/me"


# ── DTOs ─────────────────────────────────────────────────────────────────────

class CallbackRequest(BaseModel):
    code: str
    state: str


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_msal_app():
    """Build a MSAL ConfidentialClientApplication for delegated auth."""
    import msal
    client_id = os.getenv("MS365_CLIENT_ID", "")
    client_secret = os.getenv("MS365_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MS365 OAuth is not configured on this server",
        )
    return msal.ConfidentialClientApplication(
        client_id=client_id,
        client_credential=client_secret,
        # Use "common" to allow personal Microsoft accounts AND work/school accounts
        authority="https://login.microsoftonline.com/common",
    )


def _create_state_jwt(user_id: str) -> str:
    """Create a short-lived state JWT to prevent CSRF in OAuth callback."""
    secret = os.getenv("JWT_SECRET", "INSECURE_DEFAULT_CHANGE_ME")
    now = datetime.now(timezone.utc)
    payload = {
        "user_id": user_id,
        "purpose": "ms_oauth_state",
        "exp": int((now + timedelta(minutes=10)).timestamp()),
        "iat": int(now.timestamp()),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def _decode_state_jwt(state_token: str) -> dict:
    """Decode and validate the OAuth state JWT."""
    secret = os.getenv("JWT_SECRET", "INSECURE_DEFAULT_CHANGE_ME")
    try:
        payload = jwt.decode(state_token, secret, algorithms=["HS256"])
        if payload.get("purpose") != "ms_oauth_state":
            raise ValueError("Invalid state token purpose")
        return payload
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid or expired OAuth state token: {e}",
        )


async def _log_audit(db: AsyncSession, user_id: str, action: str, details: dict = None) -> None:
    """Write an entry to audit_log."""
    try:
        import json
        await db.execute(
            text("""
                INSERT INTO audit_log (user_id, action, resource, details, success)
                VALUES (:uid, :action, 'ms_oauth', :details, true)
            """),
            {
                "uid": user_id,
                "action": action,
                "details": json.dumps(details or {}),
            },
        )
    except Exception as e:
        logger.warning(f"Audit log write failed: {e}")


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/auth/url")
async def get_auth_url(
    current_user: dict = Depends(get_current_user),
):
    """
    Generate a Microsoft OAuth login URL for the current user.
    The URL should be opened in an in-app browser on the mobile client.
    """
    user_id = current_user["user_id"]
    msal_app = _get_msal_app()
    state_jwt = _create_state_jwt(user_id)

    auth_url = msal_app.get_authorization_request_url(
        scopes=MS365_DELEGATED_SCOPES,
        state=state_jwt,
        redirect_uri=MS365_DELEGATED_REDIRECT_URI,
    )

    logger.info(f"Generated MS OAuth URL for user {user_id}")
    return {"auth_url": auth_url, "state": state_jwt}


@router.post("/auth/callback")
async def oauth_callback(
    body: CallbackRequest,
    current_user: dict = Depends(get_current_user),
    db: DBSession = None,
):
    """
    Exchange the authorization code for tokens and store them.
    Called by the mobile app after the user authenticates in the browser.
    """
    user_id = current_user["user_id"]

    # Validate state JWT (CSRF protection)
    state_payload = _decode_state_jwt(body.state)
    if state_payload.get("user_id") != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="State token user mismatch — possible CSRF attempt",
        )

    # Exchange code for tokens via MSAL
    msal_app = _get_msal_app()
    result = msal_app.acquire_token_by_authorization_code(
        code=body.code,
        scopes=MS365_DELEGATED_SCOPES,
        redirect_uri=MS365_DELEGATED_REDIRECT_URI,
    )

    if "error" in result:
        logger.error(f"MSAL code exchange failed for user {user_id}: {result}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Token exchange failed: {result.get('error_description', result.get('error'))}",
        )

    access_token = result["access_token"]
    refresh_token = result.get("refresh_token", "")
    expires_in = result.get("expires_in", 3600)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    scopes_list = result.get("scope", "").split()

    # Fetch MS user profile
    ms_user_id = ""
    ms_email = ""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                _GRAPH_ME,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if resp.status_code == 200:
                me = resp.json()
                ms_user_id = me.get("id", "")
                ms_email = me.get("mail") or me.get("userPrincipalName", "")
    except Exception as e:
        logger.warning(f"Failed to fetch MS user profile for {user_id}: {e}")

    # Store encrypted tokens
    from app.services.ms_token_service import save_tokens
    await save_tokens(
        user_id=user_id,
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=expires_at,
        ms_user_id=ms_user_id,
        ms_email=ms_email,
        scopes=" ".join(scopes_list),
    )

    # Audit log (use fresh session since save_tokens has its own)
    from app.core.database import AsyncSessionLocal
    async with AsyncSessionLocal() as audit_session:
        await _log_audit(
            audit_session,
            user_id,
            "ms_oauth_connected",
            {"ms_email": ms_email, "scopes": scopes_list},
        )
        await audit_session.commit()

    logger.info(f"MS OAuth connected for user {user_id} → {ms_email}")
    return {
        "connected": True,
        "ms_email": ms_email,
        "scopes": scopes_list,
    }


@router.get("/auth/status")
async def get_auth_status(
    current_user: dict = Depends(get_current_user),
):
    """Return the current user's MS account connection status."""
    from app.services.ms_token_service import get_token_status
    user_id = current_user["user_id"]
    return await get_token_status(user_id)


@router.delete("/auth/disconnect")
async def disconnect(
    current_user: dict = Depends(get_current_user),
):
    """Remove the current user's stored MS OAuth tokens."""
    user_id = current_user["user_id"]

    from app.services.ms_token_service import delete_tokens
    await delete_tokens(user_id)

    # Audit log
    from app.core.database import AsyncSessionLocal
    async with AsyncSessionLocal() as audit_session:
        await _log_audit(audit_session, user_id, "ms_oauth_disconnected")
        await audit_session.commit()

    logger.info(f"MS OAuth disconnected for user {user_id}")
    return {"disconnected": True}
