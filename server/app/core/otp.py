"""
OTP (One-Time Password) — Redis-based OTP storage and account lockout for auth flows.

Key schema:
  login_otp:{otp_token}         300s  — Binds OTP code to temp UUID token
  otp_attempts:{email}          1800s — Failed OTP attempt counter
  account_locked:{email}        1800s — 30-min lock signal
  otp_resend_cooldown:{email}   60s   — Prevents resend spam
  reset_otp:{email}             300s  — Password reset OTP
  reset_token:{uuid}            600s  — Maps reset token → email

Usage:
    from app.core.otp import generate_otp_code, store_login_otp, ...
"""

import json
import os
import secrets

import redis.asyncio as aioredis

_REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")


def _get_redis():
    return aioredis.from_url(_REDIS_URL, decode_responses=True)


# ── Code generation ───────────────────────────────────────────────────────────

def generate_otp_code() -> str:
    """Generate a cryptographically secure 6-digit OTP code."""
    return str(secrets.randbelow(10 ** 6)).zfill(6)


# ── Login OTP (keyed by otp_token UUID) ──────────────────────────────────────

async def store_login_otp(email: str, otp_token: str, code: str) -> None:
    """Store OTP for login flow. TTL 300s (5 minutes)."""
    payload = json.dumps({"email": email, "code": code})
    async with _get_redis() as r:
        await r.setex(f"login_otp:{otp_token}", 300, payload)


async def get_login_otp(otp_token: str) -> dict | None:
    """Retrieve login OTP data by token. Returns None if expired/not found."""
    async with _get_redis() as r:
        raw = await r.get(f"login_otp:{otp_token}")
    if raw is None:
        return None
    return json.loads(raw)


async def delete_login_otp(otp_token: str) -> None:
    """Delete login OTP after successful verification."""
    async with _get_redis() as r:
        await r.delete(f"login_otp:{otp_token}")


# ── OTP attempt tracking and account lockout ──────────────────────────────────

async def increment_otp_attempts(email: str) -> int:
    """Increment failed OTP attempt counter. Sets 30-min TTL on first increment."""
    key = f"otp_attempts:{email}"
    async with _get_redis() as r:
        count = await r.incr(key)
        if count == 1:
            await r.expire(key, 1800)
        return count


async def is_account_locked(email: str) -> bool:
    """Return True if the account is under a temporary OTP lockout."""
    async with _get_redis() as r:
        result = await r.exists(f"account_locked:{email}")
        return result > 0


async def lock_account(email: str) -> None:
    """Lock account for 30 minutes after 3 failed OTP attempts."""
    async with _get_redis() as r:
        await r.setex(f"account_locked:{email}", 1800, "1")


async def reset_otp_attempts(email: str) -> None:
    """Clear failed attempt counter after successful OTP verification."""
    async with _get_redis() as r:
        await r.delete(f"otp_attempts:{email}")


# ── Resend cooldown ───────────────────────────────────────────────────────────

async def can_resend_otp(email: str) -> bool:
    """Return True if the resend cooldown has elapsed (60s between resends)."""
    async with _get_redis() as r:
        result = await r.exists(f"otp_resend_cooldown:{email}")
        return result == 0


async def set_resend_cooldown(email: str) -> None:
    """Start 60-second resend cooldown."""
    async with _get_redis() as r:
        await r.setex(f"otp_resend_cooldown:{email}", 60, "1")


# ── Password reset OTP (keyed by email) ──────────────────────────────────────

async def store_reset_otp(email: str, code: str) -> None:
    """Store password reset OTP. TTL 300s (5 minutes)."""
    payload = json.dumps({"code": code})
    async with _get_redis() as r:
        await r.setex(f"reset_otp:{email}", 300, payload)


async def get_reset_otp(email: str) -> dict | None:
    """Retrieve reset OTP data by email. Returns None if expired/not found."""
    async with _get_redis() as r:
        raw = await r.get(f"reset_otp:{email}")
    if raw is None:
        return None
    return json.loads(raw)


async def delete_reset_otp(email: str) -> None:
    """Delete reset OTP after code is verified."""
    async with _get_redis() as r:
        await r.delete(f"reset_otp:{email}")


# ── Password reset token (keyed by UUID) ─────────────────────────────────────

async def store_reset_token(reset_token: str, email: str) -> None:
    """Store mapping of reset token → email. TTL 600s (10 minutes)."""
    async with _get_redis() as r:
        await r.setex(f"reset_token:{reset_token}", 600, email)


async def get_reset_token_email(reset_token: str) -> str | None:
    """Retrieve email associated with a reset token. Returns None if expired."""
    async with _get_redis() as r:
        return await r.get(f"reset_token:{reset_token}")


async def delete_reset_token(reset_token: str) -> None:
    """Delete reset token after password has been changed."""
    async with _get_redis() as r:
        await r.delete(f"reset_token:{reset_token}")
