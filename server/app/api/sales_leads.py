"""
Sales Leads API — CRUD + automation trigger endpoints.

Prefix:  /sales/leads   (registered in main.py)
Auth:    JWT required on all endpoints

RBAC:
  sales_read   — GET endpoints (all sales staff)
  sales_write  — PATCH endpoints (reps: own leads; managers: all)
  sales_admin  — POST/bulk (managers+) + digest preview

Endpoints:
  GET    /sales/leads                   — list with filters
  GET    /sales/leads/{lead_id}         — single lead detail
  PATCH  /sales/leads/{lead_id}/status  — update status + remarks
  PATCH  /sales/leads/{lead_id}/assign  — assign to PIC (admin)
  POST   /sales/leads/research          — enqueue research task (admin)
  GET    /sales/leads/digest/preview    — preview CRM digest (admin)
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import (
    get_current_user,
    get_db,
    require_permission,
)

router = APIRouter(tags=["sales-leads"])
logger = logging.getLogger("mezzofy.api.sales_leads")


# ── Request / Response DTOs ───────────────────────────────────────────────────

class StatusUpdateRequest(BaseModel):
    new_status: str
    remarks: Optional[str] = None


class AssignRequest(BaseModel):
    assign_to: str


class ResearchRequest(BaseModel):
    targets: Optional[list[dict]] = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _serialize_row(row: dict) -> dict:
    """Convert datetime fields to ISO strings."""
    result = {}
    for k, v in row.items():
        if hasattr(v, "isoformat"):
            result[k] = v.isoformat()
        else:
            result[k] = v
    return result


def _is_manager(user: dict) -> bool:
    return user.get("role") in ("manager", "admin", "executive") or "*" in user.get("permissions", [])


# ── GET /sales/leads ──────────────────────────────────────────────────────────

@router.get("/sales/leads")
async def list_leads(
    status_filter: Optional[str] = Query(None, alias="status"),
    assigned_to: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    since: Optional[str] = Query(None, description="ISO datetime (e.g. 2026-03-01T00:00:00)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(require_permission("sales_read")),
    db: AsyncSession = Depends(get_db),
):
    """List sales leads with optional filters. Reps see only their own leads."""
    user_id = current_user.get("user_id")
    is_mgr = _is_manager(current_user)

    conditions = []
    params: dict = {"offset": (page - 1) * page_size, "limit": page_size}

    # Reps are scoped to their own leads
    if not is_mgr:
        conditions.append("sl.assigned_to = :user_id")
        params["user_id"] = user_id
    elif assigned_to:
        conditions.append("sl.assigned_to = :assigned_to")
        params["assigned_to"] = assigned_to

    if status_filter:
        conditions.append("sl.status = :status")
        params["status"] = status_filter
    if source:
        conditions.append("sl.source = :source")
        params["source"] = source
    if since:
        conditions.append("sl.created_at >= :since")
        params["since"] = since

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    count_sql = text(f"SELECT COUNT(*) FROM sales_leads sl {where}")
    data_sql = text(f"""
        SELECT sl.id, sl.company_name, sl.contact_name, sl.contact_email,
               sl.industry, sl.source, sl.status, sl.assigned_to,
               sl.notes, sl.created_at, sl.updated_at, sl.last_contacted,
               sl.follow_up_date, sl.source_ref, sl.last_status_update,
               u.name AS pic_name
        FROM sales_leads sl
        LEFT JOIN users u ON sl.assigned_to = u.id
        {where}
        ORDER BY sl.created_at DESC
        LIMIT :limit OFFSET :offset
    """)

    total = (await db.execute(count_sql, params)).scalar_one()
    rows = [_serialize_row(dict(r)) for r in (await db.execute(data_sql, params)).mappings().all()]

    return {"leads": rows, "total": total, "page": page, "page_size": page_size}


# ── GET /sales/leads/digest/preview ──────────────────────────────────────────
# NOTE: This must be defined BEFORE /sales/leads/{lead_id} to avoid FastAPI
# treating "digest" as a lead_id path segment.

@router.get("/sales/leads/digest/preview")
async def digest_preview(
    current_user: dict = Depends(require_permission("sales_admin")),
):
    """Return the data the daily digest would send, without sending emails/Teams."""
    from app.tasks.sales_lead_tasks import _daily_crm_digest_async

    try:
        data = await _daily_crm_digest_async(run_id="preview", preview_only=True)
        return data
    except Exception as e:
        logger.error(f"digest_preview failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── GET /sales/leads/{lead_id} ────────────────────────────────────────────────

@router.get("/sales/leads/{lead_id}")
async def get_lead(
    lead_id: str,
    current_user: dict = Depends(require_permission("sales_read")),
    db: AsyncSession = Depends(get_db),
):
    """Get a single lead. Reps can only fetch their own leads."""
    row = (await db.execute(
        text("""
            SELECT sl.id, sl.company_name, sl.contact_name, sl.contact_email,
                   sl.contact_phone, sl.industry, sl.location, sl.source, sl.source_ref,
                   sl.status, sl.assigned_to, sl.notes, sl.created_at, sl.updated_at,
                   sl.last_contacted, sl.follow_up_date, sl.last_status_update,
                   u.name AS pic_name, u.email AS pic_email
            FROM sales_leads sl
            LEFT JOIN users u ON sl.assigned_to = u.id
            WHERE sl.id = :id
        """),
        {"id": lead_id},
    )).mappings().one_or_none()

    if row is None:
        raise HTTPException(status_code=404, detail="Lead not found")

    lead = _serialize_row(dict(row))

    if not _is_manager(current_user):
        user_id = current_user.get("user_id")
        if str(lead.get("assigned_to")) != str(user_id):
            raise HTTPException(status_code=403, detail="Access denied — not your lead")

    return lead


# ── PATCH /sales/leads/{lead_id}/status ───────────────────────────────────────

@router.patch("/sales/leads/{lead_id}/status")
async def update_lead_status(
    lead_id: str,
    body: StatusUpdateRequest,
    current_user: dict = Depends(require_permission("sales_write")),
    db: AsyncSession = Depends(get_db),
):
    """Update lead status with transition validation. Reps can only update own leads."""
    from app.core.config import get_config
    from app.tools.database.crm_ops import CRMOps

    user_id = str(current_user.get("user_id", ""))

    # Check lead exists + scope for reps
    row = (await db.execute(
        text("SELECT id, assigned_to FROM sales_leads WHERE id = :id"),
        {"id": lead_id},
    )).mappings().one_or_none()

    if row is None:
        raise HTTPException(status_code=404, detail="Lead not found")

    if not _is_manager(current_user):
        if str(row["assigned_to"]) != user_id:
            raise HTTPException(status_code=403, detail="Access denied — not your lead")

    config = get_config()
    crm = CRMOps(config)
    result = await crm.update_lead_status(
        lead_id=lead_id,
        new_status=body.new_status,
        remarks=body.remarks,
        updated_by=user_id,
    )

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Update failed"))

    return result["output"]


# ── PATCH /sales/leads/{lead_id}/assign ──────────────────────────────────────

@router.patch("/sales/leads/{lead_id}/assign")
async def assign_lead(
    lead_id: str,
    body: AssignRequest,
    current_user: dict = Depends(require_permission("sales_admin")),
    db: AsyncSession = Depends(get_db),
):
    """Assign a lead to a PIC. Managers+ only."""
    result = await db.execute(
        text(
            "UPDATE sales_leads SET assigned_to = :assign_to "
            "WHERE id = :id RETURNING id, assigned_to"
        ),
        {"assign_to": body.assign_to, "id": lead_id},
    )
    await db.commit()
    row = result.mappings().one_or_none()

    if row is None:
        raise HTTPException(status_code=404, detail="Lead not found")

    logger.info(f"Lead {lead_id} assigned to {body.assign_to} by {current_user.get('user_id')}")
    return {"lead_id": lead_id, "assigned_to": body.assign_to}


# ── POST /sales/leads/research ────────────────────────────────────────────────

@router.post("/sales/leads/research", status_code=status.HTTP_202_ACCEPTED)
async def trigger_research(
    body: ResearchRequest = ResearchRequest(),
    current_user: dict = Depends(require_permission("sales_admin")),
):
    """Manually enqueue the lead research task. Returns immediately with task_id."""
    from app.tasks.sales_lead_tasks import research_new_leads

    kwargs = {}
    if body.targets:
        kwargs["targets"] = body.targets

    task = research_new_leads.apply_async(kwargs=kwargs, queue="sales")
    logger.info(
        f"Lead research task enqueued: task_id={task.id} by user={current_user.get('user_id')}"
    )
    return {"task_id": task.id, "status": "queued"}
