"""
Admin Portal API tests — /api/admin-portal/*

Tests:
  1. test_non_admin_email_rejected — non-admin role → 403
  2. test_unauthenticated_request_401 — missing token → 401
  3. test_wrong_role_403 — sales_rep role → 403
  4. test_create_user_sets_invite_token — POST /users sets invite_token
  5. test_delete_user_soft_deletes — DELETE /users sets deleted_at, not hard delete
  6. test_system_vitals_returns_required_fields — GET /dashboard/system-vitals
  7. test_manual_trigger_returns_task_id — POST /scheduler/jobs/{id}/trigger
  8. test_llm_usage_today_period — GET /dashboard/llm-usage?period=today
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.conftest import USERS, auth_headers, db_override

pytestmark = pytest.mark.unit


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_user_row(**kwargs):
    row = MagicMock()
    row.id = kwargs.get("id", str(uuid.uuid4()))
    row.email = kwargs.get("email", "user@test.com")
    row.name = kwargs.get("name", "Test User")
    row.department = kwargs.get("department", "sales")
    row.role = kwargs.get("role", "sales_rep")
    row.is_active = kwargs.get("is_active", True)
    row.last_login = kwargs.get("last_login", None)
    row.created_at = kwargs.get("created_at", datetime.now(timezone.utc))
    row.deleted_at = kwargs.get("deleted_at", None)
    row.session_count = kwargs.get("session_count", 0)
    return row


def _make_db(rows=None, scalar=None):
    """Build a mock DB session."""
    mock_db = AsyncMock()
    result = MagicMock()
    result.fetchall.return_value = rows or []
    result.fetchone.return_value = (rows[0] if rows else None)
    result.scalar.return_value = scalar
    mock_db.execute = AsyncMock(return_value=result)
    mock_db.commit = AsyncMock()
    return mock_db


# ── 1. Non-admin email / wrong role returns 403 ───────────────────────────────

class TestRoleEnforcement:
    async def test_non_admin_email_rejected(self, client):
        """A user with 'executive' role cannot access admin portal."""
        response = await client.get(
            "/api/admin-portal/auth/me",
            headers=auth_headers("executive"),
        )
        assert response.status_code == 403

    async def test_unauthenticated_request_401(self, client):
        """Missing Authorization header returns 401."""
        response = await client.get("/api/admin-portal/auth/me")
        assert response.status_code == 401

    async def test_wrong_role_403(self, client):
        """sales_rep role returns 403 on portal endpoint."""
        response = await client.get(
            "/api/admin-portal/users",
            headers=auth_headers("sales_rep"),
        )
        assert response.status_code == 403


# ── 2. Create user sets invite_token ──────────────────────────────────────────

class TestCreateUser:
    async def test_create_user_sets_invite_token(self, client):
        """POST /api/admin-portal/users creates user with invite_token."""
        mock_db = AsyncMock()
        # First execute (check existing email) returns no row
        check_result = MagicMock()
        check_result.fetchone.return_value = None
        # Subsequent executes (INSERT + audit_log) succeed
        mock_db.execute = AsyncMock(return_value=check_result)
        mock_db.commit = AsyncMock()

        with db_override(mock_db):
            with patch("app.tools.communication.outlook_ops.OutlookOps._send_email", new_callable=AsyncMock):
                response = await client.post(
                    "/api/admin-portal/users",
                    headers=auth_headers("admin"),
                    json={
                        "email": "newuser@mezzofy.com",
                        "name": "New User",
                        "department": "sales",
                        "role": "sales_rep",
                    },
                )
        assert response.status_code == 201
        data = response.json()
        assert "invite_token" in data
        assert len(data["invite_token"]) == 32  # UUID4 without dashes


# ── 3. Delete user soft-deletes ───────────────────────────────────────────────

class TestDeleteUser:
    async def test_delete_user_soft_deletes(self, client):
        """DELETE /api/admin-portal/users/{id} sets deleted_at (soft delete)."""
        target_id = str(uuid.uuid4())
        user_row = MagicMock()
        user_row.id = target_id
        user_row.email = "target@mezzofy.com"

        mock_db = AsyncMock()
        select_result = MagicMock()
        select_result.fetchone.return_value = user_row
        mock_db.execute = AsyncMock(return_value=select_result)
        mock_db.commit = AsyncMock()

        with db_override(mock_db):
            with patch("app.core.auth.blacklist_all_user_tokens", new_callable=AsyncMock):
                response = await client.delete(
                    f"/api/admin-portal/users/{target_id}",
                    headers=auth_headers("admin"),
                )

        assert response.status_code == 200
        data = response.json()
        assert data["deleted"] is True
        assert data["user_id"] == target_id

        # Verify UPDATE (soft delete) was called, not DELETE
        calls = mock_db.execute.call_args_list
        update_calls = [c for c in calls if "UPDATE" in str(c).upper() and "deleted_at" in str(c).lower()]
        assert len(update_calls) >= 1, "Expected soft-delete UPDATE call"


# ── 4. System vitals returns required fields ──────────────────────────────────

class TestSystemVitals:
    async def test_system_vitals_returns_required_fields(self, client):
        """GET /api/admin-portal/dashboard/system-vitals returns all required sections."""
        mock_db = AsyncMock()
        ping_result = MagicMock()
        ping_result.fetchone.return_value = (1,)
        mock_db.execute = AsyncMock(return_value=ping_result)

        with db_override(mock_db):
            with patch("psutil.cpu_percent", return_value=25.0):
                with patch("psutil.virtual_memory") as mock_mem:
                    mock_mem.return_value = MagicMock(
                        total=8e9, used=4e9, available=4e9, percent=50.0
                    )
                    with patch("psutil.disk_usage") as mock_disk:
                        mock_disk.return_value = MagicMock(
                            total=100e9, used=40e9, free=60e9
                        )
                        response = await client.get(
                            "/api/admin-portal/dashboard/system-vitals",
                            headers=auth_headers("admin"),
                        )

        assert response.status_code == 200
        data = response.json()
        assert "cpu" in data
        assert "memory" in data
        assert "disk" in data
        assert "services" in data
        assert "percent" in data["cpu"]
        assert "percent" in data["memory"]
        assert "postgresql" in data["services"]
        assert "redis" in data["services"]


# ── 5. Manual trigger returns task_id ─────────────────────────────────────────

class TestManualTrigger:
    async def test_manual_trigger_returns_task_id(self, client):
        """POST /api/admin-portal/scheduler/jobs/{id}/trigger returns task_id."""
        job_id = str(uuid.uuid4())

        job_row = MagicMock()
        job_row.id = job_id
        job_row.name = "Test Job"
        job_row.agent = "finance"
        job_row.message = "Generate weekly report"

        mock_db = AsyncMock()
        select_result = MagicMock()
        select_result.fetchone.return_value = job_row
        mock_db.execute = AsyncMock(return_value=select_result)
        mock_db.commit = AsyncMock()

        fake_task = MagicMock()
        fake_task.id = str(uuid.uuid4())

        with db_override(mock_db):
            with patch("app.tasks.tasks.process_agent_task") as mock_task:
                mock_task.delay.return_value = fake_task
                response = await client.post(
                    f"/api/admin-portal/scheduler/jobs/{job_id}/trigger",
                    headers=auth_headers("admin"),
                )

        assert response.status_code == 200
        data = response.json()
        assert "task_id" in data
        assert "message" in data


# ── 6. LLM usage today period ─────────────────────────────────────────────────

class TestLlmUsage:
    async def test_llm_usage_today_period(self, client):
        """GET /api/admin-portal/dashboard/llm-usage?period=today returns model list."""
        mock_row = MagicMock()
        mock_row.model = "claude-sonnet-4-5"
        mock_row.total_tokens = 5000
        mock_row.input_tokens = 3000
        mock_row.output_tokens = 2000
        mock_row.total_cost = 0.05
        mock_row.request_count = 10
        mock_row.today_cost = 0.05

        mock_db = AsyncMock()
        result = MagicMock()
        result.fetchall.return_value = [mock_row]
        mock_db.execute = AsyncMock(return_value=result)

        with db_override(mock_db):
            response = await client.get(
                "/api/admin-portal/dashboard/llm-usage?period=today",
                headers=auth_headers("admin"),
            )

        assert response.status_code == 200
        data = response.json()
        assert "period" in data
        assert data["period"] == "today"
        assert "models" in data
        assert isinstance(data["models"], list)
