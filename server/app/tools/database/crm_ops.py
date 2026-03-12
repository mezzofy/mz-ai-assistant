"""
CRM Tool — sales lead CRUD operations against the sales_leads PostgreSQL table.

Tools provided:
    create_lead    — Insert a new lead into sales_leads
    update_lead    — Update lead status, notes, or follow-up date
    search_leads   — Search leads by company, status, industry, or assignee
    get_lead       — Fetch a single lead by ID
    export_leads   — Export matching leads as CSV bytes
    get_pipeline   — Aggregate pipeline summary grouped by status or assignee
    get_stale_leads — Return leads whose follow_up_date is overdue

Access control (enforced by caller via RBAC):
    Sales reps    — see only leads assigned to themselves (assigned_to = user_id)
    Sales managers — see all leads
    Management    — read-only pipeline summaries

Mutations (create_lead, update_lead) are logged to audit_log.

Library: SQLAlchemy async (existing dependency), pandas (for CSV export)
"""

import logging
import uuid
from typing import Any, Optional

from app.tools.base_tool import BaseTool

logger = logging.getLogger("mezzofy.tools.crm")

# Allowed lead status values
_VALID_STATUSES = {
    "new", "contacted", "qualified", "proposal",
    "closed_won", "closed_lost", "disqualified",
}

# Allowed lead sources (expanded for automation)
_VALID_SOURCES = {
    "linkedin", "website", "referral", "event", "manual",
    "email", "ticket", "web",
}

# Valid status transitions
_STATUS_TRANSITIONS: dict[str, set[str]] = {
    "new":       {"contacted", "disqualified"},
    "contacted": {"qualified", "closed_lost", "disqualified"},
    "qualified": {"proposal", "closed_lost", "disqualified"},
    "proposal":  {"closed_won", "closed_lost"},
}


class CRMOps(BaseTool):

    def get_tools(self) -> list[dict]:
        return [
            {
                "name": "create_lead",
                "description": (
                    "Add a new sales lead to the CRM database. "
                    "Records company name, contact details, industry, source, and assigned rep. "
                    "Returns the new lead's UUID."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "company_name": {
                            "type": "string",
                            "description": "Name of the prospect company",
                        },
                        "contact_email": {
                            "type": "string",
                            "description": "Primary contact email address",
                        },
                        "contact_name": {
                            "type": "string",
                            "description": "Primary contact person's name",
                        },
                        "industry": {
                            "type": "string",
                            "description": "Industry sector, e.g. 'F&B', 'Retail', 'Hospitality'",
                        },
                        "source": {
                            "type": "string",
                            "description": "Lead source: linkedin | website | referral | event | manual",
                        },
                        "assigned_to": {
                            "type": "string",
                            "description": "User ID of the sales rep assigned to this lead",
                        },
                        "contact_phone": {
                            "type": "string",
                            "description": "Contact phone number (optional)",
                        },
                        "location": {
                            "type": "string",
                            "description": "City/country, e.g. 'Singapore' (optional)",
                        },
                        "notes": {
                            "type": "string",
                            "description": "Initial notes or context about this lead (optional)",
                        },
                    },
                    "required": [
                        "company_name",
                        "contact_email",
                        "contact_name",
                        "industry",
                        "source",
                        "assigned_to",
                    ],
                },
                "handler": self._create_lead,
            },
            {
                "name": "update_lead",
                "description": (
                    "Update an existing lead's status, notes, or follow-up date. "
                    "At least one of status, notes, or follow_up_date must be provided."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "lead_id": {
                            "type": "string",
                            "description": "UUID of the lead to update",
                        },
                        "status": {
                            "type": "string",
                            "description": (
                                "New status: new | contacted | qualified | "
                                "proposal | closed_won | closed_lost"
                            ),
                        },
                        "notes": {
                            "type": "string",
                            "description": "Updated notes (replaces existing notes)",
                        },
                        "follow_up_date": {
                            "type": "string",
                            "description": "Next follow-up date/time (ISO 8601, e.g. 2026-03-15T09:00:00)",
                        },
                        "updated_by": {
                            "type": "string",
                            "description": "User ID making the update (for audit log)",
                        },
                    },
                    "required": ["lead_id"],
                },
                "handler": self._update_lead,
            },
            {
                "name": "search_leads",
                "description": (
                    "Search sales leads by company name, status, industry, or assigned rep. "
                    "Sales reps should pass their own user_id as assigned_to to enforce data scoping."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "company": {
                            "type": "string",
                            "description": "Company name (partial match, case-insensitive)",
                        },
                        "status": {
                            "type": "string",
                            "description": "Filter by status: new | contacted | qualified | proposal | closed_won | closed_lost",
                        },
                        "industry": {
                            "type": "string",
                            "description": "Filter by industry sector",
                        },
                        "assigned_to": {
                            "type": "string",
                            "description": "Filter by assigned user ID (pass own user_id for reps)",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Max leads to return (default: 20, max: 100)",
                            "default": 20,
                        },
                    },
                    "required": [],
                },
                "handler": self._search_leads,
            },
            {
                "name": "get_lead",
                "description": "Get full details for a single sales lead by its UUID.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "lead_id": {
                            "type": "string",
                            "description": "UUID of the lead",
                        },
                    },
                    "required": ["lead_id"],
                },
                "handler": self._get_lead,
            },
            {
                "name": "export_leads",
                "description": (
                    "Export sales leads matching optional filters as a CSV file. "
                    "Returns base64-encoded CSV bytes and row count."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "status": {
                            "type": "string",
                            "description": "Filter by status (optional)",
                        },
                        "assigned_to": {
                            "type": "string",
                            "description": "Filter by assigned user ID (optional)",
                        },
                        "industry": {
                            "type": "string",
                            "description": "Filter by industry (optional)",
                        },
                    },
                    "required": [],
                },
                "handler": self._export_leads,
            },
            {
                "name": "get_pipeline",
                "description": (
                    "Get a sales pipeline summary — lead counts and list per stage. "
                    "Can group by status (default) or by assigned rep."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "group_by": {
                            "type": "string",
                            "description": "Group dimension: 'status' (default) or 'assigned_to'",
                            "default": "status",
                        },
                    },
                    "required": [],
                },
                "handler": self._get_pipeline,
            },
            {
                "name": "get_stale_leads",
                "description": (
                    "Return leads whose follow_up_date is today or earlier (overdue). "
                    "Used by the scheduled daily follow-up job."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "days_overdue": {
                            "type": "integer",
                            "description": "Return leads overdue by at least N days (default: 0 = any overdue)",
                            "default": 0,
                        },
                        "assigned_to": {
                            "type": "string",
                            "description": "Limit to a specific rep's leads (optional)",
                        },
                    },
                    "required": [],
                },
                "handler": self._get_stale_leads,
            },
        ]

    # ── Private helpers ────────────────────────────────────────────────────────

    async def _get_session(self):
        """Return a new async DB session from the shared pool."""
        from app.core.database import AsyncSessionLocal
        return AsyncSessionLocal()

    async def _log_audit(
        self,
        user_id: str,
        action: str,
        resource: str,
        details: Optional[dict] = None,
        success: bool = True,
        error_message: Optional[str] = None,
    ) -> None:
        """Fire-and-forget audit log — never raises."""
        try:
            from app.core.audit import log_action
            from app.core.database import AsyncSessionLocal

            async with AsyncSessionLocal() as audit_session:
                await log_action(
                    db=audit_session,
                    user_id=user_id,
                    action=action,
                    resource=resource,
                    details=details,
                    success=success,
                    error_message=error_message,
                )
        except Exception:
            pass  # Audit failures are non-fatal

    # ── Handlers ──────────────────────────────────────────────────────────────

    async def _create_lead(
        self,
        company_name: str,
        contact_email: str,
        contact_name: str,
        industry: str,
        source: str,
        assigned_to: str,
        contact_phone: Optional[str] = None,
        location: Optional[str] = None,
        notes: Optional[str] = None,
        source_ref: Optional[str] = None,
    ) -> dict:
        # Validate source
        if source not in _VALID_SOURCES:
            return self._err(
                f"Invalid source '{source}'. Must be one of: {', '.join(sorted(_VALID_SOURCES))}"
            )

        try:
            from sqlalchemy import text

            sql = """
                INSERT INTO sales_leads
                    (company_name, contact_name, contact_email, contact_phone,
                     industry, location, source, source_ref, status, assigned_to, notes)
                VALUES
                    (:company_name, :contact_name, :contact_email, :contact_phone,
                     :industry, :location, :source, :source_ref, 'new', :assigned_to, :notes)
                RETURNING id
            """
            params: dict[str, Any] = {
                "company_name": company_name,
                "contact_name": contact_name,
                "contact_email": contact_email,
                "contact_phone": contact_phone,
                "industry": industry,
                "location": location,
                "source": source,
                "source_ref": source_ref,
                "assigned_to": assigned_to,
                "notes": notes,
            }

            async with await self._get_session() as session:
                result = await session.execute(text(sql), params)
                await session.commit()
                lead_id = str(result.scalar_one())

            logger.info(f"create_lead: new lead {lead_id} for {company_name}")
            await self._log_audit(
                user_id=assigned_to,
                action="lead_created",
                resource="crm",
                details={"lead_id": lead_id, "company_name": company_name, "source": source},
            )
            return self._ok({"lead_id": lead_id, "company_name": company_name, "status": "new"})
        except Exception as e:
            logger.error(f"create_lead failed: {e}")
            await self._log_audit(
                user_id=assigned_to,
                action="lead_created",
                resource="crm",
                success=False,
                error_message=str(e),
            )
            return self._err(f"Failed to create lead: {e}")

    async def _update_lead(
        self,
        lead_id: str,
        status: Optional[str] = None,
        notes: Optional[str] = None,
        follow_up_date: Optional[str] = None,
        updated_by: Optional[str] = None,
    ) -> dict:
        if not any([status, notes, follow_up_date]):
            return self._err("At least one of status, notes, or follow_up_date must be provided")

        if status and status not in _VALID_STATUSES:
            return self._err(
                f"Invalid status '{status}'. Must be one of: {', '.join(sorted(_VALID_STATUSES))}"
            )

        try:
            from sqlalchemy import text

            set_clauses = ["updated_at = NOW()"]
            params: dict[str, Any] = {"lead_id": lead_id}

            if status:
                set_clauses.append("status = :status")
                params["status"] = status
            if notes is not None:
                set_clauses.append("notes = :notes")
                params["notes"] = notes
            if follow_up_date:
                set_clauses.append("follow_up_date = :follow_up_date")
                params["follow_up_date"] = follow_up_date
            if status in ("contacted", "qualified", "proposal"):
                set_clauses.append("last_contacted = NOW()")

            sql = (
                f"UPDATE sales_leads SET {', '.join(set_clauses)} "
                f"WHERE id = :lead_id RETURNING id"
            )

            async with await self._get_session() as session:
                result = await session.execute(text(sql), params)
                await session.commit()
                updated = result.scalar_one_or_none()

            if not updated:
                return self._err(f"Lead '{lead_id}' not found")

            logger.info(f"update_lead: {lead_id} updated (status={status})")
            await self._log_audit(
                user_id=updated_by or "system",
                action="lead_updated",
                resource="crm",
                details={"lead_id": lead_id, "status": status, "follow_up_date": follow_up_date},
            )
            return self._ok({"updated": True, "lead_id": lead_id})
        except Exception as e:
            logger.error(f"update_lead failed: {e}")
            return self._err(f"Failed to update lead: {e}")

    async def _search_leads(
        self,
        company: Optional[str] = None,
        status: Optional[str] = None,
        industry: Optional[str] = None,
        assigned_to: Optional[str] = None,
        limit: int = 20,
    ) -> dict:
        limit = min(limit, 100)
        conditions: list[str] = []
        params: dict[str, Any] = {"limit": limit}

        if company:
            conditions.append("LOWER(company_name) LIKE :company")
            params["company"] = f"%{company.lower()}%"
        if status:
            if status not in _VALID_STATUSES:
                return self._err(f"Invalid status '{status}'")
            conditions.append("status = :status")
            params["status"] = status
        if industry:
            conditions.append("LOWER(industry) LIKE :industry")
            params["industry"] = f"%{industry.lower()}%"
        if assigned_to:
            conditions.append("assigned_to = :assigned_to")
            params["assigned_to"] = assigned_to

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        sql = f"""
            SELECT id, company_name, contact_name, contact_email, industry,
                   location, source, status, assigned_to, notes,
                   created_at, last_contacted, follow_up_date
            FROM sales_leads
            {where}
            ORDER BY created_at DESC
            LIMIT :limit
        """

        try:
            from sqlalchemy import text

            async with await self._get_session() as session:
                result = await session.execute(text(sql), params)
                rows = [dict(r) for r in result.mappings().all()]

            # Serialize datetime and UUID fields
            for row in rows:
                for k, v in row.items():
                    if hasattr(v, "isoformat"):
                        row[k] = v.isoformat()
                    elif isinstance(v, uuid.UUID):
                        row[k] = str(v)

            logger.info(f"search_leads: {len(rows)} results (filters: company={company}, status={status})")
            return self._ok({"leads": rows, "count": len(rows)})
        except Exception as e:
            logger.error(f"search_leads failed: {e}")
            return self._err(f"Lead search failed: {e}")

    async def _get_lead(self, lead_id: str) -> dict:
        try:
            from sqlalchemy import text

            sql = """
                SELECT id, company_name, contact_name, contact_email, contact_phone,
                       industry, location, source, status, assigned_to, notes,
                       created_at, updated_at, last_contacted, follow_up_date
                FROM sales_leads
                WHERE id = :lead_id
            """

            async with await self._get_session() as session:
                result = await session.execute(text(sql), {"lead_id": lead_id})
                row = result.mappings().one_or_none()

            if row is None:
                return self._err(f"Lead '{lead_id}' not found")

            lead = dict(row)
            for k, v in lead.items():
                if hasattr(v, "isoformat"):
                    lead[k] = v.isoformat()
                elif isinstance(v, uuid.UUID):
                    lead[k] = str(v)

            return self._ok({"lead": lead})
        except Exception as e:
            logger.error(f"get_lead failed: {e}")
            return self._err(f"Failed to get lead: {e}")

    async def _export_leads(
        self,
        status: Optional[str] = None,
        assigned_to: Optional[str] = None,
        industry: Optional[str] = None,
    ) -> dict:
        # Reuse search to get matching rows
        search_result = await self._search_leads(
            status=status,
            assigned_to=assigned_to,
            industry=industry,
            limit=100,
        )
        if not search_result["success"]:
            return search_result

        leads = search_result["output"]["leads"]
        if not leads:
            return self._ok({"csv_bytes": "", "count": 0})

        try:
            import base64
            import io

            import pandas as pd

            df = pd.DataFrame(leads)
            buf = io.StringIO()
            df.to_csv(buf, index=False)
            csv_bytes = base64.b64encode(buf.getvalue().encode()).decode()

            logger.info(f"export_leads: {len(leads)} rows exported")
            return self._ok({"csv_bytes": csv_bytes, "count": len(leads)})
        except Exception as e:
            logger.error(f"export_leads failed: {e}")
            return self._err(f"CSV export failed: {e}")

    async def _get_pipeline(self, group_by: str = "status") -> dict:
        if group_by not in ("status", "assigned_to"):
            return self._err("group_by must be 'status' or 'assigned_to'")

        try:
            from sqlalchemy import text

            sql = f"""
                SELECT
                    {group_by} AS stage,
                    COUNT(*) AS count
                FROM sales_leads
                GROUP BY {group_by}
                ORDER BY count DESC
            """

            async with await self._get_session() as session:
                agg_result = await session.execute(text(sql))
                agg_rows = agg_result.mappings().all()

            stages = [{"stage": r["stage"], "count": r["count"]} for r in agg_rows]

            logger.info(f"get_pipeline: {len(stages)} stages (group_by={group_by})")
            return self._ok({"stages": stages, "group_by": group_by})
        except Exception as e:
            logger.error(f"get_pipeline failed: {e}")
            return self._err(f"Pipeline query failed: {e}")

    async def _get_stale_leads(
        self,
        days_overdue: int = 0,
        assigned_to: Optional[str] = None,
    ) -> dict:
        try:
            from sqlalchemy import text

            conditions = [
                "follow_up_date IS NOT NULL",
                "follow_up_date <= NOW() - MAKE_INTERVAL(days := :days_overdue)",
                "status NOT IN ('closed_won', 'closed_lost')",
            ]
            params: dict[str, Any] = {"days_overdue": max(0, days_overdue)}

            if assigned_to:
                conditions.append("assigned_to = :assigned_to")
                params["assigned_to"] = assigned_to

            where = "WHERE " + " AND ".join(conditions)
            sql = f"""
                SELECT id, company_name, contact_name, contact_email, status,
                       assigned_to, follow_up_date, notes
                FROM sales_leads
                {where}
                ORDER BY follow_up_date ASC
                LIMIT 100
            """

            async with await self._get_session() as session:
                result = await session.execute(text(sql), params)
                rows = [dict(r) for r in result.mappings().all()]

            for row in rows:
                for k, v in row.items():
                    if hasattr(v, "isoformat"):
                        row[k] = v.isoformat()
                    elif isinstance(v, uuid.UUID):
                        row[k] = str(v)

            logger.info(f"get_stale_leads: {len(rows)} overdue leads")
            return self._ok({"leads": rows, "count": len(rows)})
        except Exception as e:
            logger.error(f"get_stale_leads failed: {e}")
            return self._err(f"Stale leads query failed: {e}")

    # ── Automation helpers (called by scheduled tasks) ─────────────────────────

    async def check_duplicate_lead(self, source: str, source_ref: str) -> bool:
        """Return True if a lead with (source, source_ref) already exists."""
        try:
            from sqlalchemy import text

            sql = "SELECT id FROM sales_leads WHERE source = :source AND source_ref = :source_ref LIMIT 1"
            async with await self._get_session() as session:
                result = await session.execute(text(sql), {"source": source, "source_ref": source_ref})
                return result.scalar_one_or_none() is not None
        except Exception as e:
            logger.error(f"check_duplicate_lead failed: {e}")
            return False

    async def create_lead_safe(self, lead_data: dict) -> dict:
        """
        Insert a lead only if (source, source_ref) is not already present.

        Returns:
            {"success": True, "skipped": True, "reason": "duplicate"} — if dupe
            {"success": True, "skipped": False, "lead_id": ...}        — if inserted
        """
        source = lead_data.get("source", "")
        source_ref = lead_data.get("source_ref")

        if source_ref and await self.check_duplicate_lead(source, source_ref):
            logger.debug(f"create_lead_safe: duplicate skipped (source={source}, ref={source_ref})")
            return self._ok({"skipped": True, "reason": "duplicate"})

        result = await self._create_lead(
            company_name=lead_data.get("company_name", "Unknown"),
            contact_email=lead_data.get("contact_email", ""),
            contact_name=lead_data.get("contact_name", ""),
            industry=lead_data.get("industry", ""),
            source=source,
            assigned_to=lead_data.get("assigned_to", "system"),
            contact_phone=lead_data.get("contact_phone"),
            location=lead_data.get("location"),
            notes=lead_data.get("notes"),
            source_ref=source_ref,
        )
        if result.get("success"):
            return self._ok({"skipped": False, "lead_id": result["output"]["lead_id"]})
        return result

    async def get_new_leads_summary(
        self,
        since: Any,
        assigned_to: Optional[str] = None,
    ) -> list[dict]:
        """
        Return leads created or status-updated since `since`.
        Optionally filter by assigned_to (PIC UUID).
        """
        try:
            from sqlalchemy import text

            conditions = [
                "(sl.created_at >= :since OR sl.last_status_update >= :since)"
            ]
            params: dict[str, Any] = {"since": since}
            if assigned_to:
                conditions.append("sl.assigned_to = :assigned_to")
                params["assigned_to"] = assigned_to

            where = "WHERE " + " AND ".join(conditions)
            sql = f"""
                SELECT sl.id, sl.company_name, sl.contact_name, sl.contact_email,
                       sl.industry, sl.source, sl.status, sl.assigned_to,
                       sl.notes, sl.created_at, sl.last_status_update,
                       sl.follow_up_date, sl.last_contacted, sl.source_ref,
                       u.name AS pic_name, u.email AS pic_email
                FROM sales_leads sl
                LEFT JOIN users u ON sl.assigned_to = u.id
                {where}
                ORDER BY sl.created_at DESC
            """
            async with await self._get_session() as session:
                result = await session.execute(text(sql), params)
                rows = [dict(r) for r in result.mappings().all()]

            for row in rows:
                for k, v in row.items():
                    if hasattr(v, "isoformat"):
                        row[k] = v.isoformat()
                    elif isinstance(v, uuid.UUID):
                        row[k] = str(v)

            return rows
        except Exception as e:
            logger.error(f"get_new_leads_summary failed: {e}")
            return []

    async def update_lead_status(
        self,
        lead_id: str,
        new_status: str,
        remarks: Optional[str],
        updated_by: str,
    ) -> dict:
        """
        Transition lead status with allowlist validation.
        Appends timestamped remark to notes; sets last_status_update = NOW().
        """
        try:
            from datetime import datetime, timezone
            from sqlalchemy import text

            # Fetch current status
            async with await self._get_session() as session:
                row = await session.execute(
                    text("SELECT status, notes FROM sales_leads WHERE id = :id"),
                    {"id": lead_id},
                )
                current = row.mappings().one_or_none()

            if current is None:
                return self._err(f"Lead '{lead_id}' not found")

            current_status = current["status"]
            allowed = _STATUS_TRANSITIONS.get(current_status, set())
            if new_status not in allowed:
                return self._err(
                    f"Invalid status transition: {current_status} → {new_status}. "
                    f"Allowed: {', '.join(sorted(allowed)) or 'none'}"
                )

            # Build updated notes
            ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            note_line = f"[{ts}] Status → {new_status}"
            if remarks:
                note_line += f": {remarks}"
            old_notes = current["notes"] or ""
            new_notes = f"{old_notes}\n{note_line}".strip()

            set_clauses = [
                "status = :new_status",
                "notes = :notes",
                "last_status_update = NOW()",
            ]
            params: dict[str, Any] = {
                "new_status": new_status,
                "notes": new_notes,
                "id": lead_id,
            }
            if new_status in ("contacted", "qualified", "proposal"):
                set_clauses.append("last_contacted = NOW()")

            sql = (
                f"UPDATE sales_leads SET {', '.join(set_clauses)} "
                f"WHERE id = :id RETURNING id, status, notes, last_status_update"
            )

            async with await self._get_session() as session:
                result = await session.execute(text(sql), params)
                await session.commit()
                updated_row = result.mappings().one_or_none()

            if not updated_row:
                return self._err(f"Lead '{lead_id}' update failed")

            lead = dict(updated_row)
            for k, v in lead.items():
                if hasattr(v, "isoformat"):
                    lead[k] = v.isoformat()
                elif isinstance(v, uuid.UUID):
                    lead[k] = str(v)

            await self._log_audit(
                user_id=updated_by,
                action="lead_status_updated",
                resource="crm",
                details={
                    "lead_id": lead_id,
                    "old_status": current_status,
                    "new_status": new_status,
                    "remarks": remarks,
                },
            )
            logger.info(f"update_lead_status: {lead_id} → {new_status}")
            return self._ok({"lead": lead, "previous_status": current_status})

        except Exception as e:
            logger.error(f"update_lead_status failed: {e}")
            return self._err(f"Status update failed: {e}")

    async def bulk_assign_leads(
        self,
        lead_ids: list[str],
        assign_to: str,
        assigned_by: str,
    ) -> dict:
        """
        Bulk-update assigned_to on a list of leads.
        Logs each assignment to audit_log.
        """
        try:
            from sqlalchemy import text

            updated = 0
            failed = []
            for lead_id in lead_ids:
                try:
                    async with await self._get_session() as session:
                        result = await session.execute(
                            text(
                                "UPDATE sales_leads SET assigned_to = :assign_to "
                                "WHERE id = :id RETURNING id"
                            ),
                            {"assign_to": assign_to, "id": lead_id},
                        )
                        await session.commit()
                        if result.scalar_one_or_none():
                            updated += 1
                            await self._log_audit(
                                user_id=assigned_by,
                                action="lead_assigned",
                                resource="crm",
                                details={"lead_id": lead_id, "assigned_to": assign_to},
                            )
                except Exception as e:
                    logger.error(f"bulk_assign_leads: failed for {lead_id}: {e}")
                    failed.append(lead_id)

            logger.info(f"bulk_assign_leads: {updated} updated, {len(failed)} failed")
            return self._ok({"updated": updated, "failed": failed, "assign_to": assign_to})

        except Exception as e:
            logger.error(f"bulk_assign_leads outer failed: {e}")
            return self._err(f"Bulk assign failed: {e}")
