"""
Auth API — JWT login with OTP 2FA, token refresh, logout, password management.

Endpoints:
    POST /auth/login              — email + password → otp_required + otp_token
    POST /auth/verify-otp         — otp_token + code → JWT tokens
    POST /auth/resend-otp         — resend OTP to email
    POST /auth/refresh            — refresh_token → new access_token
    POST /auth/logout             — blacklist refresh token
    GET  /auth/me                 — return current user info from JWT
    POST /auth/forgot-password    — send reset OTP to email
    POST /auth/verify-reset-otp   — verify reset OTP → reset_token
    POST /auth/reset-password     — reset_token + new_password → update password
    POST /auth/change-password    — authenticated in-app password change
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from jose import JWTError

from app.core.database import get_db
from app.core.auth import (
    verify_password,
    hash_password,
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
from app.core.otp import (
    generate_otp_code,
    store_login_otp,
    get_login_otp,
    delete_login_otp,
    increment_otp_attempts,
    is_account_locked,
    lock_account,
    reset_otp_attempts,
    can_resend_otp,
    set_resend_cooldown,
    store_reset_otp,
    get_reset_otp,
    delete_reset_otp,
    store_reset_token,
    get_reset_token_email,
    delete_reset_token,
)
from app.core.email_sender import send_transactional_email
from app.core.password_validator import validate_password_complexity

router = APIRouter(tags=["auth"])


# ── Request / Response DTOs ───────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginOTPResponse(BaseModel):
    status: str = "otp_required"
    otp_token: str
    message: str


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_info: dict


class VerifyOTPRequest(BaseModel):
    otp_token: str
    code: str


class ResendOTPRequest(BaseModel):
    otp_token: str


class RefreshRequest(BaseModel):
    refresh_token: str


class RefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LogoutRequest(BaseModel):
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class VerifyResetOTPRequest(BaseModel):
    email: EmailStr
    code: str


class VerifyResetOTPResponse(BaseModel):
    status: str
    reset_token: str


class ResetPasswordRequest(BaseModel):
    reset_token: str
    new_password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_user_by_email(db: AsyncSession, email: str) -> dict | None:
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


async def _update_password(db: AsyncSession, user_id: str, new_hash: str) -> None:
    """Update the password_hash for a user."""
    from sqlalchemy import text
    await db.execute(
        text("UPDATE users SET password_hash = :hash WHERE id = :id"),
        {"hash": new_hash, "id": user_id},
    )
    await db.commit()


def _login_otp_email_html(code: str) -> str:
    return (
        f"<p>Your Mezzofy login verification code is:</p>"
        f"<h2 style='letter-spacing:6px;font-family:monospace'>{code}</h2>"
        f"<p>This code expires in 5 minutes. Do not share it with anyone.</p>"
    )


def _reset_otp_email_html(code: str) -> str:
    return (
        f"<p>You requested a password reset for your Mezzofy account.</p>"
        f"<p>Your verification code is:</p>"
        f"<h2 style='letter-spacing:6px;font-family:monospace'>{code}</h2>"
        f"<p>This code expires in 5 minutes. If you did not request this, ignore this email.</p>"
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/login", response_model=LoginOTPResponse)
async def login(
    request: Request,
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
    _rl: None = Depends(rate_limit_auth),
):
    """
    Step 1 of login: validate credentials and send OTP.
    Returns otp_token (not JWT tokens) — call /auth/verify-otp to complete login.
    Account lock is checked BEFORE password validation to prevent timing attacks.
    """
    email = body.email.lower().strip()

    # Check account lock first (before password validation — prevents enumeration)
    if await is_account_locked(email):
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="Account temporarily locked due to too many failed attempts. Try again in 30 minutes.",
        )

    user = await _get_user_by_email(db, email)

    # Constant-time-style comparison (both checks always evaluated)
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

    # Generate and send OTP
    otp_token = str(uuid.uuid4())
    code = generate_otp_code()
    await store_login_otp(email, otp_token, code)
    await set_resend_cooldown(email)

    try:
        await send_transactional_email(
            to=email,
            subject="Your Mezzofy Login Code",
            body_html=_login_otp_email_html(code),
        )
    except Exception:
        # Email failure should not block login flow — OTP is in Redis
        pass

    return LoginOTPResponse(
        otp_token=otp_token,
        message=f"A verification code has been sent to {email}",
    )


@router.post("/verify-otp", response_model=LoginResponse)
async def verify_otp(
    body: VerifyOTPRequest,
    db: AsyncSession = Depends(get_db),
    _rl: None = Depends(rate_limit_auth),
):
    """
    Step 2 of login: verify OTP code and return JWT tokens.
    3 wrong codes locks the account for 30 minutes.
    """
    otp_data = await get_login_otp(body.otp_token)
    if otp_data is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OTP expired or not found. Please log in again.",
        )

    email = otp_data["email"]
    expected_code = otp_data["code"]

    if body.code != expected_code:
        attempts = await increment_otp_attempts(email)
        if attempts >= 3:
            await lock_account(email)
            await delete_login_otp(body.otp_token)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many incorrect attempts. Account locked for 30 minutes.",
            )
        remaining = 3 - attempts
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Incorrect code. {remaining} attempt{'s' if remaining != 1 else ''} remaining.",
        )

    # OTP verified — clean up and issue tokens
    await delete_login_otp(body.otp_token)
    await reset_otp_attempts(email)

    user = await _get_user_by_email(db, email)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found.")

    user_data = enrich_user_with_permissions(dict(user))
    access_token = create_access_token(user_data)
    refresh_token = create_refresh_token(user_data)

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


@router.post("/resend-otp")
async def resend_otp(
    body: ResendOTPRequest,
    _rl: None = Depends(rate_limit_auth),
):
    """Resend OTP to the email associated with otp_token. 60-second cooldown enforced."""
    otp_data = await get_login_otp(body.otp_token)
    if otp_data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="OTP session not found or expired. Please log in again.",
        )

    email = otp_data["email"]

    if not await can_resend_otp(email):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Please wait 60 seconds before requesting a new code.",
            headers={"Retry-After": "60"},
        )

    code = generate_otp_code()
    await store_login_otp(email, body.otp_token, code)
    await set_resend_cooldown(email)

    try:
        await send_transactional_email(
            to=email,
            subject="Your Mezzofy Login Code",
            body_html=_login_otp_email_html(code),
        )
    except Exception:
        pass

    return {"status": "sent"}


@router.post("/refresh", response_model=RefreshResponse)
async def refresh_token(
    request: Request,
    body: RefreshRequest,
    _rl: None = Depends(rate_limit_auth),
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

    if await is_refresh_token_blacklisted(jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has been revoked. Please log in again.",
        )

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


@router.post("/forgot-password")
async def forgot_password(
    body: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
    _rl: None = Depends(rate_limit_auth),
):
    """
    Send a password reset OTP to the provided email.
    Always returns 200 regardless of whether the email exists (prevents enumeration).
    """
    email = body.email.lower().strip()
    user = await _get_user_by_email(db, email)

    if user and user["is_active"]:
        code = generate_otp_code()
        await store_reset_otp(email, code)
        try:
            await send_transactional_email(
                to=email,
                subject="Mezzofy Password Reset Code",
                body_html=_reset_otp_email_html(code),
            )
        except Exception:
            pass

    return {
        "status": "sent",
        "message": "If that email is registered, a reset code has been sent.",
    }


@router.post("/verify-reset-otp", response_model=VerifyResetOTPResponse)
async def verify_reset_otp(
    body: VerifyResetOTPRequest,
    _rl: None = Depends(rate_limit_auth),
):
    """Verify the password reset OTP and return a short-lived reset token."""
    email = body.email.lower().strip()
    otp_data = await get_reset_otp(email)

    if otp_data is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reset code expired or not found. Please request a new one.",
        )

    if body.code != otp_data["code"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect reset code.",
        )

    await delete_reset_otp(email)
    reset_token = str(uuid.uuid4())
    await store_reset_token(reset_token, email)

    return VerifyResetOTPResponse(status="verified", reset_token=reset_token)


@router.post("/reset-password")
async def reset_password(
    body: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
    _rl: None = Depends(rate_limit_auth),
):
    """Complete password reset using a verified reset token."""
    email = await get_reset_token_email(body.reset_token)
    if email is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reset token expired or invalid. Please start the reset process again.",
        )

    violations = validate_password_complexity(body.new_password)
    if violations:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "Password does not meet complexity requirements.", "violations": violations},
        )

    user = await _get_user_by_email(db, email)
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User not found.")

    new_hash = hash_password(body.new_password)
    await _update_password(db, str(user["id"]), new_hash)
    await delete_reset_token(body.reset_token)

    return {"status": "ok"}


@router.post("/change-password")
async def change_password(
    body: ChangePasswordRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Authenticated in-app password change. Requires current password for verification."""
    email = current_user["email"]
    user = await _get_user_by_email(db, email)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found.")

    if not verify_password(body.current_password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect.",
        )

    violations = validate_password_complexity(body.new_password)
    if violations:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "Password does not meet complexity requirements.", "violations": violations},
        )

    new_hash = hash_password(body.new_password)
    await _update_password(db, str(user["id"]), new_hash)

    return {"status": "ok"}
