"""
Core Celery Tasks — background task definitions for mz-ai-assistant.

Tasks:
    process_agent_task(task_data)  — Run an agent workflow as a background job.
                                     Used for: scheduled reports, long video processing,
                                     batch email outreach, webhook-triggered workflows.
    health_check()                 — Periodic system health check (every 5 minutes).

Celery workers run in separate processes; async agent code is called via asyncio.run().
"""

import asyncio
import logging

from app.tasks.celery_app import celery_app

logger = logging.getLogger("mezzofy.tasks.core")


# ── Main background task ───────────────────────────────────────────────────────

@celery_app.task(bind=True, max_retries=3, name="app.tasks.tasks.process_agent_task")
def process_agent_task(self, task_data: dict):
    """
    Execute an agent workflow as a Celery background task.

    Used for: scheduled reports, long-running agent workflows, batch operations.
    Delivers results via Teams/email/push based on task_data["deliver_to"].

    Args:
        task_data: Standard task dict with keys:
            - agent:       Agent name ("sales", "finance", etc.)
            - message:     Natural language task description
            - deliver_to:  {"teams_channel": "sales", "email": ["ceo@co.com"]}
            - user_id:     (optional) User to notify via WebSocket / push
            - department:  Department context
            - source:      "scheduler" | "webhook" (affects permission bypass)
    """
    try:
        result = asyncio.run(_run_agent_task(task_data))
        logger.info(
            f"process_agent_task completed: agent={task_data.get('agent')!r} "
            f"user={task_data.get('user_id')!r}"
        )
        return result
    except Exception as exc:
        logger.error(f"process_agent_task failed: {exc}", exc_info=True)
        raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))


async def _run_agent_task(task_data: dict) -> dict:
    """Async core for process_agent_task: run agent + deliver results."""
    from app.core.config import get_config
    from app.agents.agent_registry import get_agent_for_task, AGENT_MAP

    config = get_config()
    task_data["_config"] = config

    # Ensure source is set (enables permission bypass for system tasks)
    if not task_data.get("source"):
        task_data["source"] = "scheduler"

    # Fill in defaults if caller didn't set them
    task_data.setdefault("input_type", "text")
    task_data.setdefault("permissions", ["all"])
    task_data.setdefault("attachments", [])
    task_data.setdefault("conversation_history", [])

    # Get agent — try by explicit name first, then auto-detect
    agent_name = task_data.get("agent", "")
    agent = AGENT_MAP.get(agent_name) if agent_name else get_agent_for_task(task_data, config)

    if agent is None:
        logger.warning(f"No agent found for task (agent={agent_name!r})")
        return {
            "success": False,
            "content": f"Agent {agent_name!r} not available",
            "agent_used": "none",
        }

    # Execute agent
    result = await agent.execute(task_data)

    # Store result in scheduled_jobs.last_run if this is a scheduled job
    job_id = task_data.get("_job_id")
    if job_id:
        await _update_job_last_run(job_id)

    # Deliver results if configured
    deliver_to = task_data.get("deliver_to") or {}
    if deliver_to:
        from app.tasks.webhook_tasks import _deliver_results_async
        await _deliver_results_async(result, deliver_to, config)

    return result


async def _update_job_last_run(job_id: str):
    """Update scheduled_jobs.last_run timestamp after successful execution."""
    try:
        from app.core.database import AsyncSessionLocal
        from sqlalchemy import text

        async with AsyncSessionLocal() as db:
            await db.execute(
                text("UPDATE scheduled_jobs SET last_run = NOW() WHERE id = :id"),
                {"id": job_id},
            )
            await db.commit()
    except Exception as e:
        logger.warning(f"Failed to update job last_run (id={job_id}): {e}")


# ── Health check task ──────────────────────────────────────────────────────────

@celery_app.task(name="app.tasks.tasks.health_check")
def health_check():
    """
    Periodic system health check task — runs every 5 minutes via Celery Beat.

    Checks: PostgreSQL, Redis connectivity, LLM manager status.
    Logs results; does NOT raise exceptions (task must succeed to be rescheduled).
    """
    results = {}

    # PostgreSQL
    try:
        asyncio.run(_check_db())
        results["database"] = "ok"
    except Exception as e:
        results["database"] = f"FAIL: {e}"
        logger.error(f"Health check DB failed: {e}")

    # Redis (via celery backend — already connected if this task ran)
    results["celery_worker"] = "ok"

    # LLM manager
    try:
        from app.llm import llm_manager as llm_mod
        llm_mod.get()
        results["llm_manager"] = "ok"
    except Exception as e:
        results["llm_manager"] = f"not_initialized: {e}"
        logger.warning(f"Health check LLM: {e}")

    status = "ok" if all(v == "ok" for v in results.values()) else "degraded"
    logger.info(f"System health: {status} — {results}")
    return {"status": status, "services": results}


async def _check_db():
    """Async DB ping used by health_check."""
    from app.core.database import check_db_connection
    ok = await check_db_connection()
    if not ok:
        raise RuntimeError("DB connection check failed")
