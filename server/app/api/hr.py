"""
HR API — employee management and leave management endpoints.

Prefix:  /hr   (registered in main.py)
Auth:    JWT required on all endpoints

RBAC:
  hr_read / management_read  — GET employee list / dashboard
  hr_employee_manage         — POST/PUT/PATCH employees
  hr_self_service            — apply leave, view own leave
  hr_leave_manage            — approve/reject/cancel leave
  hr_reports / management_read — leave summary dashboard

Endpoints:
  GET    /hr/employees                        — list employees
  POST   /hr/employees                        — create employee
  GET    /hr/employees/{id}                   — single employee
  PUT    /hr/employees/{id}                   — update employee
  PATCH  /hr/employees/{id}/status            — activate/deactivate
  GET    /hr/employees/{id}/profile           — rich profile
  GET    /hr/employees/{id}/leave-balance     — leave balances

  POST   /hr/leave/apply                      — submit leave application
  GET    /hr/leave/applications               — list applications
  GET    /hr/leave/applications/{id}          — single application
  PATCH  /hr/leave/applications/{id}/status   — approve/reject/cancel
  GET    /hr/leave/pending-approvals          — pending for manager
  GET    /hr/leave/types                      — active leave types
  GET    /hr/leave/balance                    — current user's balance

  GET    /hr/dashboard/leave-summary          — leave summary dashboard
"""

import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from app.core.dependencies import get_current_user, require_permission

router = APIRouter(tags=["hr"])
logger = logging.getLogger("mezzofy.api.hr")


# ── DTOs ──────────────────────────────────────────────────────────────────────

class EmployeeCreateRequest(BaseModel):
    full_name: str
    email: str
    department: str
    country: str
    hire_date: str
    phone: Optional[str] = None
    job_title: Optional[str] = None
    employment_type: Optional[str] = "full_time"
    location_office: Optional[str] = None
    manager_id: Optional[str] = None
    annual_leave_days: Optional[int] = 14
    sick_leave_days: Optional[int] = 14
    other_leave_days: Optional[int] = 0
    probation_end_date: Optional[str] = None
    profile_notes: Optional[str] = None
    staff_id: Optional[str] = None
    user_id: Optional[str] = None


class EmployeeUpdateRequest(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    job_title: Optional[str] = None
    department: Optional[str] = None
    country: Optional[str] = None
    location_office: Optional[str] = None
    manager_id: Optional[str] = None
    annual_leave_days: Optional[int] = None
    sick_leave_days: Optional[int] = None
    other_leave_days: Optional[int] = None
    employment_type: Optional[str] = None
    probation_end_date: Optional[str] = None
    profile_notes: Optional[str] = None


class EmployeeStatusRequest(BaseModel):
    is_active: bool


class LeaveApplicationRequest(BaseModel):
    employee_id: Optional[str] = None
    leave_type_id: str
    start_date: str
    end_date: str
    total_days: float
    half_day: Optional[bool] = False
    half_day_period: Optional[str] = None
    reason: Optional[str] = None


class LeaveStatusUpdateRequest(BaseModel):
    status: str
    comment: Optional[str] = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ok(data) -> dict:
    return {"success": True, "data": data, "error": None}


def _fail(error: str, code: int = 400):
    raise HTTPException(status_code=code, detail=error)


def _is_hr_role(user: dict) -> bool:
    perms = user.get("permissions", [])
    return "*" in perms or "hr_employee_manage" in perms or "hr_admin" in perms


def _has_perm(user: dict, *permissions: str) -> bool:
    perms = user.get("permissions", [])
    if "*" in perms:
        return True
    return any(p in perms for p in permissions)


# ── Employee endpoints ────────────────────────────────────────────────────────

@router.get("/employees")
async def list_employees(
    department: Optional[str] = Query(None),
    country: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    manager_id: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    current_user: dict = Depends(require_permission("hr_read", "management_read")),
):
    """List employees. HR roles see all; others see only themselves."""
    from app.tools.database.hr_ops import HROps
    from app.core.config import get_config

    user_id = str(current_user.get("user_id", ""))
    filters = {}
    if department:
        filters["department"] = department
    if country:
        filters["country"] = country
    if is_active is not None:
        filters["is_active"] = is_active
    if manager_id:
        filters["manager_id"] = manager_id
    if search:
        filters["search"] = search

    hr = HROps(get_config())
    result = await hr._list_employees(requesting_user_id=user_id, filters=filters)
    if not result.get("success"):
        _fail(result.get("error", "Failed to list employees"))
    return _ok(result["output"])


@router.post("/employees", status_code=status.HTTP_201_CREATED)
async def create_employee(
    body: EmployeeCreateRequest,
    current_user: dict = Depends(require_permission("hr_employee_manage")),
):
    """Create a new employee. Requires hr_employee_manage permission."""
    from app.tools.database.hr_ops import HROps
    from app.core.config import get_config

    user_id = str(current_user.get("user_id", ""))
    hr = HROps(get_config())
    result = await hr._create_employee(
        employee_data=body.model_dump(exclude_none=True),
        created_by_user_id=user_id,
    )
    if not result.get("success"):
        _fail(result.get("error", "Failed to create employee"))
    return _ok(result["output"])


@router.get("/employees/{employee_id}")
async def get_employee(
    employee_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Get a single employee. HR roles see all; others see own record only."""
    from app.tools.database.hr_ops import HROps
    from app.core.config import get_config

    user_id = str(current_user.get("user_id", ""))
    hr = HROps(get_config())
    result = await hr._get_employee(employee_id=employee_id, requesting_user_id=user_id)
    if not result.get("success"):
        _fail(result.get("error", "Employee not found"), 404)
    return _ok(result["output"])


@router.put("/employees/{employee_id}")
async def update_employee(
    employee_id: str,
    body: EmployeeUpdateRequest,
    current_user: dict = Depends(require_permission("hr_employee_manage")),
):
    """Update employee fields. Requires hr_employee_manage."""
    from app.tools.database.hr_ops import HROps
    from app.core.config import get_config

    user_id = str(current_user.get("user_id", ""))
    hr = HROps(get_config())
    result = await hr._update_employee(
        employee_id=employee_id,
        updates=body.model_dump(exclude_none=True),
        updated_by_user_id=user_id,
    )
    if not result.get("success"):
        _fail(result.get("error", "Failed to update employee"))
    return _ok(result["output"])


@router.patch("/employees/{employee_id}/status")
async def set_employee_status(
    employee_id: str,
    body: EmployeeStatusRequest,
    current_user: dict = Depends(require_permission("hr_employee_manage")),
):
    """Activate or deactivate an employee. Requires hr_employee_manage."""
    from app.tools.database.hr_ops import HROps
    from app.core.config import get_config

    user_id = str(current_user.get("user_id", ""))
    hr = HROps(get_config())
    result = await hr._set_employee_status(
        employee_id=employee_id,
        is_active=body.is_active,
        updated_by_user_id=user_id,
    )
    if not result.get("success"):
        _fail(result.get("error", "Failed to update employee status"))
    return _ok(result["output"])


@router.get("/employees/{employee_id}/profile")
async def get_employee_profile(
    employee_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Rich employee profile with leave balances and upcoming leaves."""
    from app.tools.database.hr_ops import HROps
    from app.core.config import get_config

    user_id = str(current_user.get("user_id", ""))
    hr = HROps(get_config())
    result = await hr._get_employee_profile(
        employee_id=employee_id,
        requesting_user_id=user_id,
    )
    if not result.get("success"):
        _fail(result.get("error", "Employee profile not found"), 404)
    return _ok(result["output"])


@router.get("/employees/{employee_id}/leave-balance")
async def get_employee_leave_balance(
    employee_id: str,
    year: int = Query(default=None),
    current_user: dict = Depends(get_current_user),
):
    """Get leave balances for a specific employee."""
    from app.tools.database.hr_ops import HROps
    from app.core.config import get_config

    user_id = str(current_user.get("user_id", ""))
    target_year = year or date.today().year
    hr = HROps(get_config())
    result = await hr._get_leave_balance(
        employee_id=employee_id,
        year=target_year,
        requesting_user_id=user_id,
    )
    if not result.get("success"):
        _fail(result.get("error", "Failed to get leave balance"))
    return _ok(result["output"])


# ── Leave endpoints ───────────────────────────────────────────────────────────

@router.post("/leave/apply", status_code=status.HTTP_201_CREATED)
async def apply_leave(
    body: LeaveApplicationRequest,
    current_user: dict = Depends(require_permission("hr_self_service", "hr_leave_manage")),
):
    """Submit a leave application."""
    from app.tools.database.hr_ops import HROps
    from app.core.config import get_config

    user_id = str(current_user.get("user_id", ""))
    hr = HROps(get_config())

    # Resolve employee_id
    employee_id = body.employee_id
    if not employee_id:
        emp_result = await hr._resolve_employee_by_user(user_id)
        if not emp_result.get("success"):
            _fail("No employee record found for your account. Contact HR.", 404)
        employee_id = emp_result["output"]["id"]

    result = await hr._apply_leave(
        application_data=body.model_dump(exclude={"employee_id"}),
        employee_id=employee_id,
        actor_user_id=user_id,
    )
    if not result.get("success"):
        _fail(result.get("error", "Failed to apply for leave"))
    return _ok(result["output"])


@router.get("/leave/applications")
async def list_leave_applications(
    employee_id: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    leave_type_id: Optional[str] = Query(None),
    year: Optional[int] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
):
    """List leave applications with optional filters.

    Self-service users (no hr_read / hr_leave_manage / hr_reports / management_read)
    are automatically scoped to their own employee record only.
    """
    from app.tools.database.hr_ops import HROps
    from app.core.config import get_config

    user_id = str(current_user.get("user_id", ""))
    filters = {}
    if employee_id:
        filters["employee_id"] = employee_id
    if status_filter:
        filters["status"] = status_filter
    if leave_type_id:
        filters["leave_type_id"] = leave_type_id
    if year:
        filters["year"] = year
    if date_from:
        filters["date_from"] = date_from
    if date_to:
        filters["date_to"] = date_to

    hr = HROps(get_config())

    # Self-service scoping: if the user lacks any manager-level HR permission,
    # auto-resolve their user_id → employee_id and restrict results to that employee.
    _manager_perms = ("hr_read", "hr_leave_manage", "hr_reports", "management_read")
    is_hr_manager = _has_perm(current_user, *_manager_perms)

    if not is_hr_manager and not filters.get("employee_id"):
        emp_result = await hr._resolve_employee_by_user(user_id)
        if not emp_result.get("success"):
            # No linked employee record → return empty result gracefully
            return _ok({"applications": [], "count": 0})
        filters["employee_id"] = emp_result["output"]["id"]

    result = await hr._get_leave_applications(requesting_user_id=user_id, filters=filters)
    if not result.get("success"):
        _fail(result.get("error", "Failed to get leave applications"))
    return _ok(result["output"])


@router.get("/leave/applications/{application_id}")
async def get_leave_application(
    application_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Get a single leave application by ID."""
    from app.tools.database.hr_ops import HROps
    from app.core.config import get_config

    user_id = str(current_user.get("user_id", ""))
    hr = HROps(get_config())
    result = await hr._get_leave_applications(
        requesting_user_id=user_id,
        filters={"employee_id": None},
    )
    # Filter to single application
    if result.get("success"):
        apps = result["output"].get("applications", [])
        app = next((a for a in apps if str(a.get("id")) == application_id), None)
        if app:
            return _ok({"application": app})
    _fail("Leave application not found", 404)


@router.patch("/leave/applications/{application_id}/status")
async def update_leave_status(
    application_id: str,
    body: LeaveStatusUpdateRequest,
    current_user: dict = Depends(require_permission("hr_leave_manage", "hr_self_service")),
):
    """Approve, reject, or cancel a leave application."""
    from app.tools.database.hr_ops import HROps
    from app.core.config import get_config

    user_id = str(current_user.get("user_id", ""))
    hr = HROps(get_config())
    result = await hr._update_leave_status(
        application_id=application_id,
        new_status=body.status,
        comment=body.comment,
        actor_user_id=user_id,
    )
    if not result.get("success"):
        _fail(result.get("error", "Failed to update leave status"))
    return _ok(result["output"])


_HR_ADMIN_ROLES = {"admin", "executive", "management", "hr_staff", "hr_manager"}


@router.get("/leave/pending-approvals")
async def get_pending_approvals(
    current_user: dict = Depends(get_current_user),
):
    """
    Get pending leave applications.
    HR admins (admin/executive/management/hr_staff/hr_manager) see ALL pending.
    Managers see only their direct reports. Others get an empty list.
    """
    from app.tools.database.hr_ops import HROps
    from app.core.config import get_config

    user_id = str(current_user.get("user_id", ""))
    user_role = current_user.get("role", "")
    permissions = current_user.get("permissions", [])
    hr = HROps(get_config())

    is_hr_admin = (
        user_role in _HR_ADMIN_ROLES
        or "*" in permissions
        or "hr_leave_manage" in permissions
    )

    if is_hr_admin:
        # Return all pending leaves — admin/HR overview
        result = await hr._get_pending_approvals(manager_employee_id=None)
    else:
        # Scoped to direct reports of this manager
        emp_result = await hr._resolve_employee_by_user(user_id)
        if not emp_result.get("success"):
            return _ok({"pending_approvals": [], "count": 0})
        manager_employee_id = emp_result["output"]["id"]
        result = await hr._get_pending_approvals(manager_employee_id=manager_employee_id)

    if not result.get("success"):
        _fail(result.get("error", "Failed to get pending approvals"))
    return _ok(result["output"])


@router.get("/leave/types")
async def list_leave_types(
    country: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
):
    """List active leave types. Any authenticated user."""
    from app.tools.database.hr_ops import HROps
    from app.core.config import get_config

    hr = HROps(get_config())
    result = await hr._list_leave_types(country=country)
    if not result.get("success"):
        _fail(result.get("error", "Failed to list leave types"))
    return _ok(result["output"])


@router.get("/leave/balance")
async def get_my_leave_balance(
    year: Optional[int] = Query(None),
    current_user: dict = Depends(require_permission("hr_self_service", "hr_read")),
):
    """Get leave balance for the currently authenticated user's employee record."""
    from app.tools.database.hr_ops import HROps
    from app.core.config import get_config

    user_id = str(current_user.get("user_id", ""))
    hr = HROps(get_config())

    emp_result = await hr._resolve_employee_by_user(user_id)
    if not emp_result.get("success"):
        _fail("No employee record linked to your account. Contact HR.", 404)

    employee_id = emp_result["output"]["id"]
    target_year = year or date.today().year
    result = await hr._get_leave_balance(
        employee_id=employee_id,
        year=target_year,
        requesting_user_id=user_id,
    )
    if not result.get("success"):
        _fail(result.get("error", "Failed to get leave balance"))
    return _ok(result["output"])


# ── Dashboard endpoints ───────────────────────────────────────────────────────

@router.get("/dashboard/leave-summary")
async def get_leave_summary_dashboard(
    year: Optional[int] = Query(None),
    department: Optional[str] = Query(None),
    country: Optional[str] = Query(None),
    current_user: dict = Depends(require_permission("hr_reports", "management_read")),
):
    """Leave summary dashboard. Requires hr_reports or management_read."""
    from app.tools.database.hr_ops import HROps
    from app.core.config import get_config

    user_id = str(current_user.get("user_id", ""))
    target_year = year or date.today().year
    filters = {}
    if department:
        filters["department"] = department
    if country:
        filters["country"] = country

    hr = HROps(get_config())
    result = await hr._get_leave_summary_dashboard(
        year=target_year,
        filters=filters,
        requesting_user_id=user_id,
    )
    if not result.get("success"):
        _fail(result.get("error", "Failed to get leave summary"))
    return _ok(result["output"])
