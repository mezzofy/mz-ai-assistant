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
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, Form, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, EmailStr
from sqlalchemy import text, bindparam, ARRAY, String
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import require_role, get_db
from app.core.auth import blacklist_all_user_tokens, hash_password, decode_access_token

logger = logging.getLogger("mezzofy.admin_portal")

_KNOWLEDGE_BASE = Path(__file__).parent.parent.parent / "knowledge"

router = APIRouter()

AdminUser = Depends(require_role("admin"))


# ── Auth ──────────────────────────────────────────────────────────────────────

@router.get("/auth/me")
async def get_me(
    current_user: dict = AdminUser,
    db: AsyncSession = Depends(get_db),
):
    """Verify token is admin and return user info (includes employee fields if linked)."""
    employee_id = None
    staff_id = None
    manager_employee_id = None
    try:
        result = await db.execute(
            text("SELECT id, staff_id, manager_id FROM hr_employees WHERE user_id = :uid AND is_active = true"),
            {"uid": current_user.get("user_id")},
        )
        emp = result.mappings().one_or_none()
        if emp:
            employee_id = str(emp["id"])
            staff_id = emp["staff_id"]
            manager_employee_id = str(emp["manager_id"]) if emp["manager_id"] else None
    except Exception:
        pass  # HR tables may not exist yet

    return {
        "user_id": current_user.get("user_id"),
        "email": current_user.get("email"),
        "name": current_user.get("name"),
        "role": current_user.get("role"),
        "department": current_user.get("department"),
        "employee_id": employee_id,
        "staff_id": staff_id,
        "manager_employee_id": manager_employee_id,
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
                MAX(content) FILTER (WHERE status = 'running')
                    AS current_task
            FROM agent_tasks
            GROUP BY department
        """),
        {"today": today_start},
    )
    rows = result.fetchall()
    by_dept = {r.department: r for r in rows}

    departments = ["finance", "sales", "marketing", "support", "management", "hr", "legal", "research", "developer", "scheduler"]
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


class CreateSchedulerJobRequest(BaseModel):
    name: str
    message: str
    agent: str
    schedule: str
    workflow_name: Optional[str] = None
    deliver_to: Optional[dict] = None


_ADMIN_VALID_AGENTS = {"finance", "sales", "marketing", "support", "management", "hr"}


@router.post("/scheduler/jobs", status_code=201)
async def create_scheduler_job(
    body: CreateSchedulerJobRequest,
    current_user: dict = AdminUser,
    db: AsyncSession = Depends(get_db),
):
    """Create a new scheduled job (admin)."""
    import json as _json

    # Validate agent
    if body.agent not in _ADMIN_VALID_AGENTS:
        raise HTTPException(
            status_code=400,
            detail=f"agent must be one of: {', '.join(sorted(_ADMIN_VALID_AGENTS))}",
        )

    # Validate cron schedule (5 fields)
    if len(body.schedule.strip().split()) != 5:
        raise HTTPException(
            status_code=400,
            detail="schedule must be a 5-field cron expression: minute hour day-of-month month day-of-week",
        )

    # Compute next_run
    from app.webhooks.scheduler import compute_next_run
    try:
        next_run = compute_next_run(body.schedule.strip())
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid cron expression: {e}")

    user_id = current_user.get("user_id")
    deliver_to = body.deliver_to or {}

    try:
        result = await db.execute(
            text("""
                INSERT INTO scheduled_jobs (user_id, name, agent, message, schedule, workflow_name, deliver_to, next_run)
                VALUES (:user_id, :name, :agent, :message, :schedule, :workflow_name, CAST(:deliver_to AS JSONB), :next_run)
                RETURNING id, name, agent, message, schedule, workflow_name, deliver_to, is_active, next_run, created_at
            """),
            {
                "user_id": user_id,
                "name": body.name.strip(),
                "agent": body.agent.strip(),
                "message": body.message.strip(),
                "schedule": body.schedule.strip(),
                "workflow_name": body.workflow_name.strip() if body.workflow_name else None,
                "deliver_to": _json.dumps(deliver_to),
                "next_run": next_run,
            },
        )
        row = result.fetchone()
        await db.commit()
        return {
            "id": str(row.id),
            "name": row.name,
            "agent": row.agent,
            "message": row.message,
            "schedule": row.schedule,
            "workflow_name": row.workflow_name,
            "deliver_to": row.deliver_to,
            "is_active": row.is_active,
            "next_run": row.next_run.isoformat() if row.next_run else None,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create scheduler job: {e}")
        raise HTTPException(status_code=500, detail="Failed to create scheduled job")


@router.get("/scheduler/jobs/{job_id}/history")
async def get_job_history(
    job_id: str,
    current_user: dict = AdminUser,
    db: AsyncSession = Depends(get_db),
):
    """Last 50 run records for a scheduled job."""
    result = await db.execute(
        text("""
            SELECT id, content, status, started_at, completed_at,
                   EXTRACT(EPOCH FROM (completed_at - started_at)) * 1000 AS duration_ms,
                   current_step, error, created_at
            FROM agent_tasks
            WHERE (details->>'job_id' = :job_id OR content ILIKE :pattern)
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
            "content": r.content,
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
    {
        "name": "Management Agent", "persona": "Max", "department": "management",
        "description": "Cross-department KPI aggregator and orchestrator. Decomposes multi-department tasks and delegates to specialist agents.",
        "skills": ["data_analysis", "web_research"],
        "tools_allowed": ["DatabaseOps", "PDFOps", "PPTXOps", "CSVOps", "EmailOps", "TeamsOps"],
        "llm_model": "claude-sonnet-4-6", "is_orchestrator": True,
    },
    {
        "name": "Finance Agent", "persona": "Fiona", "department": "finance",
        "description": "Financial analysis, KPI reports, revenue metrics, and department-scoped data access.",
        "skills": ["financial_reporting", "data_analysis"],
        "tools_allowed": ["DatabaseOps", "PDFOps", "PPTXOps", "CSVOps"],
        "llm_model": "claude-sonnet-4-6", "is_orchestrator": False,
    },
    {
        "name": "Sales Agent", "persona": "Sam", "department": "sales",
        "description": "CRM lead management, LinkedIn prospecting, sales email outreach, and pitch deck generation.",
        "skills": ["linkedin_prospecting", "email_outreach", "pitch_deck_generation", "web_research"],
        "tools_allowed": ["CRMOps", "LinkedInOps", "EmailOps", "PPTXOps", "PDFOps"],
        "llm_model": "claude-sonnet-4-6", "is_orchestrator": False,
    },
    {
        "name": "Marketing Agent", "persona": "Maya", "department": "marketing",
        "description": "Marketing content creation, campaign email delivery, and competitive web research.",
        "skills": ["content_generation", "web_research"],
        "tools_allowed": ["EmailOps", "WebScrapeOps", "PDFOps", "PPTXOps", "DOCXOps"],
        "llm_model": "claude-sonnet-4-6", "is_orchestrator": False,
    },
    {
        "name": "Support Agent", "persona": "Suki", "department": "support",
        "description": "Support ticket management, SLA reporting, and customer communications.",
        "skills": ["data_analysis", "email_outreach"],
        "tools_allowed": ["DatabaseOps", "EmailOps", "TeamsOps", "PDFOps"],
        "llm_model": "claude-sonnet-4-6", "is_orchestrator": False,
    },
    {
        "name": "HR Agent", "persona": "Hana", "department": "hr",
        "description": "HR data analytics, leave management, and employee communications.",
        "skills": ["data_analysis", "email_outreach"],
        "tools_allowed": ["DatabaseOps", "EmailOps", "CSVOps"],
        "llm_model": "claude-sonnet-4-6", "is_orchestrator": False,
    },
    {
        "name": "Legal Agent", "persona": "Leo", "department": "legal",
        "description": "International business law specialist — contract review and drafting for SG, HK, MY, UAE, KSA, QA, and Cayman Islands.",
        "skills": ["document_review", "contract_drafting", "legal_research", "jurisdiction_advisory"],
        "tools_allowed": ["DOCXOps", "PDFOps", "EmailOps", "TeamsOps", "DatabaseOps", "WebResearch"],
        "llm_model": "claude-sonnet-4-6", "is_orchestrator": False,
    },
    {
        "name": "Research Agent", "persona": "Rex", "department": "research",
        "description": "Agentic web-research specialist. Multi-iteration search loop using Claude native web_search tool.",
        "skills": ["web_research", "data_analysis", "deep_research", "source_verification"],
        "tools_allowed": ["web_search_20250305 (native Anthropic tool)"],
        "llm_model": "claude-sonnet-4-6", "is_orchestrator": False,
    },
    {
        "name": "Developer Agent", "persona": "Dev", "department": "developer",
        "description": "Runs Claude Code CLI as a headless subprocess for code generation, review, and execution tasks.",
        "skills": ["code_generation", "code_review", "code_execution", "api_integration", "test_generation"],
        "tools_allowed": ["Claude Code CLI (stream-JSON subprocess)"],
        "llm_model": "claude-sonnet-4-6", "is_orchestrator": False,
    },
    {
        "name": "Scheduler Agent", "persona": "Sched", "department": "scheduler",
        "description": "Chat-based scheduled job manager. Accepts natural language and translates to UTC cron expressions.",
        "skills": ["schedule_management", "cron_validation", "job_monitoring", "beat_sync"],
        "tools_allowed": ["SchedulerOps (create_job, list_jobs, delete_job, run_now)"],
        "llm_model": "claude-sonnet-4-6", "is_orchestrator": False,
    },
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
    kb_dir = _KNOWLEDGE_BASE / agent_name
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
    kb_dir = _KNOWLEDGE_BASE / agent_name
    save_path = kb_dir / safe_filename
    content = await file.read()

    try:
        kb_dir.mkdir(parents=True, exist_ok=True)
        save_path.write_bytes(content)
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {e}")

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
    file_path = _KNOWLEDGE_BASE / agent_name / safe_filename
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
    # Sync orphaned disk files into DB for all users
    try:
        from app.context.artifact_manager import sync_user_artifacts
        from pathlib import Path as FsPath

        artifacts_root = FsPath("/var/mezzofy/artifacts")
        if artifacts_root.exists():
            users_result = await db.execute(text("SELECT id, email, department FROM users WHERE deleted_at IS NULL"))
            all_users = users_result.fetchall()
            for u in all_users:
                try:
                    await sync_user_artifacts(db, str(u.id), u.department or "general", u.email)
                except Exception as sync_err:
                    logger.warning(f"sync_user_artifacts failed for {u.email}: {sync_err}")
    except Exception as sync_ex:
        logger.warning(f"Pre-query artifact sync failed: {sync_ex}")

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

        # Extract subfolder from file_path (parts after {dept}/{email-or-shared}/)
        subfolder = None
        if r.file_path:
            try:
                artifacts_root = Path("/var/mezzofy/artifacts")
                rel_parts = Path(r.file_path).relative_to(artifacts_root).parts
                # rel_parts: (dept, email-or-"shared", [subfolder...], filename)
                if len(rel_parts) > 3:
                    subfolder = "/".join(rel_parts[2:-1])
            except Exception:
                subfolder = None

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
            "subfolder": subfolder,
        })

    return {"folders": list(groups.values())}


@router.get("/files/{file_id}/download")
async def download_file(
    file_id: str,
    current_user: dict = AdminUser,
    db: AsyncSession = Depends(get_db),
):
    """Download a file by artifact ID — admin portal auth."""
    from sqlalchemy import text as sql_text
    from fastapi.responses import FileResponse
    from pathlib import Path as FsPath
    import os

    row = await db.execute(
        sql_text("SELECT filename, file_path, file_type FROM artifacts WHERE id = :id"),
        {"id": file_id},
    )
    artifact = row.fetchone()
    if artifact is None or not artifact.file_path:
        from fastapi import HTTPException, status as http_status
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="File not found")

    file_path = artifact.file_path
    if not os.path.exists(file_path):
        from fastapi import HTTPException, status as http_status
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="File removed from storage")

    # Basic path traversal guard
    from app.context.artifact_manager import get_artifacts_dir
    resolved = FsPath(file_path).resolve()
    artifact_root = get_artifacts_dir().resolve()
    if not str(resolved).startswith(str(artifact_root)):
        from fastapi import HTTPException, status as http_status
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="File not found")

    # Map file_type to MIME (reuse same logic as files.py)
    mime_map = {
        "pdf": "application/pdf",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "xls": "application/vnd.ms-excel",
        "csv": "text/csv",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "txt": "text/plain",
        "md": "text/markdown",
        "json": "application/json",
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "mp4": "video/mp4",
        "mp3": "audio/mpeg",
    }
    mime = mime_map.get((artifact.file_type or "").lower(), "application/octet-stream")

    return FileResponse(
        path=file_path,
        filename=artifact.filename,
        media_type=mime,
    )


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

    # Send invite email via system sender (ai-assistant@mezzofy.com)
    try:
        from app.core.email_sender import send_transactional_email
        await send_transactional_email(
            to=body.email,
            subject="Welcome to Mezzofy AI Assistant",
            body_html=(
                f"<p>Hi {body.name},</p>"
                f"<p>You have been invited to Mezzofy AI Assistant.</p>"
                f"<p><strong>To activate your account:</strong></p>"
                f"<ol>"
                f"<li>Open the Mezzofy mobile app</li>"
                f"<li>Tap <em>Activate Account</em> on the login screen</li>"
                f"<li>Enter your activation code: <strong>{invite_token}</strong></li>"
                f"<li>Set a new password (minimum 8 characters)</li>"
                f"</ol>"
                f"<p>Your email: {body.email}</p>"
                f"<p>Best regards,<br/>Mezzofy Team</p>"
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


# ── Tasks ─────────────────────────────────────────────────────────────────────

@router.get("/tasks")
async def list_tasks(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
    current_user: dict = AdminUser,
    db: AsyncSession = Depends(get_db),
):
    """Paginated list of agent tasks with triggering user info."""
    offset = (page - 1) * per_page
    where_clause = ""
    params: dict = {"limit": per_page, "offset": offset}

    if status_filter:
        where_clause = "WHERE t.status = :status"
        params["status"] = status_filter

    result = await db.execute(
        text(f"""
            SELECT
                t.id, t.task_ref, t.session_id, t.content, t.status, t.department,
                t.progress, t.current_step,
                t.created_at, t.started_at, t.completed_at,
                EXTRACT(EPOCH FROM (t.completed_at - t.started_at)) * 1000 AS duration_ms,
                t.error, t.result AS details,
                u.email AS triggered_by_email,
                u.name AS triggered_by_name
            FROM agent_tasks t
            LEFT JOIN users u ON u.id = t.user_id
            {where_clause}
            ORDER BY t.created_at DESC
            LIMIT :limit OFFSET :offset
        """),
        params,
    )
    rows = result.fetchall()

    count_params = {}
    count_where = ""
    if status_filter:
        count_where = "WHERE status = :status"
        count_params["status"] = status_filter
    count_result = await db.execute(
        text(f"SELECT COUNT(*) FROM agent_tasks {count_where}"),
        count_params,
    )
    total = count_result.scalar() or 0

    # Batch-fetch token totals from llm_usage for all tasks in this page
    token_map: dict = {}
    task_ids = [str(r.id) for r in rows]
    if task_ids:
        try:
            token_result = await db.execute(
                text("""
                    SELECT
                        agtask.id::text                                                 AS task_id,
                        COALESCE(SUM(lu.input_tokens), 0)                              AS input_tokens,
                        COALESCE(SUM(lu.output_tokens), 0)                             AS output_tokens,
                        COALESCE(SUM(lu.input_tokens + lu.output_tokens), 0)           AS total_tokens,
                        STRING_AGG(DISTINCT lu.model, ', ' ORDER BY lu.model)          AS llm_model
                    FROM agent_tasks agtask
                    LEFT JOIN llm_usage lu ON lu.session_id::text = agtask.session_id
                    WHERE agtask.id::text = ANY(:task_ids)
                    GROUP BY agtask.id
                """).bindparams(bindparam("task_ids", type_=ARRAY(String))),
                {"task_ids": task_ids},
            )
            for tr in token_result.fetchall():
                token_map[str(tr.task_id)] = {
                    "input_tokens": int(tr.input_tokens),
                    "output_tokens": int(tr.output_tokens),
                    "total_tokens": int(tr.total_tokens),
                    "llm_model": tr.llm_model,
                }
        except Exception as _e:
            logger.warning(f"list_tasks: failed to fetch token totals: {_e}")

    tasks = []
    for r in rows:
        tid = str(r.id)
        tok = token_map.get(tid, {})
        tasks.append({
            "id": tid,
            "task_ref": r.task_ref,
            "content": r.content,
            "status": r.status,
            "department": r.department,
            "progress": r.progress,
            "current_step": r.current_step,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
            "duration_ms": round(r.duration_ms, 1) if r.duration_ms else None,
            "error": r.error,
            "triggered_by_email": r.triggered_by_email,
            "triggered_by_name": r.triggered_by_name,
            "details": r.details if isinstance(r.details, (dict, list, type(None))) else None,
            "total_tokens": tok.get("total_tokens", 0),
            "input_tokens": tok.get("input_tokens", 0),
            "output_tokens": tok.get("output_tokens", 0),
            "llm_model": tok.get("llm_model"),
        })

    return {
        "tasks": tasks,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page,
    }


@router.get("/tasks/stats")
async def get_task_stats(
    current_user: dict = AdminUser,
    db: AsyncSession = Depends(get_db),
):
    """Count agent tasks grouped by status."""
    result = await db.execute(
        text("SELECT status, COUNT(*) AS cnt FROM agent_tasks GROUP BY status")
    )
    rows = result.fetchall()
    stats = {"all": 0, "queued": 0, "running": 0, "completed": 0, "failed": 0, "cancelled": 0}
    for row in rows:
        if row.status in stats:
            stats[row.status] = int(row.cnt)
        stats["all"] += int(row.cnt)
    return stats


@router.get("/tasks/scheduled")
async def list_scheduled_tasks_admin(
    current_user: dict = AdminUser,
    db: AsyncSession = Depends(get_db),
):
    """List all scheduled jobs across all users (admin view)."""
    result = await db.execute(
        text("""
            SELECT sj.id, sj.name, sj.agent, sj.workflow_name, sj.schedule,
                   sj.next_run, sj.last_run, sj.is_active, sj.deliver_to,
                   u.email AS user_email, u.name AS user_name
            FROM scheduled_jobs sj
            LEFT JOIN users u ON u.id = sj.user_id
            ORDER BY sj.created_at DESC
        """)
    )
    rows = result.fetchall()
    return {
        "jobs": [
            {
                "id": str(r.id),
                "name": r.name,
                "agent": r.agent,
                "workflow_name": r.workflow_name,
                "schedule": r.schedule,
                "next_run": r.next_run.isoformat() if r.next_run else None,
                "last_run": r.last_run.isoformat() if r.last_run else None,
                "is_active": r.is_active,
                "deliver_to": r.deliver_to if isinstance(r.deliver_to, dict) else {},
                "user_email": r.user_email,
                "user_name": r.user_name,
            }
            for r in rows
        ]
    }


@router.post("/tasks/scheduled/{job_id}/run", status_code=status.HTTP_202_ACCEPTED)
async def run_scheduled_task_now(
    job_id: str,
    current_user: dict = AdminUser,
    db: AsyncSession = Depends(get_db),
):
    """Trigger a scheduled job immediately (admin). Enqueues a Celery task."""
    result = await db.execute(
        text(
            "SELECT id, name, agent, message, workflow_name, schedule, deliver_to, user_id "
            "FROM scheduled_jobs WHERE id = :id"
        ),
        {"id": job_id},
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Scheduled job not found")

    deliver_to = row.deliver_to if isinstance(row.deliver_to, dict) else {}
    task_data = {
        "agent": row.agent,
        "source": "scheduler",
        "department": row.agent,
        "user_id": str(row.user_id),
        "message": row.message,
        "workflow_name": row.workflow_name,
        "_job_name": row.name,
        "deliver_to": deliver_to,
        "_job_id": job_id,
        "input_type": "text",
        "permissions": ["all"],
        "attachments": [],
        "conversation_history": [],
    }

    from app.tasks.tasks import process_agent_task
    celery_task = process_agent_task.delay(task_data)

    from app.webhooks.scheduler import compute_next_run
    next_run_dt = compute_next_run(row.schedule)
    await db.execute(
        text("UPDATE scheduled_jobs SET last_run = NOW(), next_run = :next_run WHERE id = :id"),
        {"id": job_id, "next_run": next_run_dt},
    )
    await db.commit()

    logger.info(f"Admin {current_user.get('email')} triggered job {job_id} → Celery task {celery_task.id}")
    return {"task_id": celery_task.id, "status": "queued"}


@router.post("/tasks/scheduled/{job_id}/pause")
async def pause_scheduled_task(
    job_id: str,
    current_user: dict = AdminUser,
    db: AsyncSession = Depends(get_db),
):
    """Pause a scheduled job by setting is_active=False."""
    result = await db.execute(
        text("SELECT id FROM scheduled_jobs WHERE id = :id"),
        {"id": job_id},
    )
    if not result.fetchone():
        raise HTTPException(status_code=404, detail="Scheduled job not found")

    await db.execute(
        text("UPDATE scheduled_jobs SET is_active = FALSE WHERE id = :id"),
        {"id": job_id},
    )
    await db.commit()
    return {"id": job_id, "is_active": False}


@router.post("/tasks/scheduled/{job_id}/resume")
async def resume_scheduled_task(
    job_id: str,
    current_user: dict = AdminUser,
    db: AsyncSession = Depends(get_db),
):
    """Resume a paused scheduled job and recompute next_run."""
    result = await db.execute(
        text("SELECT id, schedule FROM scheduled_jobs WHERE id = :id"),
        {"id": job_id},
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Scheduled job not found")

    from app.webhooks.scheduler import compute_next_run
    next_run_dt = compute_next_run(row.schedule)
    await db.execute(
        text("UPDATE scheduled_jobs SET is_active = TRUE, next_run = :next_run WHERE id = :id"),
        {"id": job_id, "next_run": next_run_dt},
    )
    await db.commit()
    return {"id": job_id, "is_active": True, "next_run": next_run_dt.isoformat()}


@router.post("/tasks/{task_id}/kill")
async def kill_task(
    task_id: str,
    current_user: dict = AdminUser,
    db: AsyncSession = Depends(get_db),
):
    """Cancel a running agent task."""
    result = await db.execute(
        text("SELECT id, status FROM agent_tasks WHERE id = :id"),
        {"id": task_id},
    )
    task = result.fetchone()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status != "running":
        raise HTTPException(
            status_code=400,
            detail=f"Task is not running (status: {task.status})",
        )

    await db.execute(
        text("""
            UPDATE agent_tasks
            SET status = 'cancelled', completed_at = NOW(), error = 'Cancelled by admin'
            WHERE id = :id
        """),
        {"id": task_id},
    )

    await db.execute(
        text("""
            INSERT INTO audit_log (user_id, action, resource, details, success)
            VALUES (:uid, 'admin_kill_task', :resource, :details, TRUE)
        """),
        {
            "uid": current_user.get("user_id"),
            "resource": f"agent_tasks/{task_id}",
            "details": f'{{"task_id": "{task_id}", "admin": "{current_user.get("email")}"}}'
        },
    )
    await db.commit()
    return {"killed": True, "task_id": task_id}


@router.delete("/tasks/{task_id}")
async def delete_task(
    task_id: str,
    current_user: dict = AdminUser,
    db: AsyncSession = Depends(get_db),
):
    """Hard-delete a task from history and forget its Celery result."""
    result = await db.execute(
        text("SELECT id, task_ref FROM agent_tasks WHERE id = :id"),
        {"id": task_id},
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Task not found")

    # Forget Celery result to free result backend memory
    try:
        from celery.result import AsyncResult
        AsyncResult(row.task_ref).forget()
    except Exception:
        pass  # Non-fatal — result may already be expired

    await db.execute(
        text("DELETE FROM agent_tasks WHERE id = :id"),
        {"id": task_id},
    )
    await db.commit()

    logger.info(f"Admin {current_user.get('email')} deleted task {task_id}")
    return {"deleted": True, "task_id": task_id}


# ── Scheduler — Update Job ───────────────────────────────────────────────────

class UpdateJobRequest(BaseModel):
    name: Optional[str] = None
    schedule: Optional[str] = None
    agent: Optional[str] = None
    workflow_name: Optional[str] = None
    deliver_to: Optional[dict] = None


@router.put("/scheduler/jobs/{job_id}")
async def update_job(
    job_id: str,
    body: UpdateJobRequest,
    current_user: dict = AdminUser,
    db: AsyncSession = Depends(get_db),
):
    """Update a scheduled job's fields."""
    result = await db.execute(
        text("""
            SELECT sj.id, sj.name, sj.schedule, sj.agent, sj.workflow_name,
                   sj.deliver_to, sj.is_active, sj.last_run, sj.next_run,
                   sj.created_at, u.email AS user_email, u.name AS user_name
            FROM scheduled_jobs sj
            JOIN users u ON u.id = sj.user_id
            WHERE sj.id = :id
        """),
        {"id": job_id},
    )
    job = result.fetchone()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    import json as _json

    updates: dict = {}
    if body.name is not None:
        updates["name"] = body.name.strip()
    if body.agent is not None:
        updates["agent"] = body.agent.strip()
    if body.workflow_name is not None:
        updates["workflow_name"] = body.workflow_name.strip()
    if body.schedule is not None:
        from app.webhooks.scheduler import compute_next_run
        updates["schedule"] = body.schedule.strip()
        updates["next_run"] = compute_next_run(body.schedule.strip())
    if body.deliver_to is not None:
        updates["deliver_to"] = _json.dumps(body.deliver_to)

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    set_clauses = ", ".join(f"{k} = :{k}" for k in updates)
    updates["id"] = job_id
    await db.execute(
        text(f"UPDATE scheduled_jobs SET {set_clauses} WHERE id = :id"),
        updates,
    )

    await db.execute(
        text("""
            INSERT INTO audit_log (user_id, action, resource, details, success)
            VALUES (:uid, 'admin_update_job', :resource, :details, TRUE)
        """),
        {
            "uid": current_user.get("user_id"),
            "resource": f"scheduled_jobs/{job_id}",
            "details": _json.dumps({"job_id": job_id, "updated_fields": list(body.model_dump(exclude_none=True).keys())}),
        },
    )
    await db.commit()

    # Re-fetch updated job for response
    updated_result = await db.execute(
        text("""
            SELECT sj.id, sj.name, sj.schedule, sj.deliver_to,
                   sj.is_active, sj.last_run, sj.next_run,
                   sj.agent, sj.workflow_name, sj.created_at,
                   u.email AS user_email, u.name AS user_name
            FROM scheduled_jobs sj
            JOIN users u ON u.id = sj.user_id
            WHERE sj.id = :id
        """),
        {"id": job_id},
    )
    updated = updated_result.fetchone()
    return {
        "id": str(updated.id),
        "name": updated.name,
        "schedule": updated.schedule,
        "deliver_to": updated.deliver_to,
        "is_active": updated.is_active,
        "last_run": updated.last_run.isoformat() if updated.last_run else None,
        "next_run": updated.next_run.isoformat() if updated.next_run else None,
        "agent": updated.agent,
        "workflow_name": updated.workflow_name,
        "created_at": updated.created_at.isoformat() if updated.created_at else None,
        "user_email": updated.user_email,
        "user_name": updated.user_name,
    }


@router.delete("/scheduler/jobs/{job_id}")
async def delete_scheduler_job(
    job_id: str,
    current_user: dict = AdminUser,
    db: AsyncSession = Depends(get_db),
):
    """Delete a scheduled job (admin)."""
    try:
        result = await db.execute(
            text("SELECT id FROM scheduled_jobs WHERE id = :id"),
            {"id": job_id},
        )
        if not result.fetchone():
            raise HTTPException(status_code=404, detail="Scheduled job not found")

        await db.execute(
            text("DELETE FROM scheduled_jobs WHERE id = :id"),
            {"id": job_id},
        )
        await db.commit()
        return {"deleted": True, "job_id": job_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete scheduler job {job_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete scheduled job")


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


# ── CRM ──────────────────────────────────────────────────────────────────────

@router.get("/crm/countries")
async def get_crm_countries(
    current_user: dict = AdminUser,
    db: AsyncSession = Depends(get_db),
):
    """Get distinct non-null locations from sales_leads for country filter dropdown."""
    result = await db.execute(
        text("""
            SELECT DISTINCT location
            FROM sales_leads
            WHERE location IS NOT NULL AND location != ''
            ORDER BY location
        """)
    )
    rows = result.fetchall()
    return {"countries": [r.location for r in rows]}


@router.get("/crm/leads")
async def get_crm_leads(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
    search: Optional[str] = Query(None),
    assigned_to: Optional[str] = Query(None),
    country: Optional[str] = Query(None),
    current_user: dict = AdminUser,
    db: AsyncSession = Depends(get_db),
):
    """Paginated list of CRM leads with assignee info."""
    offset = (page - 1) * per_page
    filters = ["TRUE"]
    params: dict = {"limit": per_page, "offset": offset}

    if status_filter:
        filters.append("sl.status = :status")
        params["status"] = status_filter
    if search:
        filters.append("sl.company_name ILIKE :search")
        params["search"] = f"%{search}%"
    if assigned_to:
        filters.append("sl.assigned_to = :assigned_to")
        params["assigned_to"] = assigned_to
    if country:
        filters.append("sl.location ILIKE :country")
        params["country"] = f"%{country}%"

    where = " AND ".join(filters)

    result = await db.execute(
        text(f"""
            SELECT
                sl.id, sl.company_name, sl.contact_name, sl.contact_email,
                sl.contact_phone, sl.industry, sl.location, sl.source,
                sl.status, sl.notes, sl.created_at, sl.created_at AS updated_at,
                sl.follow_up_date, sl.last_contacted, NULL::text AS source_ref,
                sl.assigned_to,
                u.name AS assigned_to_name, u.email AS assigned_to_email
            FROM sales_leads sl
            LEFT JOIN users u ON u.id = sl.assigned_to
            WHERE {where}
            ORDER BY sl.created_at DESC
            LIMIT :limit OFFSET :offset
        """),
        params,
    )
    rows = result.fetchall()

    count_result = await db.execute(
        text(f"SELECT COUNT(*) FROM sales_leads sl WHERE {where}"),
        {k: v for k, v in params.items() if k not in ("limit", "offset")},
    )
    total = count_result.scalar() or 0

    leads = []
    for r in rows:
        leads.append({
            "id": str(r.id),
            "company_name": r.company_name,
            "contact_name": r.contact_name,
            "contact_email": r.contact_email,
            "contact_phone": r.contact_phone,
            "industry": r.industry,
            "location": r.location,
            "source": r.source,
            "status": r.status,
            "notes": r.notes,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            "follow_up_date": r.follow_up_date.isoformat() if r.follow_up_date else None,
            "last_contacted": r.last_contacted.isoformat() if r.last_contacted else None,
            "source_ref": r.source_ref,
            "assigned_to": str(r.assigned_to) if r.assigned_to else None,
            "assigned_to_name": r.assigned_to_name,
            "assigned_to_email": r.assigned_to_email,
        })

    return {
        "leads": leads,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page,
    }


@router.post("/crm/leads")
async def create_crm_lead(
    body: dict,
    current_user: dict = AdminUser,
    db: AsyncSession = Depends(get_db),
):
    """Create a new CRM lead."""
    import uuid as _uuid
    from datetime import datetime as _dt
    lead_id = str(_uuid.uuid4())
    now = _dt.utcnow()

    company_name = (body.get("company_name") or "").strip()
    if not company_name:
        raise HTTPException(status_code=400, detail="company_name is required")

    await db.execute(
        text("""
            INSERT INTO sales_leads
                (id, company_name, contact_name, contact_email, contact_phone,
                 industry, location, source, status, notes, lead_type, created_at)
            VALUES
                (:id, :company_name, :contact_name, :contact_email, :contact_phone,
                 :industry, :location, :source, :status, :notes, :lead_type, :created_at)
        """),
        {
            "id": lead_id,
            "company_name": company_name,
            "contact_name": body.get("contact_name"),
            "contact_email": body.get("contact_email"),
            "contact_phone": body.get("contact_phone"),
            "industry": body.get("industry"),
            "location": body.get("location"),
            "source": body.get("source") or "manual",
            "status": body.get("status") or "new",
            "notes": body.get("notes"),
            "lead_type": body.get("lead_type") or "buyer",
            "created_at": now,
        },
    )
    await db.commit()
    return {"id": lead_id, "created": True}


@router.patch("/crm/leads/{lead_id}")
async def update_crm_lead(
    lead_id: str,
    body: dict,
    current_user: dict = AdminUser,
    db: AsyncSession = Depends(get_db),
):
    """Update editable fields of a CRM lead."""
    allowed = {
        "company_name", "contact_name", "contact_email", "contact_phone",
        "industry", "location", "source", "status", "notes", "follow_up_date",
        "assigned_to", "lead_type",
    }
    updates = {k: v for k, v in body.items() if k in allowed}
    if not updates:
        raise HTTPException(status_code=400, detail="No valid fields to update")

    set_clause = ", ".join(f"{k} = :{k}" for k in updates)
    updates["lead_id"] = lead_id

    result = await db.execute(
        text(f"UPDATE sales_leads SET {set_clause} WHERE id::text = :lead_id"),
        updates,
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Lead not found")
    await db.commit()
    return {"updated": True}


@router.get("/crm/pipeline")
async def get_crm_pipeline(
    current_user: dict = AdminUser,
    db: AsyncSession = Depends(get_db),
):
    """Aggregate lead counts by status for pipeline view."""
    result = await db.execute(
        text("""
            SELECT status, COUNT(*) AS count
            FROM sales_leads
            GROUP BY status
            ORDER BY count DESC
        """)
    )
    rows = result.fetchall()

    pipeline = [{"status": r.status, "count": r.count} for r in rows]
    total = sum(item["count"] for item in pipeline)

    return {
        "pipeline": pipeline,
        "total": total,
    }


# ── WebSocket — Agent Office Live Feed ───────────────────────────────────────

@router.websocket("/ws")
async def admin_agent_office_ws(
    websocket: WebSocket,
    token: str = Query(...),
):
    """
    Real-time WebSocket stream for Mission Control Agent Office.

    Subscribes to the Redis "admin:agent-status" pub/sub channel and forwards
    every agent lifecycle event (queued → running → completed/failed) to the
    connected admin client.

    Auth: JWT passed as query parameter — /api/admin-portal/ws?token=<JWT>
    Admin role required (validated from JWT payload).

    Server → Client messages:
      {"type": "agent_status", "department": "...", "status": "queued|running|completed|failed",
       "task_title": "...", "agent_task_id": "..."}
    """
    # 1. Validate JWT and require admin role
    try:
        payload = decode_access_token(token)
        user_id = payload.get("user_id") or payload.get("sub")
        role = payload.get("role", "")
        if not user_id or role != "admin":
            await websocket.close(code=1008)
            return
    except Exception:
        await websocket.close(code=1008)
        return

    await websocket.accept()
    logger.info(f"admin_agent_office_ws: admin user_id={user_id} connected")

    # 2. Subscribe to Redis channel
    import redis.asyncio as aioredis
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    r = aioredis.from_url(redis_url)
    pubsub = r.pubsub()
    await pubsub.subscribe("admin:agent-status")

    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                data = message["data"]
                if isinstance(data, bytes):
                    data = data.decode()
                await websocket.send_text(data)
    except WebSocketDisconnect:
        logger.info(f"admin_agent_office_ws: admin user_id={user_id} disconnected")
    except Exception as e:
        logger.warning(f"admin_agent_office_ws: error for user_id={user_id}: {e}")
    finally:
        try:
            await pubsub.unsubscribe("admin:agent-status")
            await r.aclose()
        except Exception:
            pass
