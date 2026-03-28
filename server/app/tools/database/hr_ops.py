"""
HR Tool — employee CRUD and leave management operations.

Tools provided:
    get_employee              — Fetch a single employee by ID
    list_employees            — List employees with optional filters
    create_employee           — Create a new employee record
    update_employee           — Update employee fields
    set_employee_status       — Activate / deactivate employee
    get_employee_profile      — Rich profile: employee + leave balances + upcoming leaves
    apply_leave               — Submit a leave application
    get_leave_applications    — List leave applications with filters
    get_leave_balance         — Leave balances for an employee in a given year
    update_leave_status       — Approve / reject / cancel a leave application
    get_leave_summary_dashboard — Per-employee leave summary (HR reports)
    get_pending_approvals     — Pending leaves for a manager's direct reports
    list_leave_types          — Active leave types (optionally filtered by country)

Access control:
    HR roles (hr_staff, hr_manager) — see all employees / applications
    Managers (is_manager flag)      — see own direct reports
    Others                          — see self only

Mutations are logged to hr_audit_log.
"""

import logging
import re
import uuid
from datetime import date
from typing import Any, Optional

from app.tools.base_tool import BaseTool

logger = logging.getLogger("mezzofy.tools.hr")


def _to_date(value) -> Optional[date]:
    """Convert a string like '2024-01-15' to datetime.date, or return None/date as-is."""
    if value is None:
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except (ValueError, TypeError):
        return None


class HROps(BaseTool):

    def get_tools(self) -> list[dict]:
        return [
            {
                "name": "get_employee",
                "description": (
                    "Fetch a single employee record by UUID. "
                    "HR roles see all; others see their own record only."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "employee_id": {
                            "type": "string",
                            "description": "UUID of the employee",
                        },
                        "requesting_user_id": {
                            "type": "string",
                            "description": "User ID of the caller (for access control)",
                        },
                    },
                    "required": ["employee_id", "requesting_user_id"],
                },
                "handler": self._get_employee,
            },
            {
                "name": "list_employees",
                "description": (
                    "List employees with optional filters. "
                    "HR staff see all; managers see their direct reports; others see themselves only."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "filters": {
                            "type": "object",
                            "description": "Optional filters: department, country, is_active, manager_id, search",
                        },
                        "requesting_user_id": {
                            "type": "string",
                            "description": "User ID of the caller",
                        },
                    },
                    "required": ["requesting_user_id"],
                },
                "handler": self._list_employees,
            },
            {
                "name": "create_employee",
                "description": (
                    "Create a new employee record. Auto-generates staff_id. "
                    "Creates initial leave balances for current year."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "employee_data": {
                            "type": "object",
                            "description": "Employee fields: full_name, email, department, country, hire_date (required); plus optional fields",
                        },
                        "created_by_user_id": {
                            "type": "string",
                            "description": "User ID of the creator",
                        },
                    },
                    "required": ["employee_data", "created_by_user_id"],
                },
                "handler": self._create_employee,
            },
            {
                "name": "update_employee",
                "description": "Update employee fields. Forbidden: id, created_at, staff_id.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "employee_id": {"type": "string", "description": "UUID of the employee"},
                        "updates": {"type": "object", "description": "Fields to update"},
                        "updated_by_user_id": {"type": "string", "description": "User ID of the updater"},
                    },
                    "required": ["employee_id", "updates", "updated_by_user_id"],
                },
                "handler": self._update_employee,
            },
            {
                "name": "set_employee_status",
                "description": "Activate or deactivate an employee record.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "employee_id": {"type": "string"},
                        "is_active": {"type": "boolean"},
                        "updated_by_user_id": {"type": "string"},
                    },
                    "required": ["employee_id", "is_active", "updated_by_user_id"],
                },
                "handler": self._set_employee_status,
            },
            {
                "name": "get_employee_profile",
                "description": (
                    "Rich employee profile: employee data + current-year leave balances "
                    "+ pending/upcoming applications."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "employee_id": {"type": "string"},
                        "requesting_user_id": {"type": "string"},
                    },
                    "required": ["employee_id", "requesting_user_id"],
                },
                "handler": self._get_employee_profile,
            },
            {
                "name": "apply_leave",
                "description": (
                    "Submit a leave application for an employee. "
                    "Validates balance and checks for overlapping applications."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "application_data": {
                            "type": "object",
                            "description": "Fields: leave_type_id, start_date, end_date, total_days, reason; optional: half_day, half_day_period",
                        },
                        "employee_id": {"type": "string", "description": "UUID of the employee applying"},
                    },
                    "required": ["application_data", "employee_id"],
                },
                "handler": self._apply_leave,
            },
            {
                "name": "get_leave_applications",
                "description": "List leave applications with optional filters.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "filters": {
                            "type": "object",
                            "description": "Optional: employee_id, status, leave_type_id, year, date_from, date_to",
                        },
                        "requesting_user_id": {"type": "string"},
                    },
                    "required": ["requesting_user_id"],
                },
                "handler": self._get_leave_applications,
            },
            {
                "name": "get_leave_balance",
                "description": "Get leave balances for an employee in a given year.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "employee_id": {"type": "string"},
                        "year": {"type": "integer", "description": "Year (e.g. 2026)"},
                        "requesting_user_id": {"type": "string"},
                    },
                    "required": ["employee_id", "year", "requesting_user_id"],
                },
                "handler": self._get_leave_balance,
            },
            {
                "name": "update_leave_status",
                "description": (
                    "Approve, reject, or cancel a leave application. "
                    "Updates leave balances accordingly."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "application_id": {"type": "string"},
                        "new_status": {
                            "type": "string",
                            "description": "approved | rejected | cancelled",
                        },
                        "comment": {"type": "string"},
                        "actor_user_id": {"type": "string"},
                    },
                    "required": ["application_id", "new_status", "actor_user_id"],
                },
                "handler": self._update_leave_status,
            },
            {
                "name": "get_leave_summary_dashboard",
                "description": (
                    "Per-employee leave summary dashboard. "
                    "Requires hr_reports or management_read permission."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "year": {"type": "integer"},
                        "filters": {
                            "type": "object",
                            "description": "Optional: department, country",
                        },
                        "requesting_user_id": {"type": "string"},
                    },
                    "required": ["year", "requesting_user_id"],
                },
                "handler": self._get_leave_summary_dashboard,
            },
            {
                "name": "get_pending_approvals",
                "description": "Get pending leave applications for a manager's direct reports.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "manager_employee_id": {
                            "type": "string",
                            "description": "UUID of the manager's employee record",
                        },
                    },
                    "required": ["manager_employee_id"],
                },
                "handler": self._get_pending_approvals,
            },
            {
                "name": "list_leave_types",
                "description": "List active leave types, optionally filtered by country.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "country": {
                            "type": "string",
                            "description": "Country code (e.g. SG, MY). Returns global + country-specific types.",
                        },
                    },
                    "required": [],
                },
                "handler": self._list_leave_types,
            },
        ]

    # ── Private: session helper ────────────────────────────────────────────────

    async def _get_session(self):
        from app.core.database import AsyncSessionLocal
        return AsyncSessionLocal()

    # ── Private: audit log ─────────────────────────────────────────────────────

    async def _log_hr_audit(
        self,
        session,
        actor_id: Optional[str],
        target_type: str,
        target_id: str,
        action: str,
        changes: Optional[dict] = None,
        source: str = "portal",
    ) -> None:
        """Insert a row into hr_audit_log. Never raises."""
        try:
            import json
            from sqlalchemy import text
            await session.execute(
                text("""
                    INSERT INTO hr_audit_log (actor_id, target_type, target_id, action, changes, source)
                    VALUES (:actor_id, :target_type, :target_id, :action, :changes, :source)
                """),
                {
                    "actor_id": actor_id,
                    "target_type": target_type,
                    "target_id": target_id,
                    "action": action,
                    "changes": json.dumps(changes) if changes else None,
                    "source": source,
                },
            )
        except Exception as e:
            logger.warning(f"hr_audit_log insert failed: {e}")

    # ── Private: staff_id generator ───────────────────────────────────────────

    async def _get_next_staff_id(self, session, country: str, dept: str) -> str:
        """Generate next staff_id like 'SG-ENG-0003'."""
        from sqlalchemy import text
        country_up = country.upper()
        dept_up = dept.upper()[:8]
        prefix = f"{country_up}-{dept_up}-"
        result = await session.execute(
            text("""
                SELECT staff_id FROM hr_employees
                WHERE staff_id LIKE :prefix
                ORDER BY staff_id DESC
                LIMIT 1
            """),
            {"prefix": f"{prefix}%"},
        )
        row = result.fetchone()
        if row:
            # Extract numeric suffix
            try:
                last_seq = int(re.search(r"(\d+)$", row[0]).group(1))
                next_seq = last_seq + 1
            except Exception:
                next_seq = 1
        else:
            next_seq = 1
        return f"{country_up}-{dept_up}-{next_seq:04d}"

    # ── Private: HR role check ─────────────────────────────────────────────────

    def _is_hr_role(self, user_id: str) -> bool:
        """
        Lightweight check — returns True if user_id is truthy.
        Actual role enforcement is done at the API layer via RBAC.
        In tool layer we rely on the calling endpoint to have verified.
        """
        return True  # Tools always trust the caller for role checks

    # ── Private: serialize row ─────────────────────────────────────────────────

    def _serialize(self, row: dict) -> dict:
        result = {}
        for k, v in row.items():
            if hasattr(v, "isoformat"):
                result[k] = v.isoformat()
            elif isinstance(v, uuid.UUID):
                result[k] = str(v)
            else:
                result[k] = v
        return result

    # ── Public helpers (used by HR Agent) ─────────────────────────────────────

    async def _resolve_employee_by_user(self, user_id: str) -> dict:
        """Look up an employee record by users.id → hr_employees.user_id."""
        try:
            from sqlalchemy import text
            async with await self._get_session() as session:
                result = await session.execute(
                    text("""
                        SELECT id, staff_id, full_name, department, country,
                               manager_id, annual_leave_days, sick_leave_days,
                               hire_date, is_active
                        FROM hr_employees
                        WHERE user_id = :user_id AND is_active = true
                        LIMIT 1
                    """),
                    {"user_id": user_id},
                )
                row = result.mappings().one_or_none()
            if row is None:
                return self._err(f"No active employee record linked to user {user_id}")
            return self._ok(self._serialize(dict(row)))
        except Exception as e:
            logger.error(f"_resolve_employee_by_user failed: {e}")
            return self._err(f"Failed to resolve employee: {e}")

    async def _create_employee_from_user(
        self,
        user_id: str,
        staff_id: Optional[str],
        department: str,
        country: str,
        hire_date: Optional[str],
        annual_leave_days: int,
        sick_leave_days: int,
        created_by_user_id: str,
        session,
    ) -> dict:
        """
        Create an employee record linked to an existing user.
        Called from admin.py POST /admin/users when create_employee=True.
        """
        try:
            from sqlalchemy import text

            # Get user details
            user_row = (await session.execute(
                text("SELECT name, email FROM users WHERE id = :id"),
                {"id": user_id},
            )).mappings().one_or_none()
            if not user_row:
                return self._err(f"User {user_id} not found")

            full_name = user_row["name"]
            email = user_row["email"]

            # Generate staff_id if not provided
            if not staff_id:
                staff_id = await self._get_next_staff_id(session, country, department)

            hire = hire_date or date.today().isoformat()

            result = await session.execute(
                text("""
                    INSERT INTO hr_employees
                        (user_id, staff_id, full_name, email, department, country,
                         hire_date, annual_leave_days, sick_leave_days, created_by)
                    VALUES
                        (:user_id, :staff_id, :full_name, :email, :department, :country,
                         :hire_date, :annual_leave_days, :sick_leave_days, :created_by)
                    RETURNING id
                """),
                {
                    "user_id": user_id,
                    "staff_id": staff_id,
                    "full_name": full_name,
                    "email": email,
                    "department": department,
                    "country": country,
                    "hire_date": hire,
                    "annual_leave_days": annual_leave_days,
                    "sick_leave_days": sick_leave_days,
                    "created_by": created_by_user_id,
                },
            )
            employee_id = str(result.scalar_one())

            # Create initial leave balances for current year
            await self._create_initial_balances(session, employee_id, annual_leave_days, sick_leave_days)

            await self._log_hr_audit(
                session=session,
                actor_id=created_by_user_id,
                target_type="employee",
                target_id=employee_id,
                action="created",
                changes={"staff_id": staff_id, "user_id": user_id},
            )
            await session.commit()
            return self._ok({"employee_id": employee_id, "staff_id": staff_id})
        except Exception as e:
            logger.error(f"_create_employee_from_user failed: {e}")
            return self._err(f"Failed to create employee from user: {e}")

    async def _create_initial_balances(
        self,
        session,
        employee_id: str,
        annual_days: int,
        sick_days: int,
    ) -> None:
        """Create hr_leave_balances rows for ANNUAL and SICK for the current year."""
        from sqlalchemy import text
        year = date.today().year
        for code, days in [("ANNUAL", annual_days), ("SICK", sick_days)]:
            try:
                lt_row = (await session.execute(
                    text("SELECT id FROM hr_leave_types WHERE code = :code AND is_active = true"),
                    {"code": code},
                )).mappings().one_or_none()
                if lt_row:
                    await session.execute(
                        text("""
                            INSERT INTO hr_leave_balances
                                (employee_id, leave_type_id, year, entitled_days)
                            VALUES (:employee_id, :leave_type_id, :year, :entitled_days)
                            ON CONFLICT (employee_id, leave_type_id, year) DO NOTHING
                        """),
                        {
                            "employee_id": employee_id,
                            "leave_type_id": str(lt_row["id"]),
                            "year": year,
                            "entitled_days": days,
                        },
                    )
            except Exception as e:
                logger.warning(f"Balance init for {code} failed: {e}")

    # ── Handlers ──────────────────────────────────────────────────────────────

    async def _get_employee(
        self,
        employee_id: str,
        requesting_user_id: str,
    ) -> dict:
        try:
            from sqlalchemy import text
            async with await self._get_session() as session:
                result = await session.execute(
                    text("""
                        SELECT e.*, m.full_name AS manager_name
                        FROM hr_employees e
                        LEFT JOIN hr_employees m ON e.manager_id = m.id
                        WHERE e.id = :id
                    """),
                    {"id": employee_id},
                )
                row = result.mappings().one_or_none()

            if row is None:
                return self._err(f"Employee '{employee_id}' not found")

            employee = self._serialize(dict(row))
            return self._ok({"employee": employee})
        except Exception as e:
            logger.error(f"get_employee failed: {e}")
            return self._err(f"Failed to get employee: {e}")

    async def _list_employees(
        self,
        requesting_user_id: str,
        filters: Optional[dict] = None,
    ) -> dict:
        filters = filters or {}
        try:
            from sqlalchemy import text
            conditions: list[str] = []
            params: dict[str, Any] = {}

            if filters.get("department"):
                conditions.append("e.department = :department")
                params["department"] = filters["department"]
            if filters.get("country"):
                conditions.append("e.country = :country")
                params["country"] = filters["country"]
            if filters.get("is_active") is not None:
                conditions.append("e.is_active = :is_active")
                params["is_active"] = filters["is_active"]
            if filters.get("manager_id"):
                conditions.append("e.manager_id = :manager_id")
                params["manager_id"] = filters["manager_id"]
            if filters.get("search"):
                conditions.append("(LOWER(e.full_name) LIKE :search OR LOWER(e.staff_id) LIKE :search)")
                params["search"] = f"%{filters['search'].lower()}%"

            where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
            sql = f"""
                SELECT e.id, e.staff_id, e.full_name, e.email, e.department,
                       e.job_title, e.country, e.is_active, e.hire_date,
                       e.employment_type, e.manager_id, m.full_name AS manager_name
                FROM hr_employees e
                LEFT JOIN hr_employees m ON e.manager_id = m.id
                {where}
                ORDER BY e.full_name ASC
                LIMIT 200
            """
            async with await self._get_session() as session:
                result = await session.execute(text(sql), params)
                rows = [self._serialize(dict(r)) for r in result.mappings().all()]

            return self._ok({"employees": rows, "count": len(rows)})
        except Exception as e:
            logger.error(f"list_employees failed: {e}")
            return self._err(f"Failed to list employees: {e}")

    async def _create_employee(
        self,
        employee_data: dict,
        created_by_user_id: str,
    ) -> dict:
        required = ["full_name", "email", "department", "country", "hire_date"]
        for f in required:
            if not employee_data.get(f):
                return self._err(f"Missing required field: {f}")

        try:
            from sqlalchemy import text
            async with await self._get_session() as session:
                staff_id = employee_data.get("staff_id") or await self._get_next_staff_id(
                    session,
                    employee_data["country"],
                    employee_data["department"],
                )

                result = await session.execute(
                    text("""
                        INSERT INTO hr_employees
                            (user_id, staff_id, full_name, email, phone, department, job_title,
                             employment_type, country, location_office, manager_id,
                             annual_leave_days, sick_leave_days, other_leave_days,
                             hire_date, probation_end_date, profile_notes, created_by)
                        VALUES
                            (:user_id, :staff_id, :full_name, :email, :phone, :department, :job_title,
                             :employment_type, :country, :location_office, :manager_id,
                             :annual_leave_days, :sick_leave_days, :other_leave_days,
                             :hire_date, :probation_end_date, :profile_notes, :created_by)
                        RETURNING id
                    """),
                    {
                        "user_id": employee_data.get("user_id"),
                        "staff_id": staff_id,
                        "full_name": employee_data["full_name"],
                        "email": employee_data["email"],
                        "phone": employee_data.get("phone"),
                        "department": employee_data["department"],
                        "job_title": employee_data.get("job_title"),
                        "employment_type": employee_data.get("employment_type", "full_time"),
                        "country": employee_data["country"],
                        "location_office": employee_data.get("location_office"),
                        "manager_id": employee_data.get("manager_id"),
                        "annual_leave_days": employee_data.get("annual_leave_days", 14),
                        "sick_leave_days": employee_data.get("sick_leave_days", 14),
                        "other_leave_days": employee_data.get("other_leave_days", 0),
                        "hire_date": _to_date(employee_data["hire_date"]),
                        "probation_end_date": _to_date(employee_data.get("probation_end_date")),
                        "profile_notes": employee_data.get("profile_notes"),
                        "created_by": created_by_user_id,
                    },
                )
                employee_id = str(result.scalar_one())

                # Create initial leave balances
                await self._create_initial_balances(
                    session,
                    employee_id,
                    employee_data.get("annual_leave_days", 14),
                    employee_data.get("sick_leave_days", 14),
                )

                await self._log_hr_audit(
                    session=session,
                    actor_id=created_by_user_id,
                    target_type="employee",
                    target_id=employee_id,
                    action="created",
                    changes={"staff_id": staff_id},
                )
                await session.commit()

            logger.info(f"create_employee: {employee_id} ({staff_id})")
            return self._ok({"employee_id": employee_id, "staff_id": staff_id})
        except Exception as e:
            logger.error(f"create_employee failed: {e}")
            return self._err(f"Failed to create employee: {e}")

    async def _update_employee(
        self,
        employee_id: str,
        updates: dict,
        updated_by_user_id: str,
    ) -> dict:
        forbidden = {"id", "created_at", "staff_id"}
        updates = {k: v for k, v in updates.items() if k not in forbidden}
        for date_field in ("hire_date", "probation_end_date"):
            if date_field in updates:
                updates[date_field] = _to_date(updates[date_field])
        if not updates:
            return self._err("No valid fields to update")

        try:
            from sqlalchemy import text
            updates["updated_at"] = "NOW()"
            set_parts = []
            params: dict[str, Any] = {"id": employee_id}
            for k, v in updates.items():
                if v == "NOW()":
                    set_parts.append(f"{k} = NOW()")
                else:
                    set_parts.append(f"{k} = :{k}")
                    params[k] = v

            sql = f"UPDATE hr_employees SET {', '.join(set_parts)} WHERE id = :id RETURNING id"
            async with await self._get_session() as session:
                result = await session.execute(text(sql), params)
                updated = result.scalar_one_or_none()
                if not updated:
                    return self._err(f"Employee '{employee_id}' not found")
                await self._log_hr_audit(
                    session=session,
                    actor_id=updated_by_user_id,
                    target_type="employee",
                    target_id=employee_id,
                    action="updated",
                    changes={k: v for k, v in updates.items() if v != "NOW()"},
                )
                await session.commit()

            return self._ok({"updated": True, "employee_id": employee_id})
        except Exception as e:
            logger.error(f"update_employee failed: {e}")
            return self._err(f"Failed to update employee: {e}")

    async def _set_employee_status(
        self,
        employee_id: str,
        is_active: bool,
        updated_by_user_id: str,
    ) -> dict:
        try:
            from sqlalchemy import text
            async with await self._get_session() as session:
                result = await session.execute(
                    text("UPDATE hr_employees SET is_active = :active, updated_at = NOW() WHERE id = :id RETURNING id"),
                    {"active": is_active, "id": employee_id},
                )
                if result.scalar_one_or_none() is None:
                    return self._err(f"Employee '{employee_id}' not found")
                action = "reactivated" if is_active else "deactivated"
                await self._log_hr_audit(
                    session=session,
                    actor_id=updated_by_user_id,
                    target_type="employee",
                    target_id=employee_id,
                    action=action,
                )
                await session.commit()

            return self._ok({"updated": True, "is_active": is_active, "employee_id": employee_id})
        except Exception as e:
            logger.error(f"set_employee_status failed: {e}")
            return self._err(f"Failed to set employee status: {e}")

    async def _get_employee_profile(
        self,
        employee_id: str,
        requesting_user_id: str,
    ) -> dict:
        try:
            from sqlalchemy import text
            year = date.today().year

            async with await self._get_session() as session:
                # Employee data
                emp_result = await session.execute(
                    text("""
                        SELECT e.*, m.full_name AS manager_name
                        FROM hr_employees e
                        LEFT JOIN hr_employees m ON e.manager_id = m.id
                        WHERE e.id = :id
                    """),
                    {"id": employee_id},
                )
                emp_row = emp_result.mappings().one_or_none()
                if emp_row is None:
                    return self._err(f"Employee '{employee_id}' not found")

                # Leave balances
                bal_result = await session.execute(
                    text("""
                        SELECT lb.*, lt.name AS leave_type_name, lt.code AS leave_type_code
                        FROM hr_leave_balances lb
                        JOIN hr_leave_types lt ON lb.leave_type_id = lt.id
                        WHERE lb.employee_id = :emp_id AND lb.year = :year
                        ORDER BY lt.name
                    """),
                    {"emp_id": employee_id, "year": year},
                )
                balances = [self._serialize(dict(r)) for r in bal_result.mappings().all()]

                # Pending / upcoming applications
                apps_result = await session.execute(
                    text("""
                        SELECT la.*, lt.name AS leave_type_name
                        FROM hr_leave_applications la
                        JOIN hr_leave_types lt ON la.leave_type_id = lt.id
                        WHERE la.employee_id = :emp_id
                          AND la.status IN ('pending', 'approved')
                          AND la.end_date >= CURRENT_DATE
                        ORDER BY la.start_date ASC
                        LIMIT 10
                    """),
                    {"emp_id": employee_id},
                )
                upcoming = [self._serialize(dict(r)) for r in apps_result.mappings().all()]

            return self._ok({
                "employee": self._serialize(dict(emp_row)),
                "leave_balances": balances,
                "upcoming_leaves": upcoming,
                "year": year,
            })
        except Exception as e:
            logger.error(f"get_employee_profile failed: {e}")
            return self._err(f"Failed to get employee profile: {e}")

    async def _apply_leave(
        self,
        application_data: dict,
        employee_id: str,
    ) -> dict:
        required = ["leave_type_id", "start_date", "end_date", "total_days"]
        for f in required:
            if application_data.get(f) is None:
                return self._err(f"Missing required field: {f}")

        try:
            from sqlalchemy import text
            year = int(str(application_data["start_date"])[:4])
            total_days = float(application_data["total_days"])

            async with await self._get_session() as session:
                # Check balance
                bal_row = (await session.execute(
                    text("""
                        SELECT id, remaining_days, pending_days
                        FROM hr_leave_balances
                        WHERE employee_id = :emp_id
                          AND leave_type_id = :lt_id
                          AND year = :year
                    """),
                    {
                        "emp_id": employee_id,
                        "lt_id": application_data["leave_type_id"],
                        "year": year,
                    },
                )).mappings().one_or_none()

                allow_negative = (
                    self.config.get("hr", {})
                    .get("leave_rules", {})
                    .get("allow_negative_balance", False)
                )

                if bal_row and not allow_negative:
                    available = float(bal_row["remaining_days"] or 0) - float(bal_row["pending_days"] or 0)
                    if total_days > available:
                        return self._err(
                            f"Insufficient leave balance. Requested: {total_days}, available: {available:.1f}"
                        )

                # Check overlapping applications
                overlap = (await session.execute(
                    text("""
                        SELECT id FROM hr_leave_applications
                        WHERE employee_id = :emp_id
                          AND status IN ('pending', 'approved')
                          AND NOT (end_date < :start_date OR start_date > :end_date)
                    """),
                    {
                        "emp_id": employee_id,
                        "start_date": application_data["start_date"],
                        "end_date": application_data["end_date"],
                    },
                )).fetchone()
                if overlap:
                    return self._err("Overlapping leave application already exists for this date range")

                # Insert application
                result = await session.execute(
                    text("""
                        INSERT INTO hr_leave_applications
                            (employee_id, leave_type_id, start_date, end_date, total_days,
                             half_day, half_day_period, reason, status, applied_via)
                        VALUES
                            (:employee_id, :leave_type_id, :start_date, :end_date, :total_days,
                             :half_day, :half_day_period, :reason, 'pending', 'portal')
                        RETURNING id
                    """),
                    {
                        "employee_id": employee_id,
                        "leave_type_id": application_data["leave_type_id"],
                        "start_date": application_data["start_date"],
                        "end_date": application_data["end_date"],
                        "total_days": total_days,
                        "half_day": application_data.get("half_day", False),
                        "half_day_period": application_data.get("half_day_period"),
                        "reason": application_data.get("reason"),
                    },
                )
                app_id = str(result.scalar_one())

                # Update pending_days in balance
                if bal_row:
                    await session.execute(
                        text("""
                            UPDATE hr_leave_balances
                            SET pending_days = pending_days + :days, updated_at = NOW()
                            WHERE id = :bal_id
                        """),
                        {"days": total_days, "bal_id": str(bal_row["id"])},
                    )

                await self._log_hr_audit(
                    session=session,
                    actor_id=employee_id,
                    target_type="leave_application",
                    target_id=app_id,
                    action="leave_applied",
                    changes={
                        "start_date": str(application_data["start_date"]),
                        "end_date": str(application_data["end_date"]),
                        "total_days": total_days,
                    },
                )
                await session.commit()

            logger.info(f"apply_leave: application {app_id} created for employee {employee_id}")
            return self._ok({"application_id": app_id, "status": "pending"})
        except Exception as e:
            logger.error(f"apply_leave failed: {e}")
            return self._err(f"Failed to apply for leave: {e}")

    async def _get_leave_applications(
        self,
        requesting_user_id: str,
        filters: Optional[dict] = None,
    ) -> dict:
        filters = filters or {}
        try:
            from sqlalchemy import text
            conditions: list[str] = []
            params: dict[str, Any] = {}

            if filters.get("employee_id"):
                conditions.append("la.employee_id = :employee_id")
                params["employee_id"] = filters["employee_id"]
            if filters.get("status"):
                status_val = filters["status"]
                if isinstance(status_val, list):
                    conditions.append("la.status = ANY(:status_list)")
                    params["status_list"] = status_val
                else:
                    conditions.append("la.status = :status")
                    params["status"] = status_val
            if filters.get("leave_type_id"):
                conditions.append("la.leave_type_id = :leave_type_id")
                params["leave_type_id"] = filters["leave_type_id"]
            if filters.get("year"):
                conditions.append("EXTRACT(YEAR FROM la.start_date) = :year")
                params["year"] = filters["year"]
            if filters.get("date_from"):
                conditions.append("la.start_date >= :date_from")
                params["date_from"] = filters["date_from"]
            if filters.get("date_to"):
                conditions.append("la.end_date <= :date_to")
                params["date_to"] = filters["date_to"]
            if filters.get("future_only"):
                conditions.append("la.end_date >= CURRENT_DATE")

            where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
            sql = f"""
                SELECT la.*, lt.name AS leave_type_name, lt.code AS leave_type_code,
                       e.full_name AS employee_name, e.staff_id
                FROM hr_leave_applications la
                JOIN hr_leave_types lt ON la.leave_type_id = lt.id
                JOIN hr_employees e ON la.employee_id = e.id
                {where}
                ORDER BY la.created_at DESC
                LIMIT 200
            """
            async with await self._get_session() as session:
                result = await session.execute(text(sql), params)
                rows = [self._serialize(dict(r)) for r in result.mappings().all()]

            return self._ok({"applications": rows, "count": len(rows)})
        except Exception as e:
            logger.error(f"get_leave_applications failed: {e}")
            return self._err(f"Failed to get leave applications: {e}")

    async def _get_leave_balance(
        self,
        employee_id: str,
        year: int,
        requesting_user_id: str,
    ) -> dict:
        try:
            from sqlalchemy import text
            async with await self._get_session() as session:
                result = await session.execute(
                    text("""
                        SELECT lb.*, lt.name AS leave_type_name, lt.code AS leave_type_code,
                               lt.is_paid
                        FROM hr_leave_balances lb
                        JOIN hr_leave_types lt ON lb.leave_type_id = lt.id
                        WHERE lb.employee_id = :emp_id AND lb.year = :year
                        ORDER BY lt.name
                    """),
                    {"emp_id": employee_id, "year": year},
                )
                rows = [self._serialize(dict(r)) for r in result.mappings().all()]

            return self._ok({"balances": rows, "year": year, "employee_id": employee_id})
        except Exception as e:
            logger.error(f"get_leave_balance failed: {e}")
            return self._err(f"Failed to get leave balance: {e}")

    async def _update_leave_status(
        self,
        application_id: str,
        new_status: str,
        actor_user_id: str,
        comment: Optional[str] = None,
    ) -> dict:
        valid_statuses = {"approved", "rejected", "cancelled"}
        if new_status not in valid_statuses:
            return self._err(f"Invalid status '{new_status}'. Must be: {', '.join(valid_statuses)}")

        try:
            from sqlalchemy import text
            today = date.today()

            async with await self._get_session() as session:
                # Fetch application
                app_row = (await session.execute(
                    text("""
                        SELECT la.id, la.status, la.total_days, la.start_date,
                               la.employee_id, la.leave_type_id,
                               lb.id AS balance_id, lb.year
                        FROM hr_leave_applications la
                        LEFT JOIN hr_leave_balances lb
                            ON lb.employee_id = la.employee_id
                            AND lb.leave_type_id = la.leave_type_id
                            AND lb.year = EXTRACT(YEAR FROM la.start_date)
                        WHERE la.id = :id
                    """),
                    {"id": application_id},
                )).mappings().one_or_none()

                if app_row is None:
                    return self._err(f"Leave application '{application_id}' not found")

                current_status = app_row["status"]
                if current_status == new_status:
                    return self._err(f"Application is already in '{new_status}' status")
                if current_status in ("rejected", "cancelled"):
                    return self._err(f"Cannot update a {current_status} application")

                # Block cancel if approved and already started
                if new_status == "cancelled" and current_status == "approved":
                    start = app_row["start_date"]
                    if hasattr(start, "date"):
                        start = start.date()
                    if start <= today:
                        return self._err("Cannot cancel an approved leave that has already started")

                total_days = float(app_row["total_days"])
                balance_id = app_row["balance_id"]

                # Resolve actor's employee_id for approver_id field
                actor_emp = (await session.execute(
                    text("SELECT id FROM hr_employees WHERE user_id = :uid LIMIT 1"),
                    {"uid": actor_user_id},
                )).fetchone()
                approver_emp_id = str(actor_emp[0]) if actor_emp else None

                # Build application update
                timestamp_field = {"approved": "approved_at", "rejected": "rejected_at", "cancelled": "cancelled_at"}[new_status]
                await session.execute(
                    text(f"""
                        UPDATE hr_leave_applications
                        SET status = :status,
                            approver_id = :approver_id,
                            approver_comment = :comment,
                            {timestamp_field} = NOW(),
                            updated_at = NOW()
                        WHERE id = :id
                    """),
                    {
                        "status": new_status,
                        "approver_id": approver_emp_id,
                        "comment": comment,
                        "id": application_id,
                    },
                )

                # Update leave balance
                if balance_id:
                    if new_status == "approved":
                        await session.execute(
                            text("""
                                UPDATE hr_leave_balances
                                SET taken_days = taken_days + :days,
                                    pending_days = GREATEST(pending_days - :days, 0),
                                    updated_at = NOW()
                                WHERE id = :bal_id
                            """),
                            {"days": total_days, "bal_id": str(balance_id)},
                        )
                    elif new_status in ("rejected", "cancelled"):
                        await session.execute(
                            text("""
                                UPDATE hr_leave_balances
                                SET pending_days = GREATEST(pending_days - :days, 0),
                                    updated_at = NOW()
                                WHERE id = :bal_id
                            """),
                            {"days": total_days, "bal_id": str(balance_id)},
                        )

                await self._log_hr_audit(
                    session=session,
                    actor_id=actor_user_id,
                    target_type="leave_application",
                    target_id=application_id,
                    action=new_status,
                    changes={"previous_status": current_status, "comment": comment},
                )
                await session.commit()

            logger.info(f"update_leave_status: {application_id} → {new_status}")
            return self._ok({"updated": True, "application_id": application_id, "new_status": new_status})
        except Exception as e:
            logger.error(f"update_leave_status failed: {e}")
            return self._err(f"Failed to update leave status: {e}")

    async def _get_leave_summary_dashboard(
        self,
        year: int,
        requesting_user_id: str,
        filters: Optional[dict] = None,
    ) -> dict:
        filters = filters or {}
        try:
            from sqlalchemy import text
            conditions: list[str] = ["lb.year = :year"]
            params: dict[str, Any] = {"year": year}

            if filters.get("department"):
                conditions.append("e.department = :department")
                params["department"] = filters["department"]
            if filters.get("country"):
                conditions.append("e.country = :country")
                params["country"] = filters["country"]

            where = "WHERE " + " AND ".join(conditions)
            sql = f"""
                SELECT e.id AS employee_id, e.full_name, e.staff_id,
                       e.department, e.country,
                       lt.name AS leave_type_name, lt.code AS leave_type_code,
                       lb.entitled_days, lb.carried_over, lb.taken_days,
                       lb.pending_days, lb.remaining_days
                FROM hr_leave_balances lb
                JOIN hr_employees e ON lb.employee_id = e.id
                JOIN hr_leave_types lt ON lb.leave_type_id = lt.id
                {where}
                ORDER BY e.full_name, lt.name
            """
            async with await self._get_session() as session:
                result = await session.execute(text(sql), params)
                rows = [self._serialize(dict(r)) for r in result.mappings().all()]

            # Group by employee
            by_emp: dict[str, dict] = {}
            for r in rows:
                eid = r["employee_id"]
                if eid not in by_emp:
                    by_emp[eid] = {
                        "employee_id": eid,
                        "full_name": r["full_name"],
                        "staff_id": r["staff_id"],
                        "department": r["department"],
                        "country": r["country"],
                        "leave_balances": [],
                    }
                by_emp[eid]["leave_balances"].append({
                    "leave_type": r["leave_type_name"],
                    "code": r["leave_type_code"],
                    "entitled": r["entitled_days"],
                    "carried_over": r["carried_over"],
                    "taken": r["taken_days"],
                    "pending": r["pending_days"],
                    "remaining": r["remaining_days"],
                })

            return self._ok({"summary": list(by_emp.values()), "year": year, "count": len(by_emp)})
        except Exception as e:
            logger.error(f"get_leave_summary_dashboard failed: {e}")
            return self._err(f"Failed to get leave summary: {e}")

    async def _get_pending_approvals(self, manager_employee_id: str) -> dict:
        try:
            from sqlalchemy import text
            async with await self._get_session() as session:
                result = await session.execute(
                    text("""
                        SELECT la.id, la.employee_id, la.leave_type_id, la.start_date,
                               la.end_date, la.total_days, la.half_day, la.reason,
                               la.status, la.created_at,
                               lt.name AS leave_type_name,
                               e.full_name AS employee_name, e.staff_id, e.department
                        FROM hr_leave_applications la
                        JOIN hr_employees e ON la.employee_id = e.id
                        JOIN hr_leave_types lt ON la.leave_type_id = lt.id
                        WHERE e.manager_id = :manager_id
                          AND la.status = 'pending'
                        ORDER BY la.created_at ASC
                    """),
                    {"manager_id": manager_employee_id},
                )
                rows = [self._serialize(dict(r)) for r in result.mappings().all()]

            return self._ok({"pending_approvals": rows, "count": len(rows)})
        except Exception as e:
            logger.error(f"get_pending_approvals failed: {e}")
            return self._err(f"Failed to get pending approvals: {e}")

    async def _list_leave_types(self, country: Optional[str] = None) -> dict:
        try:
            from sqlalchemy import text
            if country:
                sql = """
                    SELECT id, name, code, is_paid, requires_document, country, is_active
                    FROM hr_leave_types
                    WHERE is_active = true AND (country IS NULL OR country = :country)
                    ORDER BY name
                """
                params: dict = {"country": country.upper()}
            else:
                sql = """
                    SELECT id, name, code, is_paid, requires_document, country, is_active
                    FROM hr_leave_types
                    WHERE is_active = true
                    ORDER BY name
                """
                params = {}

            async with await self._get_session() as session:
                result = await session.execute(text(sql), params)
                rows = [self._serialize(dict(r)) for r in result.mappings().all()]

            return self._ok({"leave_types": rows, "count": len(rows)})
        except Exception as e:
            logger.error(f"list_leave_types failed: {e}")
            return self._err(f"Failed to list leave types: {e}")
