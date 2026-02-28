"""
Auth API — JWT login, token refresh, and logout endpoints.

Endpoints:
    POST /auth/login   — email + password → {access_token, refresh_token, user_info}
    POST /auth/refresh — refresh_token → {access_token}
    POST /auth/logout  — blacklist refresh token
    GET  /auth/me      — return current user info from JWT
"""

from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from jose import JWTError

from app.core.database import get_db
from app.core.auth import (
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    blacklist_refresh_token,
    is_refresh_token_blacklisted,
    CONFIG as AUTH_CONFIG,
)
from app.core.rbac import enrich_user_with_permissions
from app.core.dependencies import get_current_user
from app.core.rate_limiter import rate_limit_auth

router = APIRouter(tags=["auth"])


# ── Request / Response DTOs ───────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_info: dict


class RefreshRequest(BaseModel):
    refresh_token: str


class RefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LogoutRequest(BaseModel):
    refresh_token: str


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_user_by_email(db: AsyncSession, email: str) -> Optional[dict]:
    """Fetch a user row from the database by email address."""
    from sqlalchemy import text
    result = await db.execute(
        text("""
            SELECT id, email, password_hash, name, department, role, is_active
            FROM users
            WHERE email = :email
        """),
        {"email": email},
    )
    row = result.mappings().first()
    if row:
        return dict(row)
    return None


async def _update_last_login(db: AsyncSession, user_id: str) -> None:
    """Update the last_login timestamp for a user."""
    from sqlalchemy import text
    await db.execute(
        text("UPDATE users SET last_login = NOW() WHERE id = :id"),
        {"id": user_id},
    )
    await db.commit()


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/login", response_model=LoginResponse)
async def login(
    request: Request,
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
    _rl: None = Depends(rate_limit_auth),  # IP-based brute-force protection (10 req/min)
):
    """
    Authenticate a user with email and password.
    Returns a short-lived access token and a long-lived refresh token.
    The access token carries full user info (department, role, permissions).
    """
    # Look up user
    user = await _get_user_by_email(db, body.email)

    # Constant-time comparison (prevents timing attacks)
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is inactive. Contact your administrator.",
        )

    # Enrich with permissions from roles.yaml
    user_data = enrich_user_with_permissions(dict(user))

    # Generate tokens
    access_token = create_access_token(user_data)
    refresh_token = create_refresh_token(user_data)

    # Update last login (non-blocking — don't fail login if this errors)
    try:
        await _update_last_login(db, str(user["id"]))
    except Exception:
        pass

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user_info={
            "id": str(user["id"]),
            "email": user["email"],
            "name": user["name"],
            "department": user["department"],
            "role": user["role"],
            "permissions": user_data["permissions"],
        },
    )


@router.post("/refresh", response_model=RefreshResponse)
async def refresh_token(
    request: Request,
    body: RefreshRequest,
    _rl: None = Depends(rate_limit_auth),  # IP-based rate limit (10 req/min)
):
    """
    Exchange a valid refresh token for a new access token.
    The refresh token must not be blacklisted (i.e. not logged out).
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired refresh token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_refresh_token(body.refresh_token)
    except (JWTError, ValueError):
        raise credentials_exception

    jti = payload.get("jti")
    if not jti:
        raise credentials_exception

    # Check blacklist
    if await is_refresh_token_blacklisted(jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has been revoked. Please log in again.",
        )

    # Issue new access token
    new_access_token = create_access_token(payload)
    return RefreshResponse(access_token=new_access_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    body: LogoutRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Invalidate the provided refresh token by adding its JTI to the Redis blacklist.
    The access token will naturally expire after 60 minutes.
    """
    try:
        payload = decode_refresh_token(body.refresh_token)
        jti = payload.get("jti")
        exp = payload.get("exp", 0)
        if jti:
            # Calculate remaining TTL for the refresh token
            now_ts = int(datetime.now(timezone.utc).timestamp())
            remaining_seconds = max(exp - now_ts, 0)
            await blacklist_refresh_token(jti, remaining_seconds or 1)
    except (JWTError, ValueError):
        pass  # Token is already invalid — logout is idempotent


@router.get("/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    """
    Return the currently authenticated user's info from their JWT payload.
    No database call required — info is encoded in the token.
    """
    return {
        "id": current_user.get("user_id"),
        "email": current_user.get("email"),
        "name": current_user.get("name"),
        "department": current_user.get("department"),
        "role": current_user.get("role"),
        "permissions": current_user.get("permissions", []),
    }
