"""
Tasks API — per-user background task management.

Endpoints:
    GET    /tasks/             — List current user's tasks (optional ?status= filter)
    GET    /tasks/active       — Return only queued + running tasks
    GET    /tasks/{id}         — Task detail (404 if not owned by current user)
    POST   /tasks/{id}/cancel  — Cancel task (revoke Celery task if still queued)
    POST   /tasks/{id}/retry   — Retry a failed task (re-enqueue as new Celery task)
    PATCH  /tasks/{id}/notify  — Toggle notify_on_done boolean

Auth: JWT via Depends(get_current_user) — all endpoints require authentication.
Scoping: Every query includes user_id filter. Returns 404 for all ownership mismatches.
"""

import json
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db

logger = logging.getLogger("mezzofy.api.tasks")
router = APIRouter(tags=["tasks"])


# ── Request models ─────────────────────────────────────────────────────────────

class NotifyRequest(BaseModel):
    notify_on_done: bool


# ── GET /tasks/ ───────────────────────────────────────────────────────────────

@router.get("/")
async def list_tasks(
    status: Optional[str] = Query(None, description="Filter by status: queued, running, completed, failed, cancelled"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all tasks belonging to the current user, newest first."""
    valid_statuses = {"queued", "running", "completed", "failed", "cancelled"}
    if status and status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Must be one of: {', '.join(sorted(valid_statuses))}",
        )

    if status:
        result = await db.execute(
            text(
                "SELECT id, task_ref, session_id, department, content, status, "
                "progress, current_step, error, notify_on_done, queue_name, "
                "started_at, completed_at, created_at "
                "FROM agent_tasks "
                "WHERE user_id = :uid AND status = :status "
                "ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
            ),
            {"uid": user["user_id"], "status": status, "limit": limit, "offset": offset},
        )
    else:
        result = await db.execute(
            text(
                "SELECT id, task_ref, session_id, department, content, status, "
                "progress, current_step, error, notify_on_done, queue_name, "
                "started_at, completed_at, created_at "
                "FROM agent_tasks "
                "WHERE user_id = :uid "
                "ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
            ),
            {"uid": user["user_id"], "limit": limit, "offset": offset},
        )

    rows = result.fetchall()
    return {"tasks": [_row_to_dict(r) for r in rows], "total": len(rows)}


# ── GET /tasks/active ─────────────────────────────────────────────────────────

@router.get("/active")
async def list_active_tasks(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return queued/running tasks plus tasks completed or failed in the last 5 minutes."""
    result = await db.execute(
        text(
            "SELECT id, task_ref, session_id, department, content, status, "
            "progress, current_step, result, error, notify_on_done, queue_name, "
            "started_at, completed_at, created_at "
            "FROM agent_tasks "
            "WHERE user_id = :uid "
            "  AND ("
            "    status IN ('queued', 'running')"
            "    OR (status IN ('completed', 'failed') AND completed_at > NOW() - INTERVAL '5 minutes')"
            "  ) "
            "ORDER BY created_at DESC"
        ),
        {"uid": user["user_id"]},
    )
    rows = result.fetchall()
    return {"tasks": [_row_to_dict(r, include_result=True) for r in rows], "total": len(rows)}


# ── GET /tasks/{task_id} ──────────────────────────────────────────────────────

@router.get("/{task_id}")
async def get_task(
    task_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get full detail for a single task. Returns 404 if not owned by current user."""
    result = await db.execute(
        text(
            "SELECT id, task_ref, session_id, department, content, plan, status, "
            "progress, current_step, result, error, notify_on_done, queue_name, "
            "started_at, completed_at, created_at "
            "FROM agent_tasks "
            "WHERE id = :id AND user_id = :uid"
        ),
        {"id": task_id, "uid": user["user_id"]},
    )
    row = result.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return _row_to_dict(row, include_result=True)


# ── POST /tasks/{task_id}/cancel ──────────────────────────────────────────────

@router.post("/{task_id}/cancel")
async def cancel_task(
    task_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Cancel a task. Attempts to revoke the Celery task; always marks DB as cancelled.
    Returns 404 if task is not owned by the current user.
    """
    result = await db.execute(
        text(
            "SELECT id, task_ref, status FROM agent_tasks "
            "WHERE id = :id AND user_id = :uid"
        ),
        {"id": task_id, "uid": user["user_id"]},
    )
    row = result.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Task not found")

    if row.status in ("completed", "failed", "cancelled"):
        return {"id": task_id, "status": row.status, "cancelled": False,
                "detail": f"Task already in terminal state: {row.status}"}

    # Attempt Celery revoke (best-effort — may fail if task already started)
    revoke_ok = False
    try:
        from app.tasks.celery_app import celery_app
        celery_app.control.revoke(row.task_ref, terminate=True)
        revoke_ok = True
        logger.info(f"cancel_task: revoked Celery task {row.task_ref!r} for task_id={task_id}")
    except Exception as e:
        logger.warning(f"cancel_task: revoke failed for task_ref={row.task_ref!r}: {e}")

    # Always mark as cancelled in DB regardless of revoke result
    await db.execute(
        text(
            "UPDATE agent_tasks SET status = 'cancelled', completed_at = NOW() "
            "WHERE id = :id AND user_id = :uid"
        ),
        {"id": task_id, "uid": user["user_id"]},
    )
    await db.commit()

    return {"id": task_id, "status": "cancelled", "cancelled": True, "celery_revoked": revoke_ok}


# ── POST /tasks/{task_id}/retry ───────────────────────────────────────────────

@router.post("/{task_id}/retry")
async def retry_task(
    task_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Retry a failed task by creating a new queued task and dispatching it.
    Returns 404 if task is not owned by the current user.
    Only tasks in 'failed' or 'cancelled' state can be retried.
    """
    result = await db.execute(
        text(
            "SELECT id, task_ref, session_id, department, content, status, queue_name "
            "FROM agent_tasks "
            "WHERE id = :id AND user_id = :uid"
        ),
        {"id": task_id, "uid": user["user_id"]},
    )
    row = result.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Task not found")

    if row.status not in ("failed", "cancelled"):
        raise HTTPException(
            status_code=400,
            detail=f"Only failed or cancelled tasks can be retried. Current status: {row.status}",
        )

    # Build task data for re-dispatch
    task_data = {
        "message": row.content,
        "user_id": user["user_id"],
        "department": row.department or user.get("department", ""),
        "session_id": row.session_id,
        "source": "mobile",
        "input_type": "text",
        "permissions": user.get("permissions", []),
        "attachments": [],
        "conversation_history": [],
    }

    # Dispatch new Celery task
    from app.tasks.tasks import process_agent_task
    new_celery_task = process_agent_task.apply_async(
        kwargs={"task_data": task_data},
        queue=row.queue_name or "default",
    )
    new_task_ref = new_celery_task.id

    # Insert new agent_tasks row with status='queued'
    new_task_id = str(uuid.uuid4())
    task_data["agent_task_id"] = new_task_id
    new_celery_task.kwargs["task_data"]["agent_task_id"] = new_task_id  # update ref

    await db.execute(
        text(
            "INSERT INTO agent_tasks "
            "(id, task_ref, user_id, session_id, department, content, status, queue_name) "
            "VALUES (:id, :task_ref, :user_id, :session_id, :department, :content, 'queued', :queue_name)"
        ),
        {
            "id": new_task_id,
            "task_ref": new_task_ref,
            "user_id": user["user_id"],
            "session_id": row.session_id,
            "department": row.department,
            "content": row.content,
            "queue_name": row.queue_name or "default",
        },
    )
    await db.commit()

    logger.info(
        f"retry_task: created new task_id={new_task_id} celery_ref={new_task_ref!r} "
        f"from original task_id={task_id}"
    )

    return {
        "original_task_id": task_id,
        "new_task_id": new_task_id,
        "new_task_ref": new_task_ref,
        "status": "queued",
    }


# ── PATCH /tasks/{task_id}/notify ─────────────────────────────────────────────

@router.patch("/{task_id}/notify")
async def update_notify(
    task_id: str,
    body: NotifyRequest,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Toggle the notify_on_done flag for a task. Returns 404 if not owned by current user."""
    result = await db.execute(
        text(
            "UPDATE agent_tasks SET notify_on_done = :notify "
            "WHERE id = :id AND user_id = :uid "
            "RETURNING id, notify_on_done"
        ),
        {"notify": body.notify_on_done, "id": task_id, "uid": user["user_id"]},
    )
    row = result.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Task not found")
    await db.commit()
    return {"id": task_id, "notify_on_done": row.notify_on_done}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _row_to_dict(row, include_result: bool = False) -> dict:
    """Convert a SQLAlchemy Row to a JSON-serialisable dict."""
    d = {
        "id": str(row.id),
        "task_ref": row.task_ref,
        "session_id": row.session_id,
        "department": row.department,
        "content": row.content,
        "status": row.status,
        "progress": row.progress,
        "current_step": row.current_step,
        "error": row.error,
        "notify_on_done": row.notify_on_done,
        "queue_name": row.queue_name,
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "completed_at": row.completed_at.isoformat() if row.completed_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }
    if include_result:
        # plan and result are JSONB — already dicts from SQLAlchemy
        d["plan"] = row.plan if hasattr(row, "plan") else []
        d["result"] = row.result if hasattr(row, "result") else None
    return d
