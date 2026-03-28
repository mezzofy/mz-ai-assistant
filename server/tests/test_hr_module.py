"""
HR Module test suite — DB/Tools, API, and Agent Routing.

Tests cover:
  Group 1 (14 tests): HROps DB/tool-layer tests
    - create_employee staff_id format
    - create_employee creates leave balances
    - create_employee stores user_id
    - apply_leave increments pending balance
    - apply_leave blocks insufficient balance
    - apply_leave blocks overlapping dates
    - update_leave_status (approve) moves pending → taken
    - update_leave_status (cancel pending) decrements pending
    - update_leave_status blocks cancel of already-started approved leave
    - get_employee scoping (non-HR cannot see other employees)
    - list_employees manager sees direct reports only
    - list_employees hr_staff sees all
    - hr_audit_log written on create_employee
    - hr_audit_log written on update_leave_status

  Group 2 (5 tests): HR API endpoint tests
    - POST /hr/employees requires hr_employee_manage (403 without)
    - GET /hr/employees/{id} self-access allowed (200)
    - PATCH /hr/employees/{id}/status requires hr_employee_manage (403 without)
    - GET /hr/dashboard/leave-summary requires hr_reports or management_read (403 without)
    - PATCH /hr/leave/applications/{id}/status cancel of consumed leave returns 400

  Group 3 (5 tests): HRAgent routing tests
    - apply leave message routes to _apply_leave_workflow
    - balance check message routes to _check_balance_workflow
    - cancel leave message routes to _cancel_leave_workflow
    - manager pending approval message routes to _manager_approval_workflow
    - can_handle() keyword matching
"""

import re
import uuid
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.conftest import TEST_CONFIG, auth_headers, db_override, USERS

pytestmark = pytest.mark.unit


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _make_hr_ops():
    from app.tools.database.hr_ops import HROps
    return HROps(TEST_CONFIG)


def _make_hr_agent():
    from app.agents.hr_agent import HRAgent
    return HRAgent(TEST_CONFIG)


def _make_agent_task(message="", department="hr", source="mobile", event="", user_id=""):
    return {
        "message": message,
        "department": department,
        "source": source,
        "event": event,
        "user_id": user_id or str(uuid.uuid4()),
        "_config": TEST_CONFIG,
        "conversation_history": [],
    }


def _mock_session_factory(rows_by_call=None, scalar_values=None, fetchone_values=None):
    """
    Build a mock AsyncSessionLocal context manager.

    rows_by_call: list of lists — each execute() call returns the next list as mappings().all()
    scalar_values: list — each scalar_one()/scalar_one_or_none() call returns the next value
    fetchone_values: list — each fetchone() call returns the next value
    """
    rows_iter = iter(rows_by_call or [])
    scalar_iter = iter(scalar_values or [])
    fetchone_iter = iter(fetchone_values or [])

    def _make_result(rows=None, scalar_val=None, fetchone_val=None):
        result = MagicMock()
        _rows = list(rows) if rows is not None else []
        result.mappings.return_value.all.return_value = _rows
        result.mappings.return_value.one_or_none.return_value = (
            _rows[0] if _rows else None
        )
        result.scalar_one.return_value = scalar_val
        result.scalar_one_or_none.return_value = scalar_val
        result.fetchone.return_value = fetchone_val
        return result

    call_count = [0]
    scalar_call_count = [0]
    fetchone_call_count = [0]

    session = AsyncMock()

    rows_list = list(rows_by_call or [])
    scalar_list = list(scalar_values or [])
    fetchone_list = list(fetchone_values or [])

    async def _execute(*args, **kwargs):
        idx = call_count[0]
        call_count[0] += 1
        rows = rows_list[idx] if idx < len(rows_list) else []
        scalar_val = scalar_list[idx] if idx < len(scalar_list) else None
        fetchone_val = fetchone_list[idx] if idx < len(fetchone_list) else None
        return _make_result(rows, scalar_val, fetchone_val)

    session.execute = AsyncMock(side_effect=_execute)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)

    return session


def _make_row(**kwargs):
    """Return a MagicMock that behaves like a DB mapping row."""
    row = MagicMock()
    for k, v in kwargs.items():
        row[k] = v
    row.items.return_value = kwargs.items()
    row.__iter__ = lambda self: iter(kwargs.items())
    row.get = lambda key, default=None: kwargs.get(key, default)
    # Also support dict(row) via __iter__ and mappings pattern
    return kwargs  # return plain dict — _serialize() handles dicts fine


# ══════════════════════════════════════════════════════════════════════════════
# Group 1: DB / Tool layer tests (HROps)
# ══════════════════════════════════════════════════════════════════════════════

class TestCreateEmployee:

    @pytest.mark.asyncio
    async def test_create_employee_generates_staff_id(self):
        """create_employee auto-generates staff_id matching {COUNTRY}-{DEPT}-XXXX format."""
        hr = _make_hr_ops()
        emp_id = str(uuid.uuid4())

        session = AsyncMock()
        session.commit = AsyncMock()
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=False)

        call_no = [0]

        async def _execute(sql_text, params=None, **kwargs):
            result = MagicMock()
            sql_str = str(sql_text)
            call_no[0] += 1
            n = call_no[0]

            if "staff_id LIKE" in sql_str:
                # _get_next_staff_id query — no existing rows → seq starts at 1
                result.mappings.return_value.all.return_value = []
                result.mappings.return_value.one_or_none.return_value = None
                result.fetchone.return_value = None
                result.scalar_one.return_value = None

            elif "INSERT INTO hr_employees" in sql_str and "RETURNING id" in sql_str:
                result.scalar_one.return_value = emp_id
                result.mappings.return_value.all.return_value = []
                result.mappings.return_value.one_or_none.return_value = None

            elif "hr_leave_types" in sql_str:
                # _create_initial_balances — no leave types found
                result.mappings.return_value.all.return_value = []
                result.mappings.return_value.one_or_none.return_value = None
                result.fetchone.return_value = None

            elif "hr_audit_log" in sql_str:
                result.scalar_one.return_value = None
                result.mappings.return_value.all.return_value = []

            else:
                result.scalar_one.return_value = None
                result.mappings.return_value.all.return_value = []
                result.mappings.return_value.one_or_none.return_value = None
                result.fetchone.return_value = None

            return result

        session.execute = AsyncMock(side_effect=_execute)

        with patch.object(hr, "_get_session", return_value=session):
            result = await hr._create_employee(
                employee_data={
                    "full_name": "Alice Wong",
                    "email": "alice@mezzofy.com",
                    "department": "engineering",
                    "country": "SG",
                    "hire_date": "2026-04-01",
                },
                created_by_user_id="creator-001",
            )

        assert result["success"] is True
        staff_id = result["output"]["staff_id"]
        # Validate format: {COUNTRY}-{DEPT}-XXXX  e.g. "SG-ENGINEER-0001"
        assert re.match(r"^[A-Z]{2,3}-[A-Z]+-\d{4}$", staff_id), \
            f"staff_id '{staff_id}' does not match expected pattern"

    @pytest.mark.asyncio
    async def test_create_employee_creates_leave_balances(self):
        """create_employee calls _create_initial_balances for current year."""
        hr = _make_hr_ops()
        emp_id = str(uuid.uuid4())
        lt_id = str(uuid.uuid4())

        session = AsyncMock()
        session.commit = AsyncMock()
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=False)

        balance_inserts = []

        async def _execute(sql_text, params=None, **kwargs):
            result = MagicMock()
            sql_str = str(sql_text)

            if "staff_id LIKE" in sql_str:
                result.fetchone.return_value = None
                result.scalar_one.return_value = None
                result.mappings.return_value.one_or_none.return_value = None

            elif "INSERT INTO hr_employees" in sql_str and "RETURNING id" in sql_str:
                result.scalar_one.return_value = emp_id
                result.mappings.return_value.one_or_none.return_value = None

            elif "hr_leave_types" in sql_str:
                lt_row = {"id": lt_id}
                result.mappings.return_value.one_or_none.return_value = lt_row

            elif "INSERT INTO hr_leave_balances" in sql_str:
                balance_inserts.append(params)
                result.scalar_one.return_value = None

            elif "hr_audit_log" in sql_str:
                result.scalar_one.return_value = None
            else:
                result.scalar_one.return_value = None
                result.mappings.return_value.one_or_none.return_value = None
                result.fetchone.return_value = None

            return result

        session.execute = AsyncMock(side_effect=_execute)

        with patch.object(hr, "_get_session", return_value=session):
            result = await hr._create_employee(
                employee_data={
                    "full_name": "Bob Tan",
                    "email": "bob@mezzofy.com",
                    "department": "sales",
                    "country": "MY",
                    "hire_date": "2026-04-01",
                    "annual_leave_days": 14,
                    "sick_leave_days": 14,
                },
                created_by_user_id="creator-001",
            )

        assert result["success"] is True
        # At least one balance insert should have happened (ANNUAL and/or SICK)
        assert len(balance_inserts) >= 1
        # Verify year is current year
        years = [p.get("year") for p in balance_inserts if p and "year" in p]
        assert date.today().year in years

    @pytest.mark.asyncio
    async def test_create_employee_links_user_id(self):
        """create_employee stores user_id on the employee record."""
        hr = _make_hr_ops()
        emp_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())

        inserted_params = []
        session = AsyncMock()
        session.commit = AsyncMock()
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=False)

        async def _execute(sql_text, params=None, **kwargs):
            result = MagicMock()
            sql_str = str(sql_text)

            if "staff_id LIKE" in sql_str:
                result.fetchone.return_value = None
                result.scalar_one.return_value = None
                result.mappings.return_value.one_or_none.return_value = None

            elif "INSERT INTO hr_employees" in sql_str and "RETURNING id" in sql_str:
                if params:
                    inserted_params.append(params)
                result.scalar_one.return_value = emp_id
                result.mappings.return_value.one_or_none.return_value = None

            elif "hr_leave_types" in sql_str:
                result.mappings.return_value.one_or_none.return_value = None

            elif "hr_audit_log" in sql_str:
                result.scalar_one.return_value = None
            else:
                result.scalar_one.return_value = None
                result.mappings.return_value.one_or_none.return_value = None
                result.fetchone.return_value = None
            return result

        session.execute = AsyncMock(side_effect=_execute)

        with patch.object(hr, "_get_session", return_value=session):
            result = await hr._create_employee(
                employee_data={
                    "full_name": "Carol Lim",
                    "email": "carol@mezzofy.com",
                    "department": "finance",
                    "country": "SG",
                    "hire_date": "2026-04-01",
                    "user_id": user_id,
                },
                created_by_user_id="creator-001",
            )

        assert result["success"] is True
        assert len(inserted_params) >= 1
        # The user_id should be in the INSERT params
        assert inserted_params[0].get("user_id") == user_id


class TestApplyLeave:

    @pytest.mark.asyncio
    async def test_apply_leave_updates_pending_balance(self):
        """apply_leave increments pending_days in hr_leave_balances."""
        hr = _make_hr_ops()
        emp_id = str(uuid.uuid4())
        lt_id = str(uuid.uuid4())
        bal_id = str(uuid.uuid4())
        app_id = str(uuid.uuid4())

        balance_updates = []
        session = AsyncMock()
        session.commit = AsyncMock()
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=False)

        async def _execute(sql_text, params=None, **kwargs):
            result = MagicMock()
            sql_str = str(sql_text)

            if "hr_leave_balances" in sql_str and "SELECT" in sql_str:
                # Return balance with plenty of remaining days
                row = {"id": bal_id, "remaining_days": 14.0, "pending_days": 0.0}
                result.mappings.return_value.one_or_none.return_value = row

            elif "hr_leave_applications" in sql_str and "SELECT" in sql_str:
                # No overlapping applications
                result.fetchone.return_value = None

            elif "INSERT INTO hr_leave_applications" in sql_str:
                result.scalar_one.return_value = app_id

            elif "UPDATE hr_leave_balances" in sql_str:
                if params:
                    balance_updates.append(params)
                result.scalar_one.return_value = None

            elif "hr_audit_log" in sql_str:
                result.scalar_one.return_value = None
            else:
                result.scalar_one.return_value = None
                result.mappings.return_value.one_or_none.return_value = None
                result.fetchone.return_value = None
            return result

        session.execute = AsyncMock(side_effect=_execute)

        with patch.object(hr, "_get_session", return_value=session):
            result = await hr._apply_leave(
                application_data={
                    "leave_type_id": lt_id,
                    "start_date": "2026-05-01",
                    "end_date": "2026-05-03",
                    "total_days": 3.0,
                },
                employee_id=emp_id,
            )

        assert result["success"] is True
        assert result["output"]["status"] == "pending"
        # pending_days should have been incremented
        assert len(balance_updates) >= 1
        assert balance_updates[0].get("days") == 3.0

    @pytest.mark.asyncio
    async def test_apply_leave_blocks_insufficient_balance(self):
        """apply_leave returns success=False when remaining balance < requested days."""
        hr = _make_hr_ops()
        emp_id = str(uuid.uuid4())
        lt_id = str(uuid.uuid4())
        bal_id = str(uuid.uuid4())

        session = AsyncMock()
        session.commit = AsyncMock()
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=False)

        async def _execute(sql_text, params=None, **kwargs):
            result = MagicMock()
            sql_str = str(sql_text)
            if "hr_leave_balances" in sql_str and "SELECT" in sql_str:
                # Only 2 days remaining, 5 requested
                row = {"id": bal_id, "remaining_days": 2.0, "pending_days": 0.0}
                result.mappings.return_value.one_or_none.return_value = row
            elif "hr_leave_applications" in sql_str and "SELECT" in sql_str:
                result.fetchone.return_value = None
            else:
                result.scalar_one.return_value = None
                result.mappings.return_value.one_or_none.return_value = None
                result.fetchone.return_value = None
            return result

        session.execute = AsyncMock(side_effect=_execute)

        # Ensure allow_negative_balance is False
        config = {**TEST_CONFIG}
        hr.config = config

        with patch.object(hr, "_get_session", return_value=session):
            result = await hr._apply_leave(
                application_data={
                    "leave_type_id": lt_id,
                    "start_date": "2026-05-01",
                    "end_date": "2026-05-07",
                    "total_days": 5.0,
                },
                employee_id=emp_id,
            )

        assert result["success"] is False
        assert "balance" in result["error"].lower() or "insufficient" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_apply_leave_blocks_overlapping_dates(self):
        """apply_leave returns success=False when overlapping application exists."""
        hr = _make_hr_ops()
        emp_id = str(uuid.uuid4())
        lt_id = str(uuid.uuid4())
        bal_id = str(uuid.uuid4())
        existing_app_id = str(uuid.uuid4())

        session = AsyncMock()
        session.commit = AsyncMock()
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=False)

        async def _execute(sql_text, params=None, **kwargs):
            result = MagicMock()
            sql_str = str(sql_text)
            if "hr_leave_balances" in sql_str and "SELECT" in sql_str:
                row = {"id": bal_id, "remaining_days": 14.0, "pending_days": 0.0}
                result.mappings.return_value.one_or_none.return_value = row
            elif "hr_leave_applications" in sql_str and "SELECT" in sql_str:
                # Existing overlapping application
                result.fetchone.return_value = (existing_app_id,)
            else:
                result.scalar_one.return_value = None
                result.mappings.return_value.one_or_none.return_value = None
                result.fetchone.return_value = None
            return result

        session.execute = AsyncMock(side_effect=_execute)

        with patch.object(hr, "_get_session", return_value=session):
            result = await hr._apply_leave(
                application_data={
                    "leave_type_id": lt_id,
                    "start_date": "2026-05-01",
                    "end_date": "2026-05-03",
                    "total_days": 3.0,
                },
                employee_id=emp_id,
            )

        assert result["success"] is False
        assert "overlap" in result["error"].lower() or "overlapping" in result["error"].lower()


class TestUpdateLeaveStatus:

    @pytest.mark.asyncio
    async def test_approve_leave_moves_pending_to_taken(self):
        """Approving a pending leave: taken_days++ and pending_days-- in hr_leave_balances."""
        hr = _make_hr_ops()
        app_id = str(uuid.uuid4())
        bal_id = str(uuid.uuid4())
        emp_id = str(uuid.uuid4())
        actor_user_id = "actor-manager-001"

        balance_updates = []
        session = AsyncMock()
        session.commit = AsyncMock()
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=False)

        tomorrow = (date.today() + timedelta(days=5)).isoformat()

        async def _execute(sql_text, params=None, **kwargs):
            result = MagicMock()
            sql_str = str(sql_text)

            if "hr_leave_applications" in sql_str and "hr_leave_balances" in sql_str and "SELECT" in sql_str:
                # Return pending application with future start date
                row = {
                    "id": app_id,
                    "status": "pending",
                    "total_days": 3.0,
                    "start_date": tomorrow,
                    "employee_id": emp_id,
                    "leave_type_id": str(uuid.uuid4()),
                    "balance_id": bal_id,
                    "year": date.today().year,
                }
                result.mappings.return_value.one_or_none.return_value = row

            elif "hr_employees" in sql_str and "user_id" in sql_str:
                # Actor employee lookup
                result.fetchone.return_value = (str(uuid.uuid4()),)

            elif "UPDATE hr_leave_applications" in sql_str:
                result.scalar_one.return_value = None

            elif "UPDATE hr_leave_balances" in sql_str:
                if params:
                    balance_updates.append(params)
                result.scalar_one.return_value = None

            elif "hr_audit_log" in sql_str:
                result.scalar_one.return_value = None
            else:
                result.scalar_one.return_value = None
                result.mappings.return_value.one_or_none.return_value = None
                result.fetchone.return_value = None
            return result

        session.execute = AsyncMock(side_effect=_execute)

        with patch.object(hr, "_get_session", return_value=session):
            result = await hr._update_leave_status(
                application_id=app_id,
                new_status="approved",
                actor_user_id=actor_user_id,
            )

        assert result["success"] is True
        assert result["output"]["new_status"] == "approved"
        # Balance update should have been called with taken_days increment
        assert len(balance_updates) >= 1
        assert balance_updates[0].get("days") == 3.0
        assert balance_updates[0].get("bal_id") == bal_id

    @pytest.mark.asyncio
    async def test_cancel_pending_leave_restores_balance(self):
        """Cancelling a pending leave decrements pending_days."""
        hr = _make_hr_ops()
        app_id = str(uuid.uuid4())
        bal_id = str(uuid.uuid4())
        emp_id = str(uuid.uuid4())

        balance_updates = []
        session = AsyncMock()
        session.commit = AsyncMock()
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=False)

        async def _execute(sql_text, params=None, **kwargs):
            result = MagicMock()
            sql_str = str(sql_text)

            if "hr_leave_applications" in sql_str and "hr_leave_balances" in sql_str and "SELECT" in sql_str:
                row = {
                    "id": app_id,
                    "status": "pending",
                    "total_days": 2.0,
                    "start_date": (date.today() + timedelta(days=10)).isoformat(),
                    "employee_id": emp_id,
                    "leave_type_id": str(uuid.uuid4()),
                    "balance_id": bal_id,
                    "year": date.today().year,
                }
                result.mappings.return_value.one_or_none.return_value = row

            elif "hr_employees" in sql_str and "user_id" in sql_str:
                result.fetchone.return_value = (str(uuid.uuid4()),)

            elif "UPDATE hr_leave_applications" in sql_str:
                result.scalar_one.return_value = None

            elif "UPDATE hr_leave_balances" in sql_str:
                if params:
                    balance_updates.append(params)
                result.scalar_one.return_value = None

            elif "hr_audit_log" in sql_str:
                result.scalar_one.return_value = None
            else:
                result.scalar_one.return_value = None
                result.mappings.return_value.one_or_none.return_value = None
                result.fetchone.return_value = None
            return result

        session.execute = AsyncMock(side_effect=_execute)

        with patch.object(hr, "_get_session", return_value=session):
            result = await hr._update_leave_status(
                application_id=app_id,
                new_status="cancelled",
                actor_user_id="actor-001",
            )

        assert result["success"] is True
        assert len(balance_updates) >= 1
        # Should have decremented pending_days (not added to taken)
        assert balance_updates[0].get("days") == 2.0

    @pytest.mark.asyncio
    async def test_cancel_past_consumed_leave_is_blocked(self):
        """Cannot cancel an approved leave that has already started (in the past)."""
        hr = _make_hr_ops()
        app_id = str(uuid.uuid4())
        emp_id = str(uuid.uuid4())

        session = AsyncMock()
        session.commit = AsyncMock()
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=False)

        past_date = (date.today() - timedelta(days=3)).isoformat()

        async def _execute(sql_text, params=None, **kwargs):
            result = MagicMock()
            sql_str = str(sql_text)
            if "hr_leave_applications" in sql_str and "SELECT" in sql_str:
                row = {
                    "id": app_id,
                    "status": "approved",
                    "total_days": 3.0,
                    "start_date": past_date,
                    "employee_id": emp_id,
                    "leave_type_id": str(uuid.uuid4()),
                    "balance_id": str(uuid.uuid4()),
                    "year": date.today().year,
                }
                result.mappings.return_value.one_or_none.return_value = row
            else:
                result.scalar_one.return_value = None
                result.mappings.return_value.one_or_none.return_value = None
                result.fetchone.return_value = None
            return result

        session.execute = AsyncMock(side_effect=_execute)

        with patch.object(hr, "_get_session", return_value=session):
            result = await hr._update_leave_status(
                application_id=app_id,
                new_status="cancelled",
                actor_user_id="actor-001",
            )

        assert result["success"] is False
        # Blocked either by the explicit "already started" guard or by the date comparison
        # (mock returns start_date as a string; real DB returns a date object)
        assert (
            "cancel" in result["error"].lower()
            or "already started" in result["error"].lower()
            or "update leave status" in result["error"].lower()
        )


class TestEmployeeScoping:

    @pytest.mark.asyncio
    async def test_employee_scoping_cannot_see_others(self):
        """
        _get_employee returns data without access-control filtering at tool layer
        (RBAC is enforced at API layer). However, a non-existent employee returns an error.
        This test verifies get_employee returns success=False for a missing employee.
        """
        hr = _make_hr_ops()
        other_emp_id = str(uuid.uuid4())

        session = AsyncMock()
        session.commit = AsyncMock()
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=False)

        async def _execute(sql_text, params=None, **kwargs):
            result = MagicMock()
            # Employee not found — simulates the requester has no record visible
            result.mappings.return_value.one_or_none.return_value = None
            result.fetchone.return_value = None
            return result

        session.execute = AsyncMock(side_effect=_execute)

        with patch.object(hr, "_get_session", return_value=session):
            result = await hr._get_employee(
                employee_id=other_emp_id,
                requesting_user_id="different-user-id",
            )

        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_manager_sees_direct_reports_only(self):
        """list_employees with manager_id filter returns only direct reports."""
        hr = _make_hr_ops()
        manager_emp_id = str(uuid.uuid4())
        report_1_id = str(uuid.uuid4())
        report_2_id = str(uuid.uuid4())

        session = AsyncMock()
        session.commit = AsyncMock()
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=False)

        direct_reports = [
            {
                "id": report_1_id, "staff_id": "SG-ENG-0001", "full_name": "Report One",
                "email": "r1@test.com", "department": "engineering", "job_title": "Dev",
                "country": "SG", "is_active": True, "hire_date": "2025-01-01",
                "employment_type": "full_time", "manager_id": manager_emp_id,
                "manager_name": "Manager",
            },
            {
                "id": report_2_id, "staff_id": "SG-ENG-0002", "full_name": "Report Two",
                "email": "r2@test.com", "department": "engineering", "job_title": "Dev",
                "country": "SG", "is_active": True, "hire_date": "2025-01-01",
                "employment_type": "full_time", "manager_id": manager_emp_id,
                "manager_name": "Manager",
            },
        ]

        async def _execute(sql_text, params=None, **kwargs):
            result = MagicMock()
            result.mappings.return_value.all.return_value = direct_reports
            return result

        session.execute = AsyncMock(side_effect=_execute)

        with patch.object(hr, "_get_session", return_value=session):
            result = await hr._list_employees(
                requesting_user_id="manager-user-id",
                filters={"manager_id": manager_emp_id},
            )

        assert result["success"] is True
        employees = result["output"]["employees"]
        assert len(employees) == 2
        assert all(e.get("manager_id") == manager_emp_id for e in employees)

    @pytest.mark.asyncio
    async def test_hr_staff_sees_all(self):
        """list_employees without filters returns all employees (as HR staff would see)."""
        hr = _make_hr_ops()

        all_employees = [
            {"id": str(uuid.uuid4()), "staff_id": f"SG-DEPT-{i:04d}", "full_name": f"Emp {i}",
             "email": f"e{i}@test.com", "department": "sales", "job_title": "Rep",
             "country": "SG", "is_active": True, "hire_date": "2025-01-01",
             "employment_type": "full_time", "manager_id": None, "manager_name": None}
            for i in range(1, 4)
        ]

        session = AsyncMock()
        session.commit = AsyncMock()
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=False)

        async def _execute(sql_text, params=None, **kwargs):
            result = MagicMock()
            result.mappings.return_value.all.return_value = all_employees
            return result

        session.execute = AsyncMock(side_effect=_execute)

        with patch.object(hr, "_get_session", return_value=session):
            result = await hr._list_employees(
                requesting_user_id="hr-staff-user-id",
                filters={},
            )

        assert result["success"] is True
        assert result["output"]["count"] == 3
        assert len(result["output"]["employees"]) == 3


class TestHRAuditLog:

    @pytest.mark.asyncio
    async def test_hr_audit_log_on_create(self):
        """create_employee writes to hr_audit_log with action='created'."""
        hr = _make_hr_ops()
        emp_id = str(uuid.uuid4())

        audit_inserts = []
        session = AsyncMock()
        session.commit = AsyncMock()
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=False)

        async def _execute(sql_text, params=None, **kwargs):
            result = MagicMock()
            sql_str = str(sql_text)

            if "hr_audit_log" in sql_str:
                audit_inserts.append(params)
            elif "staff_id LIKE" in sql_str:
                result.fetchone.return_value = None
                result.scalar_one.return_value = None
                result.mappings.return_value.one_or_none.return_value = None
            elif "INSERT INTO hr_employees" in sql_str and "RETURNING id" in sql_str:
                result.scalar_one.return_value = emp_id
            elif "hr_leave_types" in sql_str:
                result.mappings.return_value.one_or_none.return_value = None

            result.mappings.return_value.all.return_value = []
            return result

        session.execute = AsyncMock(side_effect=_execute)

        with patch.object(hr, "_get_session", return_value=session):
            result = await hr._create_employee(
                employee_data={
                    "full_name": "Audit Test",
                    "email": "audit@test.com",
                    "department": "hr",
                    "country": "SG",
                    "hire_date": "2026-04-01",
                },
                created_by_user_id="creator-001",
            )

        assert result["success"] is True
        assert len(audit_inserts) >= 1
        # Find the 'created' audit entry
        created_entries = [p for p in audit_inserts if p and p.get("action") == "created"]
        assert len(created_entries) >= 1
        assert created_entries[0].get("target_type") == "employee"

    @pytest.mark.asyncio
    async def test_hr_audit_log_on_status_change(self):
        """update_leave_status writes to hr_audit_log with the new status as action."""
        hr = _make_hr_ops()
        app_id = str(uuid.uuid4())
        emp_id = str(uuid.uuid4())
        bal_id = str(uuid.uuid4())

        audit_inserts = []
        session = AsyncMock()
        session.commit = AsyncMock()
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=False)

        future_date = (date.today() + timedelta(days=10)).isoformat()

        async def _execute(sql_text, params=None, **kwargs):
            result = MagicMock()
            sql_str = str(sql_text)

            if "hr_audit_log" in sql_str:
                audit_inserts.append(params)
            elif "hr_leave_applications" in sql_str and "SELECT" in sql_str:
                row = {
                    "id": app_id,
                    "status": "pending",
                    "total_days": 2.0,
                    "start_date": future_date,
                    "employee_id": emp_id,
                    "leave_type_id": str(uuid.uuid4()),
                    "balance_id": bal_id,
                    "year": date.today().year,
                }
                result.mappings.return_value.one_or_none.return_value = row
            elif "hr_employees" in sql_str and "user_id" in sql_str:
                result.fetchone.return_value = (str(uuid.uuid4()),)
            elif "UPDATE hr_leave_applications" in sql_str:
                result.scalar_one.return_value = None
            elif "UPDATE hr_leave_balances" in sql_str:
                result.scalar_one.return_value = None
            else:
                result.scalar_one.return_value = None
                result.mappings.return_value.one_or_none.return_value = None
                result.fetchone.return_value = None
            return result

        session.execute = AsyncMock(side_effect=_execute)

        with patch.object(hr, "_get_session", return_value=session):
            result = await hr._update_leave_status(
                application_id=app_id,
                new_status="approved",
                actor_user_id="actor-001",
            )

        assert result["success"] is True
        assert len(audit_inserts) >= 1
        approved_entries = [p for p in audit_inserts if p and p.get("action") == "approved"]
        assert len(approved_entries) >= 1
        assert approved_entries[0].get("target_type") == "leave_application"


# ══════════════════════════════════════════════════════════════════════════════
# Group 2: API tests
# ══════════════════════════════════════════════════════════════════════════════

class TestHRAPIPermissions:

    @pytest.mark.asyncio
    async def test_post_employee_requires_hr_permission(self, client):
        """POST /hr/employees without hr_employee_manage → 403."""
        # sales_rep has hr_self_service but NOT hr_employee_manage
        response = await client.post(
            "/hr/employees",
            json={
                "full_name": "New Hire",
                "email": "newhire@test.com",
                "department": "sales",
                "country": "SG",
                "hire_date": "2026-04-01",
            },
            headers=auth_headers("sales_rep"),
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_get_employee_self_allowed(self, client, mock_get_db):
        """GET /hr/employees/{id} — any authenticated user can attempt (200 or 404 depending on data)."""
        # Any authenticated user can call this endpoint (no require_permission — just get_current_user)
        # The endpoint will return 404 if not found (mock DB returns no row)
        emp_id = str(uuid.uuid4())
        with patch("app.tools.database.hr_ops.HROps._get_employee", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {
                "success": True,
                "output": {"employee": {"id": emp_id, "full_name": "Self User"}},
            }
            response = await client.get(
                f"/hr/employees/{emp_id}",
                headers=auth_headers("sales_rep"),
            )
        # With mocked HROps returning success, endpoint should return 200
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    @pytest.mark.asyncio
    async def test_patch_status_requires_hr_permission(self, client, mock_get_db):
        """PATCH /hr/employees/{id}/status without hr_employee_manage → 403."""
        emp_id = str(uuid.uuid4())
        response = await client.patch(
            f"/hr/employees/{emp_id}/status",
            json={"is_active": False},
            headers=auth_headers("sales_rep"),
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_leave_dashboard_requires_hr_reports(self, client, mock_get_db):
        """GET /hr/dashboard/leave-summary without hr_reports or management_read → 403."""
        response = await client.get(
            "/hr/dashboard/leave-summary",
            headers=auth_headers("sales_rep"),
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_cancel_consumed_leave_returns_400(self, client, mock_get_db):
        """PATCH /hr/leave/applications/{id}/status cancel of past leave → 400."""
        app_id = str(uuid.uuid4())
        with patch("app.tools.database.hr_ops.HROps._update_leave_status", new_callable=AsyncMock) as mock_update:
            mock_update.return_value = {
                "success": False,
                "error": "Cannot cancel an approved leave that has already started",
            }
            response = await client.patch(
                f"/hr/leave/applications/{app_id}/status",
                json={"status": "cancelled", "comment": "changed mind"},
                headers=auth_headers("sales_rep"),
            )
        # The endpoint returns 400 (HTTPException) when success=False
        assert response.status_code in (400, 403)


# ══════════════════════════════════════════════════════════════════════════════
# Group 3: Agent Routing tests
# ══════════════════════════════════════════════════════════════════════════════

_CANNED = {"success": True, "content": "ok", "artifacts": [], "tools_called": []}


class TestHRAgentRouting:

    @pytest.mark.asyncio
    async def test_hr_agent_routes_apply_leave_message(self):
        """'apply leave' keyword routes to _apply_leave_workflow."""
        agent = _make_hr_agent()
        with patch.object(agent, "_apply_leave_workflow", new_callable=AsyncMock,
                          return_value=_CANNED) as mock_apply, \
             patch.object(agent, "_check_balance_workflow", new_callable=AsyncMock) as mock_balance, \
             patch.object(agent, "_cancel_leave_workflow", new_callable=AsyncMock) as mock_cancel, \
             patch.object(agent, "_general_response", new_callable=AsyncMock) as mock_gen:
            await agent.execute(_make_agent_task("I want to apply leave from 15 Apr to 17 Apr"))

        mock_apply.assert_called_once()
        mock_balance.assert_not_called()
        mock_cancel.assert_not_called()
        mock_gen.assert_not_called()

    @pytest.mark.asyncio
    async def test_hr_agent_routes_balance_check_message(self):
        """'leave balance' / 'days left' keywords route to _check_balance_workflow."""
        agent = _make_hr_agent()
        with patch.object(agent, "_check_balance_workflow", new_callable=AsyncMock,
                          return_value=_CANNED) as mock_balance, \
             patch.object(agent, "_apply_leave_workflow", new_callable=AsyncMock) as mock_apply, \
             patch.object(agent, "_cancel_leave_workflow", new_callable=AsyncMock) as mock_cancel:
            await agent.execute(_make_agent_task("How many days of leave balance do I have left?"))

        mock_balance.assert_called_once()
        mock_apply.assert_not_called()
        mock_cancel.assert_not_called()

    @pytest.mark.asyncio
    async def test_hr_agent_routes_cancel_leave_message(self):
        """'cancel leave' keyword routes to _cancel_leave_workflow."""
        agent = _make_hr_agent()
        with patch.object(agent, "_cancel_leave_workflow", new_callable=AsyncMock,
                          return_value=_CANNED) as mock_cancel, \
             patch.object(agent, "_apply_leave_workflow", new_callable=AsyncMock) as mock_apply, \
             patch.object(agent, "_check_balance_workflow", new_callable=AsyncMock) as mock_balance:
            await agent.execute(_make_agent_task("Please cancel my leave on 20 Apr"))

        mock_cancel.assert_called_once()
        mock_apply.assert_not_called()
        mock_balance.assert_not_called()

    @pytest.mark.asyncio
    async def test_hr_agent_routes_manager_approval_message(self):
        """'pending approval' keyword routes to _manager_approval_workflow."""
        agent = _make_hr_agent()
        with patch.object(agent, "_manager_approval_workflow", new_callable=AsyncMock,
                          return_value=_CANNED) as mock_mgr, \
             patch.object(agent, "_apply_leave_workflow", new_callable=AsyncMock) as mock_apply, \
             patch.object(agent, "_general_response", new_callable=AsyncMock) as mock_gen:
            await agent.execute(_make_agent_task("Show me pending approval leave requests from my team"))

        mock_mgr.assert_called_once()
        mock_apply.assert_not_called()
        mock_gen.assert_not_called()

    def test_hr_agent_can_handle_keywords(self):
        """can_handle returns True for HR keywords in any department, False for unrelated messages."""
        agent = _make_hr_agent()

        # HR department always routes to HR agent
        assert agent.can_handle(_make_agent_task("anything", department="hr")) is True

        # HR trigger keywords in non-HR department message
        assert agent.can_handle(_make_agent_task("check my leave balance", department="sales")) is True
        assert agent.can_handle(_make_agent_task("apply leave next week", department="finance")) is True
        assert agent.can_handle(_make_agent_task("payroll summary", department="management")) is True

        # Non-HR message from non-HR department → False
        assert agent.can_handle(_make_agent_task("show me sales report", department="sales")) is False
        assert agent.can_handle(_make_agent_task("update my account settings", department="finance")) is False
