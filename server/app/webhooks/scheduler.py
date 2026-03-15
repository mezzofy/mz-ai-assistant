"""
Scheduler API — user-managed recurring job CRUD.

Endpoints:
    GET    /scheduler/jobs           — List the current user's scheduled jobs
    POST   /scheduler/jobs           — Create a new scheduled job
    GET    /scheduler/jobs/{id}      — Get job details
    PUT    /scheduler/jobs/{id}      — Update a scheduled job
    DELETE /scheduler/jobs/{id}      — Delete a scheduled job (owner or admin)
    POST   /scheduler/jobs/{id}/run  — Manually trigger a job immediately

Constraints:
    - Max 10 active jobs per user
    - Minimum schedule interval: 15 minutes
    - Only job owner or admin can update/delete
    - Cron expressions: 5-field standard format (minute hour dom month dow)

Jobs are stored in the `scheduled_jobs` PostgreSQL table and picked up by
Celery Beat at startup via app.tasks.beat_schedule.DatabaseScheduler.
"""

import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db

logger = logging.getLogger("mezzofy.api.scheduler")
router = APIRouter(tags=["scheduler"])

# Limits
_MAX_JOBS_PER_USER = 10
_MIN_INTERVAL_MINUTES = 15

# Valid agent names
_VALID_AGENTS = {"sales", "marketing", "finance", "support", "management"}


# ── DTOs ──────────────────────────────────────────────────────────────────────

class ScheduleDTO(BaseModel):
    """Schedule specification for a job."""
    type: str  # "cron" | "interval"
    cron: Optional[str] = None           # "0 9 * * 1" — required when type=cron
    interval_minutes: Optional[int] = None  # required when type=interval

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        if v not in ("cron", "interval"):
            raise ValueError("schedule.type must be 'cron' or 'interval'")
        return v


class DeliverToDTO(BaseModel):
    """Delivery targets for job results."""
    teams_channel: Optional[str] = None
    email: Optional[list[str]] = None
    push_user_id: Optional[str] = None


class CreateJobRequest(BaseModel):
    name: str
    description: Optional[str] = None
    agent: str
    message: str
    workflow_name: Optional[str] = None   # Human-readable label shown in mobile card
    schedule: ScheduleDTO
    deliver_to: DeliverToDTO = DeliverToDTO()

    @field_validator("agent")
    @classmethod
    def validate_agent(cls, v: str) -> str:
        if v not in _VALID_AGENTS:
            raise ValueError(f"agent must be one of: {', '.join(sorted(_VALID_AGENTS))}")
        return v

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if not v or len(v) > 100:
            raise ValueError("name must be 1–100 characters")
        return v

    @field_validator("message")
    @classmethod
    def validate_message(cls, v: str) -> str:
        v = v.strip()
        if not v or len(v) > 2000:
            raise ValueError("message must be 1–2000 characters")
        return v


class UpdateJobRequest(BaseModel):
    name: Optional[str] = None
    message: Optional[str] = None
    workflow_name: Optional[str] = None
    schedule: Optional[ScheduleDTO] = None
    deliver_to: Optional[DeliverToDTO] = None
    is_active: Optional[bool] = None


# ── Cron next-run helper ──────────────────────────────────────────────────────

def compute_next_run(cron_expr: str) -> datetime:
    """
    Compute the next UTC run time for a 5-field cron expression.

    Uses croniter (standard library for cron iteration).
    Returns a timezone-aware UTC datetime strictly after now.
    """
    from croniter import croniter as _croniter
    base = datetime.now(timezone.utc)
    return _croniter(cron_expr, base).get_next(datetime).replace(tzinfo=timezone.utc)


# ── Validation helpers ────────────────────────────────────────────────────────

def _schedule_dto_to_cron(schedule: ScheduleDTO) -> str:
    """
    Convert a ScheduleDTO to a 5-field cron expression string.
    Validates minimum 15-minute interval.
    """
    if schedule.type == "cron":
        cron_expr = schedule.cron or ""
        _validate_cron_expression(cron_expr)
        return cron_expr

    if schedule.type == "interval":
        minutes = schedule.interval_minutes
        if minutes is None or minutes < _MIN_INTERVAL_MINUTES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Minimum interval is {_MIN_INTERVAL_MINUTES} minutes",
            )
        # Convert interval to cron: every N minutes
        if minutes < 60:
            return f"*/{minutes} * * * *"
        hours = minutes // 60
        return f"0 */{hours} * * *"

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="schedule.type must be 'cron' or 'interval'",
    )


def _validate_cron_expression(expr: str):
    """
    Validate a 5-field cron expression.
    Raises HTTPException if invalid or below minimum interval.
    """
    if not expr or not expr.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="schedule.cron is required when type is 'cron'",
        )

    parts = expr.strip().split()
    if len(parts) != 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cron expression must have exactly 5 fields: minute hour day-of-month month day-of-week",
        )

    minute_field = parts[0]

    # Block * (every minute) — minimum is */15
    if minute_field == "*":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Minimum schedule interval is {_MIN_INTERVAL_MINUTES} minutes. Use '*/15' or higher.",
        )

    # Block */N where N < 15
    m = re.match(r"^\*/(\d+)$", minute_field)
    if m:
        n = int(m.group(1))
        if n < _MIN_INTERVAL_MINUTES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Minimum schedule interval is {_MIN_INTERVAL_MINUTES} minutes. Got */{n}.",
            )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/jobs")
async def list_jobs(
    limit: int = 50,
    offset: int = 0,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List the current user's scheduled jobs."""
    result = await db.execute(
        text(
            "SELECT id, name, agent, message, workflow_name, schedule, deliver_to, is_active, "
            "last_run, next_run, created_at "
            "FROM scheduled_jobs WHERE user_id = :uid "
            "ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
        ),
        {"uid": current_user["user_id"], "limit": limit, "offset": offset},
    )
    rows = result.fetchall()

    return {
        "jobs": [_row_to_dict(row) for row in rows],
        "count": len(rows),
    }


@router.post("/jobs", status_code=status.HTTP_201_CREATED)
async def create_job(
    body: CreateJobRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new scheduled job.

    Constraints:
    - Max 10 active jobs per user
    - Minimum schedule interval: 15 minutes
    """
    user_id = current_user["user_id"]

    # Check job limit
    count_result = await db.execute(
        text("SELECT COUNT(*) FROM scheduled_jobs WHERE user_id = :uid AND is_active = TRUE"),
        {"uid": user_id},
    )
    active_count = count_result.scalar() or 0
    if active_count >= _MAX_JOBS_PER_USER:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Maximum of {_MAX_JOBS_PER_USER} active scheduled jobs per user",
        )

    # Convert schedule to cron expression
    cron_expr = _schedule_dto_to_cron(body.schedule)
    next_run = compute_next_run(cron_expr)

    # Build deliver_to dict
    deliver_to = body.deliver_to.model_dump(exclude_none=True)

    job_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    await db.execute(
        text(
            """
            INSERT INTO scheduled_jobs
              (id, user_id, name, agent, message, workflow_name, schedule, deliver_to, is_active, next_run, created_at)
            VALUES
              (:id, :uid, :name, :agent, :message, :workflow_name, :schedule, :deliver_to, TRUE, :next_run, :now)
            """
        ),
        {
            "id": job_id,
            "uid": user_id,
            "name": body.name,
            "agent": body.agent,
            "message": body.message,
            "workflow_name": body.workflow_name,
            "schedule": cron_expr,
            "deliver_to": json.dumps(deliver_to),
            "next_run": next_run,
            "now": now,
        },
    )
    await db.commit()

    logger.info(f"User {user_id} created scheduled job {job_id} ({body.name!r}, cron={cron_expr!r})")

    return {
        "job_id": job_id,
        "name": body.name,
        "agent": body.agent,
        "schedule": cron_expr,
        "deliver_to": deliver_to,
        "is_active": True,
        "next_run": next_run.isoformat(),
        "created_at": now.isoformat(),
        "note": "Job will be picked up at next Celery Beat restart. Use /run for immediate execution.",
    }


@router.get("/jobs/{job_id}")
async def get_job(
    job_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get details for a specific scheduled job."""
    row = await _fetch_job(db, job_id, current_user["user_id"], allow_admin=True,
                           current_user=current_user)
    return _row_to_dict(row)


@router.put("/jobs/{job_id}")
async def update_job(
    job_id: str,
    body: UpdateJobRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a scheduled job. Only the job owner or admin can update."""
    row = await _fetch_job(db, job_id, current_user["user_id"], allow_admin=True,
                           current_user=current_user)

    updates: dict = {}

    if body.name is not None:
        updates["name"] = body.name.strip()
    if body.message is not None:
        updates["message"] = body.message.strip()
    if body.workflow_name is not None:
        updates["workflow_name"] = body.workflow_name.strip()
    if body.schedule is not None:
        new_cron = _schedule_dto_to_cron(body.schedule)
        updates["schedule"] = new_cron
        updates["next_run"] = compute_next_run(new_cron)
    if body.deliver_to is not None:
        updates["deliver_to"] = json.dumps(body.deliver_to.model_dump(exclude_none=True))
    if body.is_active is not None:
        updates["is_active"] = body.is_active

    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update",
        )

    updates["id"] = job_id
    set_clause = ", ".join(f"{k} = :{k}" for k in updates if k != "id")

    await db.execute(
        text(f"UPDATE scheduled_jobs SET {set_clause} WHERE id = :id"),
        updates,
    )
    await db.commit()

    logger.info(f"User {current_user['user_id']} updated job {job_id}: {list(updates.keys())}")
    return {"job_id": job_id, "updated": [k for k in updates if k != "id"]}


@router.delete("/jobs/{job_id}", status_code=status.HTTP_200_OK)
async def delete_job(
    job_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a scheduled job. Only the job owner or admin can delete."""
    await _fetch_job(db, job_id, current_user["user_id"], allow_admin=True,
                     current_user=current_user)

    await db.execute(
        text("DELETE FROM scheduled_jobs WHERE id = :id"),
        {"id": job_id},
    )
    await db.commit()

    logger.info(f"User {current_user['user_id']} deleted job {job_id}")
    return {"deleted": True, "job_id": job_id}


@router.post("/jobs/{job_id}/run", status_code=status.HTTP_202_ACCEPTED)
async def run_job_now(
    job_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Manually trigger a scheduled job immediately.

    Enqueues the job as a Celery task. Returns 202 Accepted with the task ID.
    """
    row = await _fetch_job(db, job_id, current_user["user_id"], allow_admin=True,
                           current_user=current_user)

    deliver_to = row.deliver_to if isinstance(row.deliver_to, dict) else {}

    task_data = {
        "agent": row.agent,
        "source": "scheduler",
        "department": row.agent,
        "user_id": current_user["user_id"],
        "message": row.message,
        "deliver_to": deliver_to,
        "_job_id": job_id,
        "input_type": "text",
        "permissions": ["all"],
        "attachments": [],
        "conversation_history": [],
    }

    from app.tasks.tasks import process_agent_task
    celery_task = process_agent_task.delay(task_data)

    # Update last_run and next_run
    next_run = compute_next_run(row.schedule)
    await db.execute(
        text("UPDATE scheduled_jobs SET last_run = NOW(), next_run = :next_run WHERE id = :id"),
        {"id": job_id, "next_run": next_run},
    )
    await db.commit()

    logger.info(
        f"User {current_user['user_id']} manually triggered job {job_id} "
        f"→ Celery task {celery_task.id}"
    )
    return {
        "triggered": True,
        "job_id": job_id,
        "task_id": celery_task.id,
        "message": "Job enqueued. Results will be delivered per job configuration.",
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _fetch_job(
    db: AsyncSession,
    job_id: str,
    user_id: str,
    allow_admin: bool = False,
    current_user: dict = None,
):
    """
    Fetch a scheduled_jobs row by ID.
    Enforces ownership: only the job owner can access it.
    If allow_admin=True and current_user has role=admin, access is granted regardless.
    Raises 404 if not found, 403 if access denied.
    """
    result = await db.execute(
        text(
            "SELECT id, user_id, name, agent, message, workflow_name, schedule, deliver_to, "
            "is_active, last_run, next_run, created_at "
            "FROM scheduled_jobs WHERE id = :id"
        ),
        {"id": job_id},
    )
    row = result.fetchone()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scheduled job not found",
        )

    is_admin = (current_user or {}).get("role") in ("admin", "executive")
    if str(row.user_id) != user_id and not (allow_admin and is_admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied — you can only access your own jobs",
        )

    return row


def _row_to_dict(row) -> dict:
    """Convert a scheduled_jobs DB row to a response dict."""
    deliver_to = row.deliver_to if isinstance(row.deliver_to, dict) else {}
    return {
        "id": str(row.id),
        "name": row.name,
        "agent": row.agent,
        "message": row.message,
        "workflow_name": row.workflow_name,
        "schedule": row.schedule,
        "deliver_to": deliver_to,
        "is_active": row.is_active,
        "last_run": row.last_run.isoformat() if row.last_run else None,
        "next_run": row.next_run.isoformat() if row.next_run else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }
