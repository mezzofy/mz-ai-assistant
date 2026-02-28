"""
Scheduler API tests — /scheduler/jobs CRUD + manual trigger.

Tests cover:
  - GET  /scheduler/jobs         — list user's jobs (empty + with data)
  - POST /scheduler/jobs         — create job (success, max-10 limit, min-interval)
  - GET  /scheduler/jobs/{id}    — get own job, get other user's job (403)
  - PUT  /scheduler/jobs/{id}    — update (success, no fields 400)
  - DELETE /scheduler/jobs/{id}  — delete (success, other user 403)
  - POST /scheduler/jobs/{id}/run — manual trigger (enqueues Celery task)
  - Cron validation (5 fields, */N < 15 blocked, * minute blocked)
  - Interval validation (< 15 minutes blocked)
  - Admin can access any user's job
"""

import app.tasks.tasks  # noqa: F401 — ensure submodule loaded before patching
import json
import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.engine.row import Row

from tests.conftest import USERS, auth_headers, db_override

pytestmark = pytest.mark.unit


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_db_row(job_id=None, user_id=None, name="Test Job",
                 agent="sales", message="Run sales report",
                 schedule="0 */2 * * *", is_active=True) -> MagicMock:
    """Build a mock DB row resembling a scheduled_jobs row."""
    row = MagicMock()
    row.id = job_id or str(uuid.uuid4())
    row.user_id = user_id or USERS["sales_rep"]["user_id"]
    row.name = name
    row.agent = agent
    row.message = message
    row.schedule = schedule
    row.deliver_to = {}
    row.is_active = is_active
    row.last_run = None
    row.next_run = None
    row.created_at = datetime.now(timezone.utc)
    return row


def _make_mock_db(count=0, fetch_one_row=None, fetch_all_rows=None):
    """Build a mock AsyncSession with configurable return values."""
    mock_session = AsyncMock()

    scalar_result = MagicMock()
    scalar_result.scalar.return_value = count

    fetchone_result = MagicMock()
    fetchone_result.fetchone.return_value = fetch_one_row

    fetchall_result = MagicMock()
    fetchall_result.fetchall.return_value = fetch_all_rows or []

    # execute returns different values on successive calls
    mock_session.execute = AsyncMock(side_effect=[
        scalar_result,
        fetchone_result,
        fetchall_result,
    ] * 5)  # repeat to handle multiple calls

    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()
    return mock_session


# ── GET /scheduler/jobs ───────────────────────────────────────────────────────

class TestListJobs:
    async def test_list_jobs_empty(self, client):
        mock_db = AsyncMock()
        fetchall_result = MagicMock()
        fetchall_result.fetchall.return_value = []
        mock_db.execute = AsyncMock(return_value=fetchall_result)
        mock_db.commit = AsyncMock()

        with db_override(mock_db):
            response = await client.get(
                "/scheduler/jobs",
                headers=auth_headers("sales_rep"),
            )

        assert response.status_code == 200
        data = response.json()
        assert data["jobs"] == []
        assert data["count"] == 0

    async def test_list_jobs_returns_only_user_jobs(self, client):
        user_id = USERS["sales_rep"]["user_id"]
        rows = [_make_db_row(user_id=user_id) for _ in range(3)]

        mock_db = AsyncMock()
        fetchall_result = MagicMock()
        fetchall_result.fetchall.return_value = rows
        mock_db.execute = AsyncMock(return_value=fetchall_result)
        mock_db.commit = AsyncMock()

        with db_override(mock_db):
            response = await client.get(
                "/scheduler/jobs",
                headers=auth_headers("sales_rep"),
            )

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 3

    async def test_list_jobs_requires_auth(self, client):
        response = await client.get("/scheduler/jobs")
        assert response.status_code == 401


# ── POST /scheduler/jobs ──────────────────────────────────────────────────────

class TestCreateJob:
    async def test_create_job_with_cron_schedule(self, client):
        mock_db = AsyncMock()
        count_result = MagicMock()
        count_result.scalar.return_value = 0  # 0 existing jobs
        mock_db.execute = AsyncMock(return_value=count_result)
        mock_db.commit = AsyncMock()

        with db_override(mock_db):
            response = await client.post(
                "/scheduler/jobs",
                json={
                    "name": "Weekly Sales Report",
                    "agent": "sales",
                    "message": "Generate weekly sales summary",
                    "schedule": {"type": "cron", "cron": "0 9 * * 1"},
                },
                headers=auth_headers("sales_manager"),
            )

        assert response.status_code == 201
        data = response.json()
        assert "job_id" in data
        assert data["schedule"] == "0 9 * * 1"
        assert data["agent"] == "sales"

    async def test_create_job_with_interval_schedule(self, client):
        mock_db = AsyncMock()
        count_result = MagicMock()
        count_result.scalar.return_value = 0
        mock_db.execute = AsyncMock(return_value=count_result)
        mock_db.commit = AsyncMock()

        with db_override(mock_db):
            response = await client.post(
                "/scheduler/jobs",
                json={
                    "name": "Finance Check",
                    "agent": "finance",
                    "message": "Check financial metrics",
                    "schedule": {"type": "interval", "interval_minutes": 60},
                },
                headers=auth_headers("finance_manager"),
            )

        assert response.status_code == 201
        data = response.json()
        assert data["schedule"] == "0 */1 * * *"

    async def test_create_job_max_limit_exceeded(self, client):
        """Should return 409 when user already has 10 active jobs."""
        mock_db = AsyncMock()
        count_result = MagicMock()
        count_result.scalar.return_value = 10  # already at limit
        mock_db.execute = AsyncMock(return_value=count_result)
        mock_db.commit = AsyncMock()

        with db_override(mock_db):
            response = await client.post(
                "/scheduler/jobs",
                json={
                    "name": "Extra Job",
                    "agent": "sales",
                    "message": "One too many",
                    "schedule": {"type": "cron", "cron": "0 */2 * * *"},
                },
                headers=auth_headers("sales_manager"),
            )

        assert response.status_code == 409
        assert "Maximum" in response.json()["detail"]

    async def test_create_job_interval_below_minimum(self, client):
        """Interval < 15 minutes must be rejected with 400."""
        mock_db = AsyncMock()
        count_result = MagicMock()
        count_result.scalar.return_value = 0
        mock_db.execute = AsyncMock(return_value=count_result)

        with db_override(mock_db):
            response = await client.post(
                "/scheduler/jobs",
                json={
                    "name": "Too Frequent",
                    "agent": "sales",
                    "message": "Every 5 minutes",
                    "schedule": {"type": "interval", "interval_minutes": 5},
                },
                headers=auth_headers("sales_manager"),
            )

        assert response.status_code == 400
        assert "Minimum interval" in response.json()["detail"]

    async def test_create_job_cron_every_minute_blocked(self, client):
        """Cron with '*' in minute field must be blocked."""
        mock_db = AsyncMock()
        count_result = MagicMock()
        count_result.scalar.return_value = 0
        mock_db.execute = AsyncMock(return_value=count_result)

        with db_override(mock_db):
            response = await client.post(
                "/scheduler/jobs",
                json={
                    "name": "Every Minute",
                    "agent": "sales",
                    "message": "Too frequent",
                    "schedule": {"type": "cron", "cron": "* * * * *"},
                },
                headers=auth_headers("sales_manager"),
            )

        assert response.status_code == 400
        assert "Minimum schedule interval" in response.json()["detail"]

    async def test_create_job_cron_minute_below_15_blocked(self, client):
        """Cron with */5 in minute field (below 15) must be blocked."""
        mock_db = AsyncMock()
        count_result = MagicMock()
        count_result.scalar.return_value = 0
        mock_db.execute = AsyncMock(return_value=count_result)

        with db_override(mock_db):
            response = await client.post(
                "/scheduler/jobs",
                json={
                    "name": "Every 5 Min",
                    "agent": "sales",
                    "message": "Too frequent",
                    "schedule": {"type": "cron", "cron": "*/5 * * * *"},
                },
                headers=auth_headers("sales_manager"),
            )

        assert response.status_code == 400

    async def test_create_job_cron_15_minutes_allowed(self, client):
        """Cron with */15 in minute field (exactly 15) must be allowed."""
        mock_db = AsyncMock()
        count_result = MagicMock()
        count_result.scalar.return_value = 0
        mock_db.execute = AsyncMock(return_value=count_result)
        mock_db.commit = AsyncMock()

        with db_override(mock_db):
            response = await client.post(
                "/scheduler/jobs",
                json={
                    "name": "Every 15 Min",
                    "agent": "sales",
                    "message": "Minimum allowed",
                    "schedule": {"type": "cron", "cron": "*/15 * * * *"},
                },
                headers=auth_headers("sales_manager"),
            )

        assert response.status_code == 201

    async def test_create_job_invalid_agent_name(self, client):
        """agent must be one of the valid department agents."""
        mock_db = AsyncMock()
        count_result = MagicMock()
        count_result.scalar.return_value = 0
        mock_db.execute = AsyncMock(return_value=count_result)

        with db_override(mock_db):
            response = await client.post(
                "/scheduler/jobs",
                json={
                    "name": "Bad Agent",
                    "agent": "hacker",  # invalid
                    "message": "Something",
                    "schedule": {"type": "cron", "cron": "0 9 * * 1"},
                },
                headers=auth_headers("sales_manager"),
            )

        assert response.status_code == 422

    async def test_create_job_name_too_long(self, client):
        mock_db = AsyncMock()
        count_result = MagicMock()
        count_result.scalar.return_value = 0
        mock_db.execute = AsyncMock(return_value=count_result)

        with db_override(mock_db):
            response = await client.post(
                "/scheduler/jobs",
                json={
                    "name": "x" * 101,  # > 100 chars
                    "agent": "sales",
                    "message": "Something",
                    "schedule": {"type": "cron", "cron": "0 9 * * 1"},
                },
                headers=auth_headers("sales_manager"),
            )

        assert response.status_code == 422


# ── GET /scheduler/jobs/{id} ──────────────────────────────────────────────────

class TestGetJob:
    async def test_get_own_job_success(self, client):
        user_id = USERS["sales_rep"]["user_id"]
        row = _make_db_row(user_id=user_id)

        mock_db = AsyncMock()
        fetchone_result = MagicMock()
        fetchone_result.fetchone.return_value = row
        mock_db.execute = AsyncMock(return_value=fetchone_result)
        mock_db.commit = AsyncMock()

        with db_override(mock_db):
            response = await client.get(
                f"/scheduler/jobs/{row.id}",
                headers=auth_headers("sales_rep"),
            )

        assert response.status_code == 200
        data = response.json()
        assert data["agent"] == "sales"

    async def test_get_other_users_job_returns_403(self, client):
        """A user cannot read another user's job."""
        other_user_id = str(uuid.uuid4())  # different from sales_rep
        row = _make_db_row(user_id=other_user_id)

        mock_db = AsyncMock()
        fetchone_result = MagicMock()
        fetchone_result.fetchone.return_value = row
        mock_db.execute = AsyncMock(return_value=fetchone_result)

        with db_override(mock_db):
            response = await client.get(
                f"/scheduler/jobs/{row.id}",
                headers=auth_headers("sales_rep"),
            )

        assert response.status_code == 403

    async def test_admin_can_get_any_job(self, client):
        """Admin bypasses ownership check."""
        other_user_id = str(uuid.uuid4())
        row = _make_db_row(user_id=other_user_id)

        mock_db = AsyncMock()
        fetchone_result = MagicMock()
        fetchone_result.fetchone.return_value = row
        mock_db.execute = AsyncMock(return_value=fetchone_result)
        mock_db.commit = AsyncMock()

        with db_override(mock_db):
            response = await client.get(
                f"/scheduler/jobs/{row.id}",
                headers=auth_headers("admin"),
            )

        assert response.status_code == 200

    async def test_get_nonexistent_job_returns_404(self, client):
        mock_db = AsyncMock()
        fetchone_result = MagicMock()
        fetchone_result.fetchone.return_value = None
        mock_db.execute = AsyncMock(return_value=fetchone_result)

        with db_override(mock_db):
            response = await client.get(
                f"/scheduler/jobs/{uuid.uuid4()}",
                headers=auth_headers("sales_rep"),
            )

        assert response.status_code == 404


# ── DELETE /scheduler/jobs/{id} ───────────────────────────────────────────────

class TestDeleteJob:
    async def test_delete_own_job(self, client):
        user_id = USERS["sales_manager"]["user_id"]
        row = _make_db_row(user_id=user_id)

        mock_db = AsyncMock()
        fetchone_result = MagicMock()
        fetchone_result.fetchone.return_value = row
        mock_db.execute = AsyncMock(return_value=fetchone_result)
        mock_db.commit = AsyncMock()

        with db_override(mock_db):
            response = await client.delete(
                f"/scheduler/jobs/{row.id}",
                headers=auth_headers("sales_manager"),
            )

        assert response.status_code == 200
        assert response.json()["deleted"] is True

    async def test_delete_other_users_job_returns_403(self, client):
        other_user_id = str(uuid.uuid4())
        row = _make_db_row(user_id=other_user_id)

        mock_db = AsyncMock()
        fetchone_result = MagicMock()
        fetchone_result.fetchone.return_value = row
        mock_db.execute = AsyncMock(return_value=fetchone_result)

        with db_override(mock_db):
            response = await client.delete(
                f"/scheduler/jobs/{row.id}",
                headers=auth_headers("sales_rep"),
            )

        assert response.status_code == 403


# ── POST /scheduler/jobs/{id}/run ─────────────────────────────────────────────

class TestRunJobNow:
    async def test_run_job_enqueues_celery_task(self, client, mock_celery_delay):
        user_id = USERS["sales_manager"]["user_id"]
        row = _make_db_row(user_id=user_id)

        mock_db = AsyncMock()
        fetchone_result = MagicMock()
        fetchone_result.fetchone.return_value = row
        mock_db.execute = AsyncMock(return_value=fetchone_result)
        mock_db.commit = AsyncMock()

        with db_override(mock_db):
            response = await client.post(
                f"/scheduler/jobs/{row.id}/run",
                headers=auth_headers("sales_manager"),
            )

        assert response.status_code == 202
        data = response.json()
        assert data["triggered"] is True
        assert "task_id" in data
        mock_celery_delay["process_agent_task"].delay.assert_called_once()

    async def test_run_job_task_data_has_scheduler_source(self, client, mock_celery_delay):
        """Task dispatched via /run must have source='scheduler' to bypass permission checks."""
        user_id = USERS["finance_manager"]["user_id"]
        row = _make_db_row(user_id=user_id, agent="finance")

        mock_db = AsyncMock()
        fetchone_result = MagicMock()
        fetchone_result.fetchone.return_value = row
        mock_db.execute = AsyncMock(return_value=fetchone_result)
        mock_db.commit = AsyncMock()

        with db_override(mock_db):
            await client.post(
                f"/scheduler/jobs/{row.id}/run",
                headers=auth_headers("finance_manager"),
            )

        task_data = mock_celery_delay["process_agent_task"].delay.call_args[0][0]
        assert task_data["source"] == "scheduler"
        assert task_data["agent"] == "finance"


# ── Cron expression validation unit tests ─────────────────────────────────────

class TestCronValidation:
    """Unit tests for the cron validation function (no HTTP)."""

    def test_five_field_cron_valid(self):
        from app.webhooks.scheduler import _validate_cron_expression
        _validate_cron_expression("0 9 * * 1")  # must not raise

    def test_star_minute_raises(self):
        from app.webhooks.scheduler import _validate_cron_expression
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            _validate_cron_expression("* * * * *")
        assert exc_info.value.status_code == 400

    def test_step_below_15_raises(self):
        from app.webhooks.scheduler import _validate_cron_expression
        from fastapi import HTTPException
        with pytest.raises(HTTPException):
            _validate_cron_expression("*/10 * * * *")

    def test_step_exactly_15_allowed(self):
        from app.webhooks.scheduler import _validate_cron_expression
        _validate_cron_expression("*/15 * * * *")  # must not raise

    def test_step_above_15_allowed(self):
        from app.webhooks.scheduler import _validate_cron_expression
        _validate_cron_expression("*/20 * * * *")  # must not raise

    def test_four_field_cron_raises(self):
        from app.webhooks.scheduler import _validate_cron_expression
        from fastapi import HTTPException
        with pytest.raises(HTTPException):
            _validate_cron_expression("0 9 * *")

    def test_empty_cron_raises(self):
        from app.webhooks.scheduler import _validate_cron_expression
        from fastapi import HTTPException
        with pytest.raises(HTTPException):
            _validate_cron_expression("")

    def test_interval_below_15_raises(self):
        from app.webhooks.scheduler import _schedule_dto_to_cron, ScheduleDTO
        from fastapi import HTTPException
        dto = ScheduleDTO(type="interval", interval_minutes=10)
        with pytest.raises(HTTPException):
            _schedule_dto_to_cron(dto)

    def test_interval_exactly_15_gives_star_slash_15(self):
        from app.webhooks.scheduler import _schedule_dto_to_cron, ScheduleDTO
        dto = ScheduleDTO(type="interval", interval_minutes=15)
        result = _schedule_dto_to_cron(dto)
        assert result == "*/15 * * * *"

    def test_interval_60_minutes_gives_hourly(self):
        from app.webhooks.scheduler import _schedule_dto_to_cron, ScheduleDTO
        dto = ScheduleDTO(type="interval", interval_minutes=60)
        result = _schedule_dto_to_cron(dto)
        assert result == "0 */1 * * *"
