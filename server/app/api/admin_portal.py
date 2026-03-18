"""
Mission Control Admin Portal API
All routes require admin role. Uses existing require_role("admin") dependency.
Prefix: /api/admin-portal
"""
import os
import uuid
import logging
from datetime import datetime, timezone, timedelta, date
from pathlib import Path
from typing import Optional

import psutil
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, Form
from pydantic import BaseModel, EmailStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import require_role, get_db
from app.core.auth import blacklist_all_user_tokens, hash_password

logger = logging.getLogger("mezzofy.admin_portal")

router = APIRouter()

AdminUser = Depends(require_role("admin"))


# ── Auth ──────────────────────────────────────────────────────────────────────

@router.get("/auth/me")
async def get_me(current_user: dict = AdminUser):
    """Verify token is admin and return user info."""
    return {
        "user_id": current_user.get("user_id"),
        "email": current_user.get("email"),
        "name": current_user.get("name"),
        "role": current_user.get("role"),
        "department": current_user.get("department"),
    }


# ── Dashboard — Sessions ──────────────────────────────────────────────────────

@router.get("/dashboard/sessions")
async def get_sessions(
    current_user: dict = AdminUser,
    db: AsyncSession = Depends(get_db),
):
    """Active and recent sessions across all users."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=30)
    result = await db.execute(
        text("""
            SELECT
                c.id            AS session_id,
                c.user_id,
                u.name          AS user_name,
                u.department,
                c.updated_at    AS last_active,
                jsonb_array_length(c.messages) AS message_count,
                c.department    AS agent
            FROM conversations c
            JOIN users u ON u.id = c.user_id
            WHERE u.deleted_at IS NULL
            ORDER BY c.updated_at DESC
            LIMIT 100
        """)
    )
    rows = result.fetchall()
    sessions = []
    for r in rows:
        last_active = r.last_active
        if last_active and last_active.tzinfo is None:
            last_active = last_active.replace(tzinfo=timezone.utc)
        sessions.append({
            "session_id": str(r.session_id),
            "user_id": str(r.user_id),
            "user_name": r.user_name,
            "department": r.department,
            "agent": r.agent or "",
            "last_active": last_active.isoformat() if last_active else None,
            "message_count": r.message_count or 0,
            "is_active": last_active >= cutoff if last_active else False,
        })
    return {"sessions": sessions, "total": len(sessions)}


# ── Dashboard — LLM Usage ─────────────────────────────────────────────────────

def _period_start(period: str) -> datetime:
    now = datetime.now(timezone.utc)
    if period == "today":
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "week":
        return now - timedelta(days=now.weekday())
    elif period == "month":
        return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


# LLM daily budget thresholds (USD)
LLM_BUDGETS = {
    "claude-sonnet": 50.0,
    "claude-haiku": 10.0,
    "claude-opus": 100.0,
    "kimi": 20.0,
}


@router.get("/dashboard/llm-usage")
async def get_llm_usage(
    period: str = Query("today", regex="^(today|week|month)$"),
    current_user: dict = AdminUser,
    db: AsyncSession = Depends(get_db),
):
    """Token and cost usage grouped by model."""
    start = _period_start(period)
    result = await db.execute(
        text("""
            SELECT
                model,
                SUM(input_tokens + output_tokens) AS total_tokens,
                SUM(input_tokens)                 AS input_tokens,
                SUM(output_tokens)                AS output_tokens,
                SUM(cost_usd)                     AS total_cost,
                COUNT(*)                          AS request_count
            FROM llm_usage
            WHERE created_at >= :start
            GROUP BY model
            ORDER BY total_cost DESC NULLS LAST
        """),
        {"start": start},
    )
    rows = result.fetchall()

    # Also get today totals for budget % calculation
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today_result = await db.execute(
        text("""
            SELECT model, SUM(cost_usd) AS today_cost
            FROM llm_usage
            WHERE created_at >= :start
            GROUP BY model
        """),
        {"start": today_start},
    )
    today_by_model = {r.model: float(r.today_cost or 0) for r in today_result.fetchall()}

    models = []
    for r in rows:
        model_key = r.model.lower().replace("claude-sonnet", "claude-sonnet").replace("claude-haiku", "claude-haiku")
        # Find matching budget key
        budget = 0.0
        for k, v in LLM_BUDGETS.items():
            if k in (r.model or "").lower():
                budget = v
                break
        today_cost = today_by_model.get(r.model, 0.0)
        budget_pct = round((today_cost / budget * 100), 1) if budget > 0 else 0.0
        models.append({
            "model": r.model,
            "total_tokens": int(r.total_tokens or 0),
            "input_tokens": int(r.input_tokens or 0),
            "output_tokens": int(r.output_tokens or 0),
            "total_cost_usd": round(float(r.total_cost or 0), 4),
            "request_count": int(r.request_count or 0),
            "daily_budget_usd": budget,
            "today_cost_usd": round(today_cost, 4),
            "budget_pct": budget_pct,
        })
    return {"period": period, "period_start": start.isoformat(), "models": models}


# ── Dashboard — System Vitals ─────────────────────────────────────────────────

@router.get("/dashboard/system-vitals")
async def get_system_vitals(
    current_user: dict = AdminUser,
    db: AsyncSession = Depends(get_db),
):
    """CPU, memory, disk, and service health."""
    # psutil metrics
    cpu_pct = psutil.cpu_percent(interval=0.5)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    try:
        load_avg = list(os.getloadavg())
    except AttributeError:
        load_avg = [0.0, 0.0, 0.0]  # Windows fallback

    # DB check
    db_ok = False
    try:
        await db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        pass

    # Redis check
    redis_ok = False
    try:
        import redis.asyncio as aioredis
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        async with aioredis.from_url(redis_url, decode_responses=True) as r:
            await r.ping()
        redis_ok = True
    except Exception:
        pass

    # Celery worker check
    celery_workers = 0
    try:
        from app.tasks.tasks import celery_app
        inspect = celery_app.control.inspect(timeout=2)
        active = inspect.active()
        celery_workers = len(active) if active else 0
    except Exception:
        pass

    return {
        "cpu": {
            "percent": cpu_pct,
            "load_avg_1m": load_avg[0],
            "load_avg_5m": load_avg[1],
            "load_avg_15m": load_avg[2],
        },
        "memory": {
            "total_gb": round(mem.total / 1e9, 2),
            "used_gb": round(mem.used / 1e9, 2),
            "available_gb": round(mem.available / 1e9, 2),
            "percent": mem.percent,
        },
        "disk": {
            "total_gb": round(disk.total / 1e9, 2),
            "used_gb": round(disk.used / 1e9, 2),
            "free_gb": round(disk.free / 1e9, 2),
            "percent": round(disk.used / disk.total * 100, 1),
        },
        "services": {
            "fastapi": True,
            "postgresql": db_ok,
            "redis": redis_ok,
            "celery_workers": celery_workers,
            "celery_beat": celery_workers > 0,
        },
    }


# ── Dashboard — Agent Status ──────────────────────────────────────────────────

@router.get("/dashboard/agent-status")
async def get_agent_status(
    current_user: dict = AdminUser,
    db: AsyncSession = Depends(get_db),
):
    """Agent busy/idle state and today's task counts."""
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    result = await db.execute(
        text("""
            SELECT
                department,
                COUNT(*) FILTER (WHERE status = 'completed' AND created_at >= :today)
                    AS tasks_today,
                COUNT(*) FILTER (WHERE status = 'running')
                    AS running_count,
                MAX(title) FILTER (WHERE status = 'running')
                    AS current_task
            FROM agent_tasks
            GROUP BY department
        """),
        {"today": today_start},
    )
    rows = result.fetchall()
    by_dept = {r.department: r for r in rows}

    departments = ["finance", "sales", "marketing", "support", "management", "hr", "research", "developer", "scheduler"]
    agents = []
    for dept in departments:
        r = by_dept.get(dept)
        agents.append({
            "name": dept.capitalize(),
            "department": dept,
            "is_busy": bool(r and r.running_count > 0),
            "tasks_today": int(r.tasks_today) if r else 0,
            "current_task": r.current_task if r and r.running_count > 0 else None,
        })

    return {"agents": agents}


# ── Scheduler ─────────────────────────────────────────────────────────────────

@router.get("/scheduler/jobs")
async def list_scheduler_jobs(
    current_user: dict = AdminUser,
    db: AsyncSession = Depends(get_db),
):
    """All scheduled jobs with owner info."""
    result = await db.execute(
        text("""
            SELECT
                sj.id, sj.name, sj.schedule, sj.deliver_to,
                sj.is_active, sj.last_run, sj.next_run,
                sj.agent, sj.workflow_name, sj.created_at,
                u.email AS user_email, u.name AS user_name
            FROM scheduled_jobs sj
            JOIN users u ON u.id = sj.user_id
            ORDER BY sj.created_at DESC
        """)
    )
    rows = result.fetchall()
    jobs = []
    for r in rows:
        jobs.append({
            "id": str(r.id),
            "name": r.name,
            "schedule": r.schedule,
            "deliver_to": r.deliver_to,
            "is_active": r.is_active,
            "last_run": r.last_run.isoformat() if r.last_run else None,
            "next_run": r.next_run.isoformat() if r.next_run else None,
            "agent": r.agent,
            "workflow_name": r.workflow_name,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "user_email": r.user_email,
            "user_name": r.user_name,
        })
    return {"jobs": jobs, "total": len(jobs)}


@router.get("/scheduler/jobs/{job_id}/history")
async def get_job_history(
    job_id: str,
    current_user: dict = AdminUser,
    db: AsyncSession = Depends(get_db),
):
    """Last 50 run records for a scheduled job."""
    result = await db.execute(
        text("""
            SELECT id, title, status, started_at, completed_at,
                   EXTRACT(EPOCH FROM (completed_at - started_at)) * 1000 AS duration_ms,
                   current_step, error, created_at
            FROM agent_tasks
            WHERE (details->>'job_id' = :job_id OR title ILIKE :pattern)
            ORDER BY created_at DESC
            LIMIT 50
        """),
        {"job_id": job_id, "pattern": f"%{job_id}%"},
    )
    rows = result.fetchall()
    history = []
    for r in rows:
        history.append({
            "id": str(r.id),
            "title": r.title,
            "status": r.status,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
            "duration_ms": int(r.duration_ms) if r.duration_ms else None,
            "current_step": r.current_step,
            "error": r.error,
        })
    return {"job_id": job_id, "history": history, "total": len(history)}


class TriggerJobResponse(BaseModel):
    task_id: str
    message: str


@router.post("/scheduler/jobs/{job_id}/trigger", response_model=TriggerJobResponse)
async def trigger_job(
    job_id: str,
    current_user: dict = AdminUser,
    db: AsyncSession = Depends(get_db),
):
    """Manually trigger a scheduled job."""
    # Verify job exists
    result = await db.execute(
        text("SELECT id, name, agent, message FROM scheduled_jobs WHERE id = :id"),
        {"id": job_id},
    )
    job = result.fetchone()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Enqueue via Celery
    try:
        from app.tasks.tasks import process_agent_task
        task = process_agent_task.delay(
            user_id=current_user.get("user_id"),
            session_id=str(uuid.uuid4()),
            department=job.agent,
            message=job.message,
            source="manual_admin_trigger",
        )
        task_id = task.id
    except Exception as e:
        logger.error(f"Failed to enqueue job {job_id}: {e}")
        task_id = str(uuid.uuid4())

    # Audit log
    await db.execute(
        text("""
            INSERT INTO audit_log (user_id, action, resource, details, success)
            VALUES (:uid, 'admin_trigger_job', :resource, :details, TRUE)
        """),
        {
            "uid": current_user.get("user_id"),
            "resource": f"scheduled_jobs/{job_id}",
            "details": f'{{"job_id": "{job_id}", "task_id": "{task_id}", "admin": "{current_user.get("email")}"}}'
        },
    )
    await db.commit()

    return TriggerJobResponse(task_id=task_id, message=f"Job '{job.name}' queued successfully")


@router.patch("/scheduler/jobs/{job_id}/toggle")
async def toggle_job(
    job_id: str,
    current_user: dict = AdminUser,
    db: AsyncSession = Depends(get_db),
):
    """Toggle a job's is_active state."""
    result = await db.execute(
        text("SELECT id, name, is_active FROM scheduled_jobs WHERE id = :id"),
        {"id": job_id},
    )
    job = result.fetchone()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    new_state = not job.is_active
    await db.execute(
        text("UPDATE scheduled_jobs SET is_active = :state WHERE id = :id"),
        {"state": new_state, "id": job_id},
    )
    await db.execute(
        text("""
            INSERT INTO audit_log (user_id, action, resource, details, success)
            VALUES (:uid, 'admin_toggle_job', :resource, :details, TRUE)
        """),
        {
            "uid": current_user.get("user_id"),
            "resource": f"scheduled_jobs/{job_id}",
            "details": f'{{"job_id": "{job_id}", "new_state": {str(new_state).lower()}}}'
        },
    )
    await db.commit()
    return {"job_id": job_id, "is_active": new_state, "name": job.name}


# ── Agents ────────────────────────────────────────────────────────────────────

AGENT_REGISTRY = [
    {"name": "Finance", "department": "finance", "skills": ["financial-reporting", "budget-analysis", "forecasting"]},
    {"name": "Sales", "department": "sales", "skills": ["lead-management", "crm", "outreach"]},
    {"name": "Marketing", "department": "marketing", "skills": ["campaign-analysis", "content-generation", "social-media"]},
    {"name": "Support", "department": "support", "skills": ["ticket-management", "customer-lookup", "escalation"]},
    {"name": "Management", "department": "management", "skills": ["kpi-reporting", "team-analytics", "executive-summary"]},
    {"name": "HR", "department": "hr", "skills": ["headcount", "onboarding", "payroll-support"]},
    {"name": "Research", "department": "research", "skills": ["web-search", "competitive-intelligence", "market-analysis"]},
    {"name": "Developer", "department": "developer", "skills": ["code-generation", "debugging", "claude-code-cli"]},
    {"name": "Scheduler", "department": "scheduler", "skills": ["job-scheduling", "cron-management", "delivery"]},
]


@router.get("/agents")
async def list_agents(
    current_user: dict = AdminUser,
    db: AsyncSession = Depends(get_db),
):
    """Agent registry with real-time task counts."""
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    result = await db.execute(
        text("""
            SELECT
                department,
                COUNT(*) FILTER (WHERE status = 'completed' AND created_at >= :today) AS tasks_today,
                COUNT(*) FILTER (WHERE status = 'running') AS running_count
            FROM agent_tasks
            GROUP BY department
        """),
        {"today": today_start},
    )
    task_stats = {r.department: r for r in result.fetchall()}

    agents = []
    for agent in AGENT_REGISTRY:
        dept = agent["department"]
        stats = task_stats.get(dept)

        # Count RAG files
        kb_dir = Path("knowledge") / dept
        rag_count = 0
        if kb_dir.exists():
            rag_count = len(list(kb_dir.iterdir()))

        agents.append({
            **agent,
            "is_busy": bool(stats and stats.running_count > 0),
            "tasks_today": int(stats.tasks_today) if stats else 0,
            "rag_memory_count": rag_count,
        })

    return {"agents": agents}


@router.get("/agents/{agent_name}/rag-memory")
async def get_agent_rag_memory(
    agent_name: str,
    current_user: dict = AdminUser,
):
    """List RAG knowledge files for an agent."""
    kb_dir = Path("knowledge") / agent_name
    if not kb_dir.exists():
        return {"agent": agent_name, "files": [], "total": 0}

    files = []
    for f in sorted(kb_dir.iterdir()):
        if f.is_file():
            stat = f.stat()
            files.append({
                "filename": f.name,
                "size_bytes": stat.st_size,
                "last_modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
            })

    return {"agent": agent_name, "files": files, "total": len(files)}


@router.post("/agents/{agent_name}/rag-memory/upload")
async def upload_agent_rag_memory(
    agent_name: str,
    file: UploadFile = File(...),
    current_user: dict = AdminUser,
):
    """Upload a RAG knowledge file for an agent."""
    safe_filename = Path(file.filename or "upload").name
    kb_dir = Path("knowledge") / agent_name
    kb_dir.mkdir(parents=True, exist_ok=True)

    save_path = kb_dir / safe_filename
    content = await file.read()
    save_path.write_bytes(content)

    stat = save_path.stat()
    return {
        "filename": safe_filename,
        "size_bytes": stat.st_size,
        "last_modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
    }


@router.delete("/agents/{agent_name}/rag-memory/{filename}")
async def delete_agent_rag_memory(
    agent_name: str,
    filename: str,
    current_user: dict = AdminUser,
):
    """Delete a RAG knowledge file for an agent."""
    safe_filename = Path(filename).name
    file_path = Path("knowledge") / agent_name / safe_filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    file_path.unlink()
    return {"deleted": True, "filename": safe_filename}


# ── Files ─────────────────────────────────────────────────────────────────────

@router.get("/files")
async def list_files(
    user_id: Optional[str] = Query(None),
    file_type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: dict = AdminUser,
    db: AsyncSession = Depends(get_db),
):
    """Paginated file list with owner info."""
    offset = (page - 1) * per_page
    filters = ["TRUE"]
    params: dict = {"limit": per_page, "offset": offset}

    if user_id:
        filters.append("a.user_id = :user_id")
        params["user_id"] = user_id
    if file_type:
        filters.append("a.file_type = :file_type")
        params["file_type"] = file_type

    where = " AND ".join(filters)

    result = await db.execute(
        text(f"""
            SELECT
                a.id, a.filename, a.file_type, a.scope, a.department,
                a.file_path, a.created_at, a.size_bytes,
                u.email AS owner_email
            FROM artifacts a
            LEFT JOIN users u ON u.id = a.user_id
            WHERE {where}
            ORDER BY a.created_at DESC
            LIMIT :limit OFFSET :offset
        """),
        params,
    )
    rows = result.fetchall()

    count_result = await db.execute(
        text(f"SELECT COUNT(*) FROM artifacts a WHERE {where}"),
        {k: v for k, v in params.items() if k not in ("limit", "offset")},
    )
    total = count_result.scalar() or 0

    files = []
    for r in rows:
        # Get size from filesystem if not stored
        size = r.size_bytes
        if not size and r.file_path:
            try:
                size = Path(r.file_path).stat().st_size
            except Exception:
                size = None
        files.append({
            "id": str(r.id),
            "filename": r.filename,
            "file_type": r.file_type,
            "scope": r.scope,
            "department": r.department,
            "owner_email": r.owner_email,
            "size_bytes": size,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "download_url": f"/files/{r.id}",
        })

    return {
        "files": files,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page,
    }


@router.delete("/files/{file_id}")
async def delete_file(
    file_id: str,
    current_user: dict = AdminUser,
    db: AsyncSession = Depends(get_db),
):
    """Delete a file record and its physical file."""
    result = await db.execute(
        text("SELECT id, filename, file_path FROM artifacts WHERE id = :id"),
        {"id": file_id},
    )
    artifact = result.fetchone()
    if not artifact:
        raise HTTPException(status_code=404, detail="File not found")

    # Delete physical file
    if artifact.file_path:
        try:
            Path(artifact.file_path).unlink(missing_ok=True)
        except Exception as e:
            logger.warning(f"Could not delete physical file {artifact.file_path}: {e}")

    await db.execute(
        text("DELETE FROM artifacts WHERE id = :id"),
        {"id": file_id},
    )
    await db.execute(
        text("""
            INSERT INTO audit_log (user_id, action, resource, details, success)
            VALUES (:uid, 'admin_delete_file', :resource, :details, TRUE)
        """),
        {
            "uid": current_user.get("user_id"),
            "resource": f"artifacts/{file_id}",
            "details": f'{{"file_id": "{file_id}", "filename": "{artifact.filename}"}}'
        },
    )
    await db.commit()
    return {"deleted": True, "file_id": file_id}


class RenameFileRequest(BaseModel):
    new_filename: str


@router.patch("/files/{file_id}/rename")
async def rename_file(
    file_id: str,
    body: RenameFileRequest,
    current_user: dict = AdminUser,
    db: AsyncSession = Depends(get_db),
):
    """Rename a file record and its physical file."""
    result = await db.execute(
        text("SELECT id, filename, file_path FROM artifacts WHERE id = :id"),
        {"id": file_id},
    )
    artifact = result.fetchone()
    if not artifact:
        raise HTTPException(status_code=404, detail="File not found")

    safe_new_name = Path(body.new_filename).name

    # Rename physical file if it exists
    if artifact.file_path:
        old_path = Path(artifact.file_path)
        if old_path.exists():
            new_path = old_path.parent / safe_new_name
            old_path.rename(new_path)
            await db.execute(
                text("UPDATE artifacts SET filename = :fname, file_path = :fpath WHERE id = :id"),
                {"fname": safe_new_name, "fpath": str(new_path), "id": file_id},
            )
        else:
            await db.execute(
                text("UPDATE artifacts SET filename = :fname WHERE id = :id"),
                {"fname": safe_new_name, "id": file_id},
            )
    else:
        await db.execute(
            text("UPDATE artifacts SET filename = :fname WHERE id = :id"),
            {"fname": safe_new_name, "id": file_id},
        )

    await db.execute(
        text("""
            INSERT INTO audit_log (user_id, action, resource, details, success)
            VALUES (:uid, 'admin_rename_file', :resource, :details, TRUE)
        """),
        {
            "uid": current_user.get("user_id"),
            "resource": f"artifacts/{file_id}",
            "details": f'{{"file_id": "{file_id}", "old_filename": "{artifact.filename}", "new_filename": "{safe_new_name}"}}'
        },
    )
    await db.commit()
    return {"id": file_id, "filename": safe_new_name}


@router.post("/files/upload")
async def admin_upload_file(
    file: UploadFile = File(...),
    department: Optional[str] = Form(None),
    scope: Optional[str] = Form("shared"),
    current_user: dict = AdminUser,
    db: AsyncSession = Depends(get_db),
):
    """Admin upload a file to any department folder."""
    from app.context.artifact_manager import get_dept_artifacts_dir, get_company_artifacts_dir, get_artifacts_dir

    dept = department or "general"
    safe_filename = Path(file.filename or "upload").name

    if scope == "company":
        upload_dir = get_company_artifacts_dir()
    else:
        upload_dir = get_dept_artifacts_dir(dept)

    content = await file.read()
    save_path = upload_dir / safe_filename
    save_path.write_bytes(content)

    artifact_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    content_type = file.content_type or ""
    file_type = content_type.split("/")[-1].split(";")[0] or "file"

    await db.execute(
        text("""
            INSERT INTO artifacts
              (id, user_id, filename, file_path, file_type, scope, department, size_bytes, created_at)
            VALUES
              (:id, :uid, :fname, :fpath, :ftype, :scope, :dept, :size, :now)
        """),
        {
            "id": artifact_id,
            "uid": current_user.get("user_id"),
            "fname": safe_filename,
            "fpath": str(save_path),
            "ftype": file_type,
            "scope": scope,
            "dept": dept,
            "size": len(content),
            "now": now,
        },
    )
    await db.execute(
        text("""
            INSERT INTO audit_log (user_id, action, resource, details, success)
            VALUES (:uid, 'admin_upload_file', :resource, :details, TRUE)
        """),
        {
            "uid": current_user.get("user_id"),
            "resource": f"artifacts/{artifact_id}",
            "details": f'{{"filename": "{safe_filename}", "department": "{dept}", "scope": "{scope}"}}'
        },
    )
    await db.commit()

    return {
        "id": artifact_id,
        "filename": safe_filename,
        "file_type": file_type,
        "scope": scope,
        "department": dept,
        "owner_email": current_user.get("email"),
        "size_bytes": len(content),
        "created_at": now.isoformat(),
        "download_url": f"/files/{artifact_id}",
    }


@router.get("/files/folder-tree")
async def get_folder_tree(
    current_user: dict = AdminUser,
    db: AsyncSession = Depends(get_db),
):
    """Get all files grouped by scope and department."""
    result = await db.execute(
        text("""
            SELECT
                a.id, a.filename, a.file_type, a.scope, a.department,
                a.file_path, a.created_at, a.size_bytes,
                u.email AS owner_email
            FROM artifacts a
            LEFT JOIN users u ON u.id = a.user_id
            ORDER BY a.scope, a.department, a.created_at DESC
        """)
    )
    rows = result.fetchall()

    # Group by (scope, department)
    from collections import defaultdict
    groups = defaultdict(lambda: {"scope": "", "department": "", "owner_email": None, "files": []})

    for r in rows:
        scope = r.scope or "personal"
        dept = r.department or "general"
        key = f"{scope}:{dept}"
        grp = groups[key]
        grp["scope"] = scope
        grp["department"] = dept
        if not grp["owner_email"] and r.owner_email:
            grp["owner_email"] = r.owner_email

        size = r.size_bytes
        if not size and r.file_path:
            try:
                size = Path(r.file_path).stat().st_size
            except Exception:
                size = None

        grp["files"].append({
            "id": str(r.id),
            "filename": r.filename,
            "file_type": r.file_type,
            "scope": scope,
            "department": dept,
            "owner_email": r.owner_email,
            "size_bytes": size,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "download_url": f"/files/{r.id}",
        })

    return {"folders": list(groups.values())}


# ── Users ─────────────────────────────────────────────────────────────────────

@router.get("/users")
async def list_users(
    current_user: dict = AdminUser,
    db: AsyncSession = Depends(get_db),
):
    """All active users with session counts."""
    result = await db.execute(
        text("""
            SELECT
                u.id, u.email, u.name, u.department, u.role,
                u.is_active, u.last_login, u.created_at,
                COUNT(c.id) AS session_count
            FROM users u
            LEFT JOIN conversations c ON c.user_id = u.id
            WHERE u.deleted_at IS NULL
            GROUP BY u.id
            ORDER BY u.created_at DESC
        """)
    )
    rows = result.fetchall()
    users = []
    for r in rows:
        users.append({
            "id": str(r.id),
            "email": r.email,
            "name": r.name,
            "department": r.department,
            "role": r.role,
            "is_active": r.is_active,
            "last_login_at": r.last_login.isoformat() if r.last_login else None,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "session_count": int(r.session_count or 0),
        })
    return {"users": users, "total": len(users)}


class CreateUserRequest(BaseModel):
    email: EmailStr
    name: str
    department: str
    role: str


@router.post("/users", status_code=status.HTTP_201_CREATED)
async def create_user(
    body: CreateUserRequest,
    current_user: dict = AdminUser,
    db: AsyncSession = Depends(get_db),
):
    """Create a new user and send an invite email."""
    # Check if email already exists
    result = await db.execute(
        text("SELECT id FROM users WHERE email = :email"),
        {"email": body.email},
    )
    if result.fetchone():
        raise HTTPException(status_code=409, detail="Email already registered")

    user_id = str(uuid.uuid4())
    invite_token = str(uuid.uuid4()).replace("-", "")
    temp_password = str(uuid.uuid4())[:12]

    await db.execute(
        text("""
            INSERT INTO users (id, email, name, department, role, is_active, password_hash, invite_token, created_at)
            VALUES (:id, :email, :name, :department, :role, FALSE, :password_hash, :invite_token, NOW())
        """),
        {
            "id": user_id,
            "email": body.email,
            "name": body.name,
            "department": body.department,
            "role": body.role,
            "password_hash": hash_password(temp_password),
            "invite_token": invite_token,
        },
    )

    # Send invite email via Outlook
    try:
        from app.tools.communication.outlook_ops import OutlookOps
        ops = OutlookOps()
        await ops._send_email(
            to=[body.email],
            subject="Welcome to Mezzofy AI Assistant",
            body=(
                f"Hi {body.name},\n\n"
                f"You have been invited to Mezzofy AI Assistant.\n"
                f"Your temporary password is: {temp_password}\n\n"
                f"Please log in and change your password.\n\n"
                f"Invite token: {invite_token}\n\n"
                "Best regards,\nMezzofy Team"
            ),
        )
    except Exception as e:
        logger.warning(f"Failed to send invite email to {body.email}: {e}")

    await db.execute(
        text("""
            INSERT INTO audit_log (user_id, action, resource, details, success)
            VALUES (:uid, 'admin_create_user', :resource, :details, TRUE)
        """),
        {
            "uid": current_user.get("user_id"),
            "resource": f"users/{user_id}",
            "details": f'{{"new_user_email": "{body.email}", "role": "{body.role}"}}'
        },
    )
    await db.commit()

    return {
        "id": user_id,
        "email": body.email,
        "name": body.name,
        "department": body.department,
        "role": body.role,
        "is_active": False,
        "invite_token": invite_token,
    }


@router.get("/users/{user_id}")
async def get_user(
    user_id: str,
    current_user: dict = AdminUser,
    db: AsyncSession = Depends(get_db),
):
    """Full user profile with recent sessions."""
    result = await db.execute(
        text("""
            SELECT id, email, name, department, role, is_active, last_login, created_at
            FROM users WHERE id = :id AND deleted_at IS NULL
        """),
        {"id": user_id},
    )
    user = result.fetchone()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    sessions_result = await db.execute(
        text("""
            SELECT id, department, updated_at, jsonb_array_length(messages) AS message_count
            FROM conversations
            WHERE user_id = :uid
            ORDER BY updated_at DESC
            LIMIT 10
        """),
        {"uid": user_id},
    )
    sessions = [
        {
            "id": str(s.id),
            "department": s.department,
            "last_active": s.updated_at.isoformat() if s.updated_at else None,
            "message_count": s.message_count or 0,
        }
        for s in sessions_result.fetchall()
    ]

    return {
        "id": str(user.id),
        "email": user.email,
        "name": user.name,
        "department": user.department,
        "role": user.role,
        "is_active": user.is_active,
        "last_login_at": user.last_login.isoformat() if user.last_login else None,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "recent_sessions": sessions,
    }


class UpdateUserRequest(BaseModel):
    name: Optional[str] = None
    department: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None


@router.patch("/users/{user_id}")
async def update_user(
    user_id: str,
    body: UpdateUserRequest,
    current_user: dict = AdminUser,
    db: AsyncSession = Depends(get_db),
):
    """Update user fields."""
    result = await db.execute(
        text("SELECT id FROM users WHERE id = :id AND deleted_at IS NULL"),
        {"id": user_id},
    )
    if not result.fetchone():
        raise HTTPException(status_code=404, detail="User not found")

    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    set_clauses = ", ".join(f"{k} = :{k}" for k in updates)
    updates["id"] = user_id
    await db.execute(
        text(f"UPDATE users SET {set_clauses} WHERE id = :id"),
        updates,
    )
    await db.execute(
        text("""
            INSERT INTO audit_log (user_id, action, resource, details, success)
            VALUES (:uid, 'admin_update_user', :resource, :details, TRUE)
        """),
        {
            "uid": current_user.get("user_id"),
            "resource": f"users/{user_id}",
            "details": str(body.model_dump(exclude_none=True)).replace("'", '"')
        },
    )
    await db.commit()
    return {"updated": True, "user_id": user_id}


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    current_user: dict = AdminUser,
    db: AsyncSession = Depends(get_db),
):
    """Soft-delete a user and blacklist all their tokens."""
    # Prevent admin from deleting themselves
    if user_id == current_user.get("user_id"):
        raise HTTPException(status_code=400, detail="Cannot delete your own account")

    result = await db.execute(
        text("SELECT id, email FROM users WHERE id = :id AND deleted_at IS NULL"),
        {"id": user_id},
    )
    user = result.fetchone()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Soft delete + deactivate
    await db.execute(
        text("UPDATE users SET deleted_at = NOW(), is_active = FALSE WHERE id = :id"),
        {"id": user_id},
    )

    # Blacklist all tokens
    try:
        await blacklist_all_user_tokens(user_id)
    except Exception as e:
        logger.warning(f"Failed to blacklist tokens for user {user_id}: {e}")

    await db.execute(
        text("""
            INSERT INTO audit_log (user_id, action, resource, details, success)
            VALUES (:uid, 'admin_delete_user', :resource, :details, TRUE)
        """),
        {
            "uid": current_user.get("user_id"),
            "resource": f"users/{user_id}",
            "details": f'{{"deleted_user_email": "{user.email}"}}'
        },
    )
    await db.commit()
    return {"deleted": True, "user_id": user_id, "email": user.email}
