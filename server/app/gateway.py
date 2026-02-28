"""
Gateway Middleware — runs on every /chat/* request.

Responsibilities (in order):
    1. Extract JWT from Authorization: Bearer header
    2. Validate token (decode + type check)
    3. Check rate limit (30 req/min per user via Redis)
    4. Write audit log entry (non-blocking)
    5. Attach decoded user payload to request.state.user

This middleware does NOT run on /auth/*, /health, /docs, /webhooks/*.
WebSocket connections at /chat/ws bypass this middleware and handle
JWT validation inside the WebSocket handler directly.

Usage:
    In main.py:
        from app.gateway import ChatGatewayMiddleware
        app.add_middleware(ChatGatewayMiddleware)

    In chat endpoints (user already attached):
        user = request.state.user  # full JWT payload dict
"""

import logging
import time

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from jose import JWTError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.core.auth import decode_access_token
from app.core.rate_limiter import check_rate_limit
from app.core.database import AsyncSessionLocal
from app.core.audit import log_action

logger = logging.getLogger("mezzofy.gateway")

# Paths that bypass JWT validation in this middleware.
# Any path matching one of these prefixes is forwarded without auth checks.
_BYPASS_PREFIXES = (
    "/auth/",        # Auth endpoints handle their own IP rate limiting
    "/health",       # Unauthenticated health check
    "/docs",         # Swagger UI (served by FastAPI)
    "/redoc",        # ReDoc (served by FastAPI)
    "/openapi.json", # OpenAPI schema
    "/webhooks/",    # Webhooks use HMAC-SHA256 instead of JWT
    "/scheduler/",   # Scheduler routes use get_current_user dependency directly
    "/files/",       # Files routes use get_current_user dependency directly
    "/admin/",       # Admin routes use require_role dependency directly
    "/chat/ws",      # WebSocket handles JWT auth inside the connection handler
)


class ChatGatewayMiddleware(BaseHTTPMiddleware):
    """
    ASGI middleware providing centralized JWT validation + rate limiting for /chat/* REST endpoints.

    Attaches request.state.user on success.
    Returns JSON 401/429 on failure (never raises unhandled exceptions).

    Note: /scheduler/, /files/, /admin/ are in bypass list because they use
    FastAPI Depends(get_current_user) directly. Only /chat/* benefits from
    middleware-level auth (avoids duplicate token decoding per request).
    """

    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path

        # Pass through any bypassed path without JWT validation
        if any(path.startswith(prefix) for prefix in _BYPASS_PREFIXES) or path == "/health":
            return await call_next(request)

        # Only apply full JWT + rate limit to /chat/* REST endpoints
        if not path.startswith("/chat/"):
            return await call_next(request)

        start_time = time.monotonic()

        # ── Step 1: Extract token ────────────────────────────────────────────
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return _json_401("Missing or malformed Authorization header")

        token = auth_header[len("Bearer "):]

        # ── Step 2: Validate token ───────────────────────────────────────────
        try:
            payload = decode_access_token(token)
        except (JWTError, ValueError) as e:
            return _json_401("Invalid or expired access token")

        user_id = payload.get("user_id")
        if not user_id:
            return _json_401("Token payload missing user_id")

        # ── Step 3: Rate limit ───────────────────────────────────────────────
        try:
            await check_rate_limit(request, user_id=user_id)
        except Exception as exc:
            # check_rate_limit raises HTTPException for 429 — re-wrap as JSONResponse
            if hasattr(exc, "status_code") and exc.status_code == 429:
                return JSONResponse(
                    status_code=429,
                    content={"detail": exc.detail},
                    headers={"Retry-After": "60"},
                )
            # Other errors (e.g. Redis down) — allow through with a warning
            logger.warning(f"Rate limit check failed: {exc} — allowing request")

        # ── Step 4: Attach user to request state ─────────────────────────────
        request.state.user = payload

        # ── Step 5: Forward to endpoint ──────────────────────────────────────
        response = await call_next(request)

        # ── Step 6: Audit log (non-blocking, best-effort) ────────────────────
        duration_ms = int((time.monotonic() - start_time) * 1000)
        try:
            async with AsyncSessionLocal() as db:
                await log_action(
                    db=db,
                    user_id=user_id,
                    action=f"http_{request.method.lower()}",
                    resource=path,
                    ip=_get_ip(request),
                    user_agent=request.headers.get("User-Agent"),
                    success=response.status_code < 400,
                    duration_ms=duration_ms,
                    session_id=request.headers.get("X-Session-ID"),
                )
        except Exception as e:
            logger.debug(f"Audit log failed (non-fatal): {e}")

        return response


# ── Helpers ───────────────────────────────────────────────────────────────────

def _json_401(detail: str) -> JSONResponse:
    return JSONResponse(
        status_code=401,
        content={"detail": detail},
        headers={"WWW-Authenticate": "Bearer"},
    )


def _get_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
