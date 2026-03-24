"""
Plans API — Read-only endpoints for inspecting ExecutionPlan records.

All plans are stored in Redis DB3 by PlanManager. These endpoints provide
visibility into the PLAN→DELEGATE→AGGREGATE pipeline for the admin portal.

Endpoints:
    GET /api/plans                          → list plans
    GET /api/plans/stats                    → plan statistics (declared BEFORE {plan_id})
    GET /api/plans/{plan_id}                → full plan detail
    GET /api/plans/{plan_id}/steps/{step_id} → single step detail

Auth: admin role required (same as admin_portal.py).
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.dependencies import require_role

logger = logging.getLogger("mezzofy.api.plans")

router = APIRouter(tags=["plans"])
AdminUser = Depends(require_role("admin"))


# ── GET /api/plans ─────────────────────────────────────────────────────────────

@router.get("/plans")
async def list_plans(
    user_id: Optional[str] = Query(None, description="Filter by user_id"),
    plan_status: Optional[str] = Query(None, alias="status", description="Filter by plan status"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: dict = AdminUser,
):
    """
    List execution plans.

    Returns plan summaries from Redis DB3. Optionally filter by user_id and status.
    Supports pagination via limit and offset.
    """
    from app.orchestrator.plan_manager import plan_manager
    from app.core.database import engine
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy import text

    try:
        plans = plan_manager.list_plans(user_id=user_id, limit=limit + offset)
    except Exception as e:
        logger.error(f"list_plans: Redis error: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to read plans from Redis: {e}",
        )

    # Filter by status if requested
    if plan_status:
        plans = [p for p in plans if p.get("status") == plan_status.upper()]

    # Apply offset
    plans = plans[offset:]

    # Batch-fetch token totals from llm_usage for all plans with a session_id
    token_map: dict = {}
    session_ids = [p["session_id"] for p in plans if p.get("session_id")]
    if session_ids:
        try:
            async with AsyncSession(engine) as db_session:
                token_result = await db_session.execute(
                    text("""
                        SELECT
                            session_id,
                            COALESCE(SUM(input_tokens), 0)                            AS input_tokens,
                            COALESCE(SUM(output_tokens), 0)                           AS output_tokens,
                            COALESCE(SUM(input_tokens + output_tokens), 0)            AS total_tokens,
                            STRING_AGG(DISTINCT model, ', ' ORDER BY model)           AS llm_model
                        FROM llm_usage
                        WHERE session_id = ANY(:session_ids)
                        GROUP BY session_id
                    """),
                    {"session_ids": session_ids},
                )
                for tr in token_result.fetchall():
                    token_map[tr.session_id] = {
                        "input_tokens": int(tr.input_tokens),
                        "output_tokens": int(tr.output_tokens),
                        "total_tokens": int(tr.total_tokens),
                        "llm_model": tr.llm_model,
                    }
        except Exception as e:
            logger.warning(f"list_plans: failed to fetch token totals: {e}")

    # Merge token totals into each plan dict
    for plan in plans:
        sid = plan.get("session_id")
        tok = token_map.get(sid, {}) if sid else {}
        plan["total_tokens"] = tok.get("total_tokens", 0)
        plan["input_tokens"] = tok.get("input_tokens", 0)
        plan["output_tokens"] = tok.get("output_tokens", 0)
        plan["llm_model"] = tok.get("llm_model")

    return {
        "plans": plans,
        "total": len(plans),
        "limit": limit,
        "offset": offset,
    }


# ── GET /api/plans/stats ───────────────────────────────────────────────────────
# IMPORTANT: Declared BEFORE /api/plans/{plan_id} to prevent FastAPI from
# treating "stats" as a plan_id path parameter.

@router.get("/plans/stats")
async def get_plan_stats(
    user_id: Optional[str] = Query(None, description="Filter stats by user_id"),
    current_user: dict = AdminUser,
):
    """
    Plan statistics: total count and breakdown by status.
    """
    from app.orchestrator.plan_manager import plan_manager

    try:
        all_plans = plan_manager.list_plans(user_id=user_id, limit=10000)
    except Exception as e:
        logger.error(f"get_plan_stats: Redis error: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to read plans from Redis: {e}",
        )

    by_status: dict = {}
    for p in all_plans:
        s = p.get("status", "UNKNOWN")
        by_status[s] = by_status.get(s, 0) + 1

    return {
        "total": len(all_plans),
        "by_status": by_status,
    }


# ── GET /api/plans/{plan_id} ───────────────────────────────────────────────────

@router.get("/plans/{plan_id}")
async def get_plan(
    plan_id: str,
    current_user: dict = AdminUser,
):
    """
    Full plan detail including all steps, shared context, and final output.
    """
    from app.orchestrator.plan_manager import plan_manager
    from dataclasses import asdict

    try:
        plan = plan_manager.load_plan(plan_id)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plan not found: {plan_id}",
        )
    except Exception as e:
        logger.error(f"get_plan: Redis error for plan_id={plan_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to load plan: {e}",
        )

    return asdict(plan)


# ── GET /api/plans/{plan_id}/steps/{step_id} ──────────────────────────────────

@router.get("/plans/{plan_id}/steps/{step_id}")
async def get_plan_step(
    plan_id: str,
    step_id: str,
    current_user: dict = AdminUser,
):
    """
    Single step detail — includes output, review, retry history.
    """
    from app.orchestrator.plan_manager import plan_manager
    from dataclasses import asdict

    try:
        plan = plan_manager.load_plan(plan_id)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plan not found: {plan_id}",
        )
    except Exception as e:
        logger.error(f"get_plan_step: Redis error: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to load plan: {e}",
        )

    step = next((s for s in plan.steps if s.step_id == step_id), None)
    if step is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Step {step_id!r} not found in plan {plan_id}",
        )

    return asdict(step)


# ── POST /api/plans/{plan_id}/kill ────────────────────────────────────────────

@router.post("/plans/{plan_id}/kill")
async def kill_plan(plan_id: str, _: dict = AdminUser):
    """
    Kill an IN_PROGRESS plan: revoke all running Celery tasks, mark all
    non-completed steps as FAILED, and set the plan status to FAILED.
    """
    import json as _json
    import os as _os
    import redis as _redis
    from datetime import datetime as _datetime
    from urllib.parse import urlparse as _urlparse, urlunparse as _urlunparse
    from app.tasks.celery_app import celery_app as _celery_app

    # Connect to Redis DB3 (same pattern as cleanup_stuck_plans)
    redis_url = (
        _os.getenv("REDIS_URL")
        or "redis://localhost:6379"
    )
    _parsed = _urlparse(redis_url)
    base_url = _urlunparse(_parsed._replace(path=""))
    r = _redis.Redis(host=_parsed.hostname or "localhost",
                     port=_parsed.port or 6379,
                     db=3,
                     decode_responses=True)

    raw = r.get(f"mz:plan:{plan_id}")
    if not raw:
        raise HTTPException(status_code=404, detail=f"Plan {plan_id} not found")

    plan = _json.loads(raw)

    if plan.get("status") != "IN_PROGRESS":
        raise HTTPException(
            status_code=400,
            detail=f"Plan is not in progress (status: {plan.get('status')})"
        )

    now = _datetime.utcnow().isoformat()
    steps_cancelled = 0

    for step in plan.get("steps", []):
        if step.get("status") == "STARTED":
            celery_task_id = step.get("celery_task_id")
            if celery_task_id:
                try:
                    _celery_app.control.revoke(celery_task_id, terminate=True)
                    logger.info(f"kill_plan: revoked celery task {celery_task_id} for step {step['step_id']} in plan {plan_id}")
                except Exception as rev_err:
                    logger.warning(f"kill_plan: failed to revoke celery task {celery_task_id}: {rev_err}")

        if step.get("status") not in ("COMPLETED",):
            step["status"] = "FAILED"
            step["error"] = "Killed by admin"
            step["completed_at"] = now
            steps_cancelled += 1

    plan["status"] = "FAILED"
    plan["completed_at"] = now
    r.set(f"mz:plan:{plan_id}", _json.dumps(plan))

    logger.info(f"kill_plan: plan {plan_id} killed by admin — {steps_cancelled} steps cancelled")

    return {
        "status": "killed",
        "plan_id": plan_id,
        "steps_cancelled": steps_cancelled,
    }
