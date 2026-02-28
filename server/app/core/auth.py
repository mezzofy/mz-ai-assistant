"""
JWT Authentication — token creation, validation, and refresh token blacklisting.

Token spec (from SECURITY.md + CONFIG.md):
  - Access token:  HS256, 60-minute expiry
  - Refresh token: HS256, 7-day expiry
  - Payload: user_id, email, name, department, role, permissions, exp, iat
  - Refresh tokens are blacklisted in Redis on logout
"""

import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
import redis.asyncio as aioredis

# ── Config ───────────────────────────────────────────────────────────────────

def _get_config():
    """Load auth config from environment variables."""
    return {
        "secret": os.getenv("JWT_SECRET", "INSECURE_DEFAULT_CHANGE_ME"),
        "algorithm": "HS256",
        "access_expire_minutes": int(os.getenv("JWT_ACCESS_EXPIRE_MINUTES", "60")),
        "refresh_expire_days": int(os.getenv("JWT_REFRESH_EXPIRE_DAYS", "7")),
        "redis_url": os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    }


CONFIG = _get_config()

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ── Password utilities ────────────────────────────────────────────────────────

def hash_password(plain_password: str) -> str:
    """Hash a plaintext password."""
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


# ── Token creation ────────────────────────────────────────────────────────────

def _build_payload(user: dict, token_type: str, expire_delta: timedelta) -> dict:
    """Build JWT payload from user data."""
    now = datetime.now(timezone.utc)
    uid = user.get("id") or user.get("user_id")  # DB row has "id"; decoded JWT has "user_id"
    return {
        "sub": str(uid),
        "user_id": str(uid),
        "email": user["email"],
        "name": user.get("name", ""),
        "department": user["department"],
        "role": user["role"],
        "permissions": user.get("permissions", []),
        "token_type": token_type,
        "jti": str(uuid.uuid4()),  # Unique token ID for blacklisting
        "iat": int(now.timestamp()),
        "exp": int((now + expire_delta).timestamp()),
    }


def create_access_token(user: dict) -> str:
    """Create a short-lived access token (60 minutes)."""
    payload = _build_payload(
        user,
        token_type="access",
        expire_delta=timedelta(minutes=CONFIG["access_expire_minutes"]),
    )
    return jwt.encode(payload, CONFIG["secret"], algorithm=CONFIG["algorithm"])


def create_refresh_token(user: dict) -> str:
    """Create a long-lived refresh token (7 days)."""
    payload = _build_payload(
        user,
        token_type="refresh",
        expire_delta=timedelta(days=CONFIG["refresh_expire_days"]),
    )
    return jwt.encode(payload, CONFIG["secret"], algorithm=CONFIG["algorithm"])


# ── Token validation ──────────────────────────────────────────────────────────

def decode_token(token: str) -> dict:
    """
    Decode and validate a JWT token.
    Returns the payload dict on success.
    Raises JWTError on invalid/expired tokens.
    """
    return jwt.decode(token, CONFIG["secret"], algorithms=[CONFIG["algorithm"]])


def decode_access_token(token: str) -> dict:
    """Decode and validate an access token. Raises ValueError if token_type is wrong."""
    payload = decode_token(token)
    if payload.get("token_type") != "access":
        raise ValueError("Not an access token")
    return payload


def decode_refresh_token(token: str) -> dict:
    """Decode and validate a refresh token. Raises ValueError if token_type is wrong."""
    payload = decode_token(token)
    if payload.get("token_type") != "refresh":
        raise ValueError("Not a refresh token")
    return payload


# ── Refresh token blacklist (Redis) ───────────────────────────────────────────

def _get_redis_client():
    return aioredis.from_url(CONFIG["redis_url"], decode_responses=True)


async def blacklist_refresh_token(jti: str, expires_in_seconds: int) -> None:
    """Add a refresh token JTI to the Redis blacklist."""
    async with _get_redis_client() as r:
        await r.setex(f"bl:rt:{jti}", expires_in_seconds, "1")


async def is_refresh_token_blacklisted(jti: str) -> bool:
    """Check if a refresh token JTI has been blacklisted."""
    async with _get_redis_client() as r:
        result = await r.get(f"bl:rt:{jti}")
        return result is not None


async def blacklist_all_user_tokens(user_id: str) -> None:
    """
    Mark all tokens for a user as invalidated via a version counter.
    On next request, tokens with an older version are rejected.
    """
    async with _get_redis_client() as r:
        await r.incr(f"token_version:{user_id}")
