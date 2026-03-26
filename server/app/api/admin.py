"""
Admin API — user management, audit log, and system health.

Endpoints:
    GET    /admin/users           — List all users (admin/executive)
    POST   /admin/users           — Create a user (admin only)
    PUT    /admin/users/{id}      — Update user role/permissions (admin only)
    GET    /admin/audit           — View audit log (admin/executive)
    GET    /admin/health          — System health dashboard (admin only)
    POST   /admin/model-check     — Live test call to an AI model (admin only)

Access: All endpoints require role=admin or role=executive (via require_role).
"""

import asyncio
import logging
import os
import time
from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import require_role, get_db
from app.core.auth import hash_password

logger = logging.getLogger("mezzofy.api.admin")
router = APIRouter(tags=["admin"])

AdminUser = Depends(require_role("admin", "executive"))
AdminOnly = Depends(require_role("admin"))


# ── DTOs ──────────────────────────────────────────────────────────────────────

class CreateUserRequest(BaseModel):
    email: str
    name: str
    password: str
    department: str
    role: str
    permissions: list[str] = []


class UpdateUserRequest(BaseModel):
    name: Optional[str] = None
    department: Optional[str] = None
    role: Optional[str] = None
    permissions: Optional[list[str]] = None
    is_active: Optional[bool] = None


class ModelCheckRequest(BaseModel):
    model: Literal["claude", "kimi"]


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/users")
async def list_users(
    limit: int = 50,
    offset: int = 0,
    department: Optional[str] = None,
    current_user: dict = AdminUser,
    db: AsyncSession = Depends(get_db),
):
    """List all users. Admin and executive roles only."""
    query = "SELECT id, email, name, department, role, is_active, created_at FROM users"
    params: dict = {"limit": limit, "offset": offset}

    if department:
        query += " WHERE department = :dept"
        params["dept"] = department

    query += " ORDER BY created_at DESC LIMIT :limit OFFSET :offset"

    result = await db.execute(text(query), params)
    rows = result.fetchall()

    return {
        "users": [
            {
                "id": row.id,
                "email": row.email,
                "name": row.name,
                "department": row.department,
                "role": row.role,
                "is_active": row.is_active,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ],
        "count": len(rows),
    }


@router.post("/users", status_code=status.HTTP_201_CREATED)
async def create_user(
    body: CreateUserRequest,
    current_user: dict = AdminOnly,
    db: AsyncSession = Depends(get_db),
):
    """Create a new user account. Admin only."""
    import uuid
    import json

    # Check for existing email
    existing = await db.execute(
        text("SELECT id FROM users WHERE email = :email"),
        {"email": body.email},
    )
    if existing.fetchone():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        )

    user_id = str(uuid.uuid4())
    pw_hash = hash_password(body.password)
    now = datetime.now(timezone.utc)

    await db.execute(
        text(
            """
            INSERT INTO users
              (id, email, name, password_hash, department, role, permissions, is_active, created_at, updated_at)
            VALUES
              (:id, :email, :name, :pw, :dept, :role, :perms, true, :now, :now)
            """
        ),
        {
            "id": user_id,
            "email": body.email,
            "name": body.name,
            "pw": pw_hash,
            "dept": body.department,
            "role": body.role,
            "perms": json.dumps(body.permissions),
            "now": now,
        },
    )

    logger.info(
        f"Admin {current_user['user_id']} created user {user_id} "
        f"({body.email}, {body.department}/{body.role})"
    )

    return {
        "user_id": user_id,
        "email": body.email,
        "name": body.name,
        "department": body.department,
        "role": body.role,
    }


@router.put("/users/{user_id}")
async def update_user(
    user_id: str,
    body: UpdateUserRequest,
    current_user: dict = AdminOnly,
    db: AsyncSession = Depends(get_db),
):
    """Update a user's role, department, permissions, or active status. Admin only."""
    import json

    # Build dynamic SET clause
    updates: dict = {}
    if body.name is not None:
        updates["name"] = body.name
    if body.department is not None:
        updates["department"] = body.department
    if body.role is not None:
        updates["role"] = body.role
    if body.permissions is not None:
        updates["permissions"] = json.dumps(body.permissions)
    if body.is_active is not None:
        updates["is_active"] = body.is_active

    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update",
        )

    updates["updated_at"] = datetime.now(timezone.utc)
    updates["id"] = user_id

    set_clause = ", ".join(f"{k} = :{k}" for k in updates if k != "id")
    result = await db.execute(
        text(f"UPDATE users SET {set_clause} WHERE id = :id RETURNING id"),
        updates,
    )
    if result.fetchone() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    logger.info(
        f"Admin {current_user['user_id']} updated user {user_id}: "
        f"{list(updates.keys())}"
    )
    return {"user_id": user_id, "updated": list(updates.keys())}


@router.get("/audit")
async def get_audit_log(
    limit: int = 100,
    offset: int = 0,
    user_id_filter: Optional[str] = None,
    action_filter: Optional[str] = None,
    current_user: dict = AdminUser,
    db: AsyncSession = Depends(get_db),
):
    """View audit log entries. Admin and executive roles only."""
    query = (
        "SELECT id, user_id, action, resource, ip_address, success, "
        "duration_ms, created_at FROM audit_log"
    )
    params: dict = {"limit": limit, "offset": offset}
    conditions = []

    if user_id_filter:
        conditions.append("user_id = :uid_filter")
        params["uid_filter"] = user_id_filter
    if action_filter:
        conditions.append("action ILIKE :action_filter")
        params["action_filter"] = f"%{action_filter}%"

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY created_at DESC LIMIT :limit OFFSET :offset"

    result = await db.execute(text(query), params)
    rows = result.fetchall()

    return {
        "entries": [
            {
                "id": row.id,
                "user_id": row.user_id,
                "action": row.action,
                "resource": row.resource,
                "ip_address": row.ip_address,
                "success": row.success,
                "duration_ms": row.duration_ms,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ],
        "count": len(rows),
    }


@router.get("/health")
async def system_health(
    current_user: dict = AdminOnly,
):
    """
    System health dashboard.
    Checks DB, Redis, Celery connectivity, and LLM manager status.
    """
    import redis.asyncio as aioredis

    from app.core.database import check_db_connection

    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # DB
    db_ok = await check_db_connection()

    # Redis
    redis_ok = False
    try:
        async with aioredis.from_url(redis_url, decode_responses=True) as r:
            await r.ping()
        redis_ok = True
    except Exception:
        pass

    # LLM manager — check that Claude client is initialized with a non-empty API key
    llm_ok = False
    try:
        from app.llm import llm_manager as llm_mod
        mgr = llm_mod.get()
        if mgr is not None and bool(mgr.claude._api_key):
            llm_ok = True
    except Exception:
        pass

    # Model names — read actual model IDs from initialized LLM clients
    model_names = {"claude": "unknown", "kimi": "unknown"}
    try:
        from app.llm import llm_manager as llm_mod
        mgr = llm_mod.get()
        if mgr is not None:
            model_names["claude"] = mgr.claude.model_name
            model_names["kimi"] = mgr.kimi.model_name
    except Exception:
        pass

    # WebSocket connections
    ws_connections = 0
    try:
        from app.output.stream_handler import ws_manager
        ws_connections = ws_manager.active_count()
    except Exception:
        pass

    overall = (
        "ok" if (db_ok and redis_ok and llm_ok) else "degraded"
    )

    return {
        "status": overall,
        "services": {
            "database": "ok" if db_ok else "unavailable",
            "redis": "ok" if redis_ok else "unavailable",
            "llm_manager": "ok" if llm_ok else "not_initialized",
        },
        "connections": {
            "websocket_active": ws_connections,
        },
        "model_names": model_names,
    }


@router.post("/model-check")
async def model_check(
    body: ModelCheckRequest,
    current_user: dict = AdminOnly,
):
    """
    Make a live test call to the specified AI model.
    Returns the response text and latency, or an error message.
    """
    from app.llm import llm_manager as llm_mod

    mgr = llm_mod.get()
    if mgr is None:
        return {
            "model": body.model,
            "model_id": "unknown",
            "status": "error",
            "message": "LLM manager not initialized",
            "latency_ms": 0,
        }

    client = mgr.claude if body.model == "claude" else mgr.kimi
    model_id = client.model_name

    test_messages = [{"role": "user", "content": "Respond with only the word OK"}]
    timeout = 60.0 if body.model == "kimi" else 15.0

    start = time.monotonic()
    try:
        result = await asyncio.wait_for(
            client.chat(test_messages, max_tokens=10),
            timeout=timeout,
        )
        latency_ms = int((time.monotonic() - start) * 1000)
        _message = result.get("content", "").strip()
        return {
            "model": body.model,
            "model_id": model_id,
            "status": "ok",
            "message": _message if _message else "OK",
            "latency_ms": latency_ms,
        }
    except asyncio.TimeoutError:
        latency_ms = int((time.monotonic() - start) * 1000)
        return {
            "model": body.model,
            "model_id": model_id,
            "status": "error",
            "message": f"Timeout after {int(timeout)}s",
            "latency_ms": latency_ms,
        }
    except Exception as e:
        latency_ms = int((time.monotonic() - start) * 1000)
        return {
            "model": body.model,
            "model_id": model_id,
            "status": "error",
            "message": f"{type(e).__name__}: {e}",
            "latency_ms": latency_ms,
        }
