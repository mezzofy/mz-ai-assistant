"""
Rate Limiter — Redis sliding window rate limiting for FastAPI.

Limits:
  - General endpoints:  30 req/min per authenticated user ID
  - Auth endpoints:     10 req/min per client IP (prevents brute-force)

Usage:
    # In endpoint — raises 429 if over limit
    await check_rate_limit(request, user_id="user-uuid")
    await check_auth_rate_limit(request)

    # As FastAPI dependency (raises 429 automatically)
    @router.post("/send", dependencies=[Depends(rate_limit_user)])
    async def send_message(...):
        ...
"""

import os
import uuid
from datetime import datetime, timezone

import redis.asyncio as aioredis
from fastapi import Depends, HTTPException, Request, status

# ── Config ────────────────────────────────────────────────────────────────────

_REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Limits (per sliding window)
USER_LIMIT = 30       # requests per minute per authenticated user
AUTH_LIMIT = 10       # requests per minute per IP (auth endpoints only)
WINDOW_SECONDS = 60   # sliding window duration


# ── Redis client ──────────────────────────────────────────────────────────────

def _get_redis():
    return aioredis.from_url(_REDIS_URL, decode_responses=True)


# ── Sliding window algorithm ──────────────────────────────────────────────────

async def _check_limit(key: str, limit: int, window: int = WINDOW_SECONDS) -> tuple[bool, int]:
    """
    Redis sliding window rate limiter.

    Uses a sorted set with request timestamps as scores.
    Returns (is_allowed, current_count).
    """
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    window_start_ms = now_ms - (window * 1000)

    async with _get_redis() as r:
        pipe = r.pipeline()
        # Remove expired entries outside window
        pipe.zremrangebyscore(key, "-inf", window_start_ms)
        # Count current requests in window
        pipe.zcard(key)
        # Add current request with unique member to prevent collision when
        # multiple requests arrive within the same millisecond
        pipe.zadd(key, {f"{now_ms}:{uuid.uuid4().hex[:8]}": now_ms})
        # Set expiry on the key (auto-cleanup)
        pipe.expire(key, window + 1)
        results = await pipe.execute()

    current_count = results[1]  # count before adding current request
    is_allowed = current_count < limit
    return is_allowed, current_count


# ── Public rate limit checks ──────────────────────────────────────────────────

async def check_rate_limit(request: Request, user_id: str) -> None:
    """
    Check per-user rate limit (30 req/min).
    Raises HTTP 429 if exceeded.
    Call this in endpoints that have an authenticated user.
    """
    key = f"rl:user:{user_id}"
    allowed, count = await _check_limit(key, USER_LIMIT)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Max {USER_LIMIT} requests per minute.",
            headers={"Retry-After": str(WINDOW_SECONDS)},
        )


async def check_auth_rate_limit(request: Request) -> None:
    """
    Check per-IP rate limit for auth endpoints (10 req/min).
    Raises HTTP 429 if exceeded.
    Prevents brute-force password attacks.
    """
    client_ip = _get_client_ip(request)
    key = f"rl:ip:{client_ip}"
    allowed, count = await _check_limit(key, AUTH_LIMIT)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many authentication attempts. Max {AUTH_LIMIT} per minute.",
            headers={"Retry-After": str(WINDOW_SECONDS)},
        )


# ── FastAPI Dependency wrappers ───────────────────────────────────────────────

async def rate_limit_auth(request: Request) -> None:
    """Dependency: IP-based rate limit for auth endpoints."""
    await check_auth_rate_limit(request)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_client_ip(request: Request) -> str:
    """
    Extract real client IP, respecting X-Forwarded-For from nginx proxy.
    Falls back to direct connection IP.
    """
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # X-Forwarded-For can be comma-separated: "client, proxy1, proxy2"
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
