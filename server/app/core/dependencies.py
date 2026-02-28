"""
FastAPI Dependencies — reusable Depends() functions for auth, DB, and RBAC.

Usage:
    @router.get("/protected")
    async def endpoint(
        current_user: dict = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ):
        ...

    @router.get("/admin-only")
    async def admin_endpoint(
        current_user: dict = Depends(require_role("admin", "executive")),
    ):
        ...
"""

from typing import Annotated
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from jose import JWTError

from app.core.database import get_db
from app.core.auth import decode_access_token, is_refresh_token_blacklisted
from app.core.rbac import has_permission, has_any_permission

# Re-export get_db so other modules only import from dependencies
__all__ = ["get_db", "get_current_user", "require_role", "require_permission"]

# HTTP Bearer token extractor
bearer_scheme = HTTPBearer(auto_error=False)

_CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)

_INACTIVE_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="User account is inactive",
)

_FORBIDDEN_EXCEPTION = HTTPException(
    status_code=status.HTTP_403_FORBIDDEN,
    detail="Insufficient permissions for this action",
)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    """
    Extract and validate the JWT access token from the Authorization header.
    Returns the decoded token payload as a dict on success.
    Raises HTTP 401 on missing, expired, or invalid tokens.
    """
    if not credentials or not credentials.credentials:
        raise _CREDENTIALS_EXCEPTION

    token = credentials.credentials
    try:
        payload = decode_access_token(token)
    except (JWTError, ValueError):
        raise _CREDENTIALS_EXCEPTION

    if not payload.get("user_id"):
        raise _CREDENTIALS_EXCEPTION

    return payload


def require_role(*allowed_roles: str):
    """
    Dependency factory: restrict endpoint to users with one of the given roles.

    Usage:
        @router.get("/admin")
        async def admin_only(user=Depends(require_role("admin", "executive"))):
            ...
    """
    async def _check_role(
        current_user: dict = Depends(get_current_user),
    ) -> dict:
        user_role = current_user.get("role", "")
        if user_role not in allowed_roles and "*" not in current_user.get("permissions", []):
            raise _FORBIDDEN_EXCEPTION
        return current_user

    return _check_role


def require_permission(*required_permissions: str):
    """
    Dependency factory: restrict endpoint to users who have at least one
    of the required permissions.

    Usage:
        @router.post("/leads")
        async def create_lead(user=Depends(require_permission("sales_write"))):
            ...
    """
    async def _check_permission(
        current_user: dict = Depends(get_current_user),
    ) -> dict:
        user_permissions = current_user.get("permissions", [])
        if "*" in user_permissions:
            return current_user  # admin bypasses all permission checks
        if not any(p in user_permissions for p in required_permissions):
            raise _FORBIDDEN_EXCEPTION
        return current_user

    return _check_permission


# Typed aliases for cleaner endpoint signatures
CurrentUser = Annotated[dict, Depends(get_current_user)]
DBSession = Annotated[AsyncSession, Depends(get_db)]
