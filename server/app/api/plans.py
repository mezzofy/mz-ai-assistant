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
