"""
Task Management Tests — mobile app task lifecycle API contract.

Tests the server-side API endpoints that the mobile ChatScreen's orange task
banner depends on:
  - POST /chat/send       → HTTP 202 for long-running keywords (research, generate pdf)
  - GET  /tasks/          → list all user tasks
  - GET  /tasks/active    → polling endpoint (queued + running only)
  - GET  /tasks/{id}      → task detail with result/plan fields
  - POST /tasks/{id}/cancel
  - POST /tasks/{id}/retry

26 tests across 5 classes:
  TestTaskCreation          (5)  — chat send → 202 + DB row + Celery dispatch
  TestTaskListAPI           (6)  — list / active polling / field completeness
  TestTaskStatusTransitions (6)  — all 5 status states + detail endpoint
  TestConcurrentTasks       (4)  — two tasks active simultaneously
  TestTaskEdgeCases         (5)  — auth, ownership, cancel, retry, null session_id
"""

import json
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.conftest import (
    USERS,
    auth_headers,
    db_override,
)

pytestmark = pytest.mark.unit


# ── Helpers ───────────────────────────────────────────────────────────────────

_NOW = datetime.now(timezone.utc)


def _make_task_row(**kwargs) -> SimpleNamespace:
    """
    Build a mock agent_tasks DB row as a SimpleNamespace.

    Attribute access mirrors what _row_to_dict() expects from a SQLAlchemy Row.
    All datetime fields are real datetime objects so .isoformat() works.
    """
    defaults = {
        "id": str(uuid.uuid4()),
        "task_ref": f"TASK-{str(uuid.uuid4())[:8].upper()}",
        "session_id": str(uuid.uuid4()),
        "department": "finance",
        "content": "Research the top 5 competitors",
        "status": "queued",
        "progress": 0,
        "current_step": None,
        "error": None,
        "notify_on_done": True,
        "queue_name": "background",
        "started_at": None,
        "completed_at": None,
        "created_at": _NOW,
        # detail endpoint only (GET /tasks/{id}):
        "plan": [],
        "result": None,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _mock_db_for_rows(*rows):
    """
    Build a mock AsyncSession where execute() returns a result whose:
      fetchall() → list(rows)
      fetchone() → rows[0]  (or None if empty)
    """
    mock_result = MagicMock()
    mock_result.fetchall.return_value = list(rows)
    mock_result.fetchone.return_value = rows[0] if rows else None

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.commit = AsyncMock()
    mock_db.rollback = AsyncMock()
    return mock_db


# ── Class 1: TestTaskCreation ─────────────────────────────────────────────────

class TestTaskCreation:
    """
    POST /chat/send with long-running keywords returns HTTP 202.
    Verifies: response shape, agent_tasks DB insert, Celery dispatch.
    """

    async def test_research_task_returns_202(
        self,
        client,
        mock_config,
        mock_db_session,
        mock_session_manager,
        mock_audit_log,
    ):
        """'research' keyword → async path → HTTP 202 with task_id, session_id, status=queued."""
        with patch("app.tasks.tasks.process_chat_task") as mock_task:
            mock_task.delay.return_value = MagicMock(id=str(uuid.uuid4()))

            response = await client.post(
                "/chat/send",
                json={"message": "research the top 5 competitors in Southeast Asia"},
                headers=auth_headers("finance_manager"),
            )

        assert response.status_code == 202
        data = response.json()
        assert "task_id" in data
        assert "session_id" in data
        assert data["status"] == "queued"

    async def test_create_text_file_task_returns_202(
        self,
        client,
        mock_config,
        mock_db_session,
        mock_session_manager,
        mock_audit_log,
    ):
        """'generate pdf' keyword → async path → HTTP 202 with task_id."""
        with patch("app.tasks.tasks.process_chat_task") as mock_task:
            mock_task.delay.return_value = MagicMock(id=str(uuid.uuid4()))

            response = await client.post(
                "/chat/send",
                json={"message": "generate pdf of Q1 sales report"},
                headers=auth_headers("finance_manager"),
            )

        assert response.status_code == 202
        data = response.json()
        assert "task_id" in data
        assert "session_id" in data
        assert data["status"] == "queued"

    async def test_non_task_message_returns_200(
        self,
        client,
        mock_config,
        mock_route_request,
        mock_process_result,
        mock_session_manager,
        mock_db_session,
        mock_audit_log,
    ):
        """Plain message with no long-running keyword → synchronous 200 response."""
        response = await client.post(
            "/chat/send",
            json={"message": "hello, how are you?"},
            headers=auth_headers("finance_manager"),
        )

        assert response.status_code == 200
        data = response.json()
        # Synchronous response does not have status="queued"
        assert data.get("status") != "queued"

    async def test_task_queued_in_db(
        self,
        client,
        mock_config,
        mock_db_session,
        mock_session_manager,
        mock_audit_log,
    ):
        """After research keyword, DB execute is called with INSERT INTO agent_tasks."""
        with patch("app.tasks.tasks.process_chat_task") as mock_task:
            mock_task.delay.return_value = MagicMock(id=str(uuid.uuid4()))

            await client.post(
                "/chat/send",
                json={"message": "research the quarterly sales trends"},
                headers=auth_headers("finance_manager"),
            )

        # mock_db_session is the AsyncSession; inspect all execute() calls
        execute_calls = mock_db_session.execute.call_args_list
        assert len(execute_calls) >= 1, "Expected at least one DB execute call"

        # TextClause.__str__ returns the raw SQL; check args[0] of each call
        found_insert = any(
            len(call.args) > 0 and "agent_tasks" in str(call.args[0])
            for call in execute_calls
        )
        assert found_insert, "Expected INSERT INTO agent_tasks in DB execute calls"

    async def test_celery_dispatched_on_task(
        self,
        client,
        mock_config,
        mock_db_session,
        mock_session_manager,
        mock_audit_log,
    ):
        """After research keyword, process_chat_task.delay() is called once with agent_task_id."""
        with patch("app.tasks.tasks.process_chat_task") as mock_task:
            mock_task.delay.return_value = MagicMock(id=str(uuid.uuid4()))

            await client.post(
                "/chat/send",
                json={"message": "research top AI companies in Singapore"},
                headers=auth_headers("finance_manager"),
            )

            mock_task.delay.assert_called_once()
            task_payload = mock_task.delay.call_args[0][0]
            assert "agent_task_id" in task_payload
            # agent_task_id must be a valid UUID
            uuid.UUID(task_payload["agent_task_id"])


# ── Class 2: TestTaskListAPI ──────────────────────────────────────────────────

class TestTaskListAPI:
    """
    GET /tasks/ and GET /tasks/active — the polling endpoints the mobile
    orange banner calls every 4 seconds.
    """

    async def test_list_tasks_returns_user_tasks(self, client):
        """GET /tasks/ returns tasks array with id, status, session_id."""
        task_id = str(uuid.uuid4())
        session_id = str(uuid.uuid4())
        task = _make_task_row(id=task_id, session_id=session_id, status="queued")

        mock_db = _mock_db_for_rows(task)
        with db_override(mock_db):
            response = await client.get("/tasks/", headers=auth_headers("finance_manager"))

        assert response.status_code == 200
        data = response.json()
        assert "tasks" in data
        assert "total" in data
        assert data["total"] == 1
        assert data["tasks"][0]["id"] == task_id
        assert data["tasks"][0]["status"] == "queued"
        assert data["tasks"][0]["session_id"] == session_id

    async def test_list_tasks_excludes_other_user(self, client):
        """
        The SQL query includes WHERE user_id = :uid — only User A's tasks
        appear when User A authenticates.  Verifies uid param is User A's id.
        """
        task = _make_task_row(status="queued", content="User A's task")
        mock_db = _mock_db_for_rows(task)

        with db_override(mock_db):
            response = await client.get("/tasks/", headers=auth_headers("finance_manager"))

        assert response.status_code == 200

        # Verify the user_id passed to the SQL matches the authenticated user
        execute_call = mock_db.execute.call_args
        # args: (text_clause, params_dict)
        params = execute_call.args[1] if len(execute_call.args) > 1 else {}
        assert params.get("uid") == USERS["finance_manager"]["user_id"]

    async def test_active_tasks_queued_only(self, client):
        """GET /tasks/active returns queued task (SQL filters IN ('queued','running'))."""
        queued = _make_task_row(status="queued")
        # DB returns only queued (simulates SQL-level filter)
        mock_db = _mock_db_for_rows(queued)

        with db_override(mock_db):
            response = await client.get("/tasks/active", headers=auth_headers("finance_manager"))

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["tasks"][0]["status"] == "queued"

    async def test_active_tasks_running_only(self, client):
        """GET /tasks/active returns running task with progress."""
        running = _make_task_row(
            status="running",
            progress=55,
            started_at=_NOW,
        )
        mock_db = _mock_db_for_rows(running)

        with db_override(mock_db):
            response = await client.get("/tasks/active", headers=auth_headers("finance_manager"))

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["tasks"][0]["status"] == "running"
        assert data["tasks"][0]["progress"] == 55

    async def test_active_tasks_empty_when_all_done(self, client):
        """GET /tasks/active → empty list when no queued/running tasks exist."""
        mock_db = _mock_db_for_rows()  # no active tasks

        with db_override(mock_db):
            response = await client.get("/tasks/active", headers=auth_headers("finance_manager"))

        assert response.status_code == 200
        data = response.json()
        assert data["tasks"] == []
        assert data["total"] == 0

    async def test_task_response_fields_complete(self, client):
        """GET /tasks/ response includes all fields required by the mobile banner."""
        task = _make_task_row(
            task_ref="TASK-ABCD1234",
            status="running",
            progress=30,
            current_step='{"description": "Searching web..."}',
            started_at=_NOW,
            notify_on_done=True,
        )
        mock_db = _mock_db_for_rows(task)

        with db_override(mock_db):
            response = await client.get("/tasks/", headers=auth_headers("finance_manager"))

        assert response.status_code == 200
        t = response.json()["tasks"][0]
        required_fields = [
            "id", "task_ref", "session_id", "content", "status",
            "progress", "current_step", "started_at", "completed_at", "created_at",
        ]
        for field in required_fields:
            assert field in t, f"Missing required field in task response: {field!r}"


# ── Class 3: TestTaskStatusTransitions ────────────────────────────────────────

class TestTaskStatusTransitions:
    """
    All 5 status values as returned by the API.
    Simulates what the mobile banner receives during each polling interval.
    """

    async def test_status_queued(self, client):
        """Queued state: progress=0, started_at=null in response."""
        task = _make_task_row(status="queued", progress=0, started_at=None)
        mock_db = _mock_db_for_rows(task)

        with db_override(mock_db):
            response = await client.get("/tasks/", headers=auth_headers("finance_manager"))

        assert response.status_code == 200
        t = response.json()["tasks"][0]
        assert t["status"] == "queued"
        assert t["progress"] == 0
        assert t["started_at"] is None

    async def test_status_running_with_progress(self, client):
        """Running state: progress=45, current_step contains parseable JSON."""
        task = _make_task_row(
            status="running",
            progress=45,
            current_step='{"description": "Searching web..."}',
            started_at=_NOW,
        )
        mock_db = _mock_db_for_rows(task)

        with db_override(mock_db):
            response = await client.get("/tasks/", headers=auth_headers("finance_manager"))

        assert response.status_code == 200
        t = response.json()["tasks"][0]
        assert t["status"] == "running"
        assert t["progress"] == 45
        assert t["current_step"] is not None
        step = json.loads(t["current_step"])
        assert "description" in step

    async def test_status_completed(self, client):
        """Completed state: progress=100, completed_at not null."""
        task = _make_task_row(
            status="completed",
            progress=100,
            completed_at=_NOW,
        )
        mock_db = _mock_db_for_rows(task)

        with db_override(mock_db):
            response = await client.get("/tasks/", headers=auth_headers("finance_manager"))

        assert response.status_code == 200
        t = response.json()["tasks"][0]
        assert t["status"] == "completed"
        assert t["progress"] == 100
        assert t["completed_at"] is not None

    async def test_status_failed_with_error(self, client):
        """Failed state: error field is populated."""
        task = _make_task_row(
            status="failed",
            error="Tool call failed: timeout after 120s",
            completed_at=_NOW,
        )
        mock_db = _mock_db_for_rows(task)

        with db_override(mock_db):
            response = await client.get("/tasks/", headers=auth_headers("finance_manager"))

        assert response.status_code == 200
        t = response.json()["tasks"][0]
        assert t["status"] == "failed"
        assert t["error"] is not None
        assert len(t["error"]) > 0

    async def test_status_cancelled(self, client):
        """Cancelled state: status field is 'cancelled'."""
        task = _make_task_row(status="cancelled", completed_at=_NOW)
        mock_db = _mock_db_for_rows(task)

        with db_override(mock_db):
            response = await client.get("/tasks/", headers=auth_headers("finance_manager"))

        assert response.status_code == 200
        t = response.json()["tasks"][0]
        assert t["status"] == "cancelled"

    async def test_task_detail_includes_result(self, client):
        """GET /tasks/{id} includes result and plan fields for a completed task."""
        task_id = str(uuid.uuid4())
        task = _make_task_row(
            id=task_id,
            status="completed",
            progress=100,
            result={"content": "Research complete. Found 5 competitors.", "summary": "done"},
            plan=[{"step": 1, "action": "Search web"}],
            completed_at=_NOW,
        )

        # Detail endpoint uses fetchone(), not fetchall()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = task
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()

        with db_override(mock_db):
            response = await client.get(
                f"/tasks/{task_id}", headers=auth_headers("finance_manager")
            )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == task_id
        assert data["status"] == "completed"
        assert "result" in data
        assert data["result"] is not None
        assert "plan" in data


# ── Class 4: TestConcurrentTasks ──────────────────────────────────────────────

class TestConcurrentTasks:
    """
    Two tasks active simultaneously — simulates a user sending two long-running
    messages in quick succession from different chat sessions.
    """

    async def test_two_concurrent_tasks_both_listed(self, client):
        """GET /tasks/active returns both running tasks for the same user."""
        session_a = str(uuid.uuid4())
        session_b = str(uuid.uuid4())
        task_a = _make_task_row(session_id=session_a, status="running", content="Research task A")
        task_b = _make_task_row(session_id=session_b, status="running", content="Generate PDF task B")

        mock_db = _mock_db_for_rows(task_a, task_b)

        with db_override(mock_db):
            response = await client.get("/tasks/active", headers=auth_headers("finance_manager"))

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        session_ids = {t["session_id"] for t in data["tasks"]}
        assert session_a in session_ids
        assert session_b in session_ids

    async def test_active_task_filtered_by_session(self, client):
        """
        GET /tasks/active returns all active tasks for the user (server does not
        filter by session_id — mobile client filters client-side by sessionId match).
        """
        session_a = str(uuid.uuid4())
        session_b = str(uuid.uuid4())
        task_a = _make_task_row(session_id=session_a, status="running")
        task_b = _make_task_row(session_id=session_b, status="running")

        mock_db = _mock_db_for_rows(task_a, task_b)

        with db_override(mock_db):
            response = await client.get("/tasks/active", headers=auth_headers("finance_manager"))

        data = response.json()
        # Server returns both; mobile filters client-side by matching sessionId
        assert data["total"] == 2

    async def test_second_task_creation_while_first_running(
        self,
        client,
        mock_config,
        mock_db_session,
        mock_session_manager,
        mock_audit_log,
    ):
        """Two successive POST /chat/send calls both return 202 with distinct task_ids."""
        task_ids = []

        with patch("app.tasks.tasks.process_chat_task") as mock_task:
            mock_task.delay.return_value = MagicMock(id=str(uuid.uuid4()))

            for msg in [
                "research top AI companies",
                "generate pdf of market analysis",
            ]:
                response = await client.post(
                    "/chat/send",
                    json={"message": msg},
                    headers=auth_headers("finance_manager"),
                )
                assert response.status_code == 202
                task_ids.append(response.json()["task_id"])

        # Both task_ids must be distinct UUIDs
        assert task_ids[0] != task_ids[1]
        assert len(task_ids[0]) == 36  # UUID string length
        assert len(task_ids[1]) == 36

    async def test_concurrent_tasks_independent_status(self, client):
        """
        Querying Task A (completed) and Task B (queued) independently shows
        their statuses are unaffected by each other — DB isolation.
        """
        task_a_id = str(uuid.uuid4())
        task_b_id = str(uuid.uuid4())
        task_a = _make_task_row(id=task_a_id, status="completed", progress=100, completed_at=_NOW)
        task_b = _make_task_row(id=task_b_id, status="queued", progress=0)

        # Two sequential GET /tasks/{id} calls → two execute() calls
        result_a = MagicMock()
        result_a.fetchone.return_value = task_a
        result_b = MagicMock()
        result_b.fetchone.return_value = task_b

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(side_effect=[result_a, result_b])
        mock_db.commit = AsyncMock()

        with db_override(mock_db):
            response_a = await client.get(
                f"/tasks/{task_a_id}", headers=auth_headers("finance_manager")
            )
            response_b = await client.get(
                f"/tasks/{task_b_id}", headers=auth_headers("finance_manager")
            )

        assert response_a.status_code == 200
        assert response_b.status_code == 200
        assert response_a.json()["status"] == "completed"
        assert response_b.json()["status"] == "queued"


# ── Class 5: TestTaskEdgeCases ────────────────────────────────────────────────

class TestTaskEdgeCases:
    """
    Edge cases: authentication, ownership scoping, cancel, retry,
    and null session_id handling.
    """

    async def test_unauthenticated_task_list_rejected(self, client):
        """GET /tasks/ without JWT Authorization header → 401."""
        response = await client.get("/tasks/")
        assert response.status_code == 401

    async def test_task_detail_not_found_for_other_user(self, client):
        """
        User B requests GET /tasks/{user_A_task_id} → 404.
        SQL WHERE clause includes user_id = :uid (User B's uid), so no row
        is found — ownership check prevents cross-user access.
        """
        user_a_task_id = str(uuid.uuid4())

        # DB returns no row (simulates ownership mismatch in SQL filter)
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)

        with db_override(mock_db):
            response = await client.get(
                f"/tasks/{user_a_task_id}",
                headers=auth_headers("sales_rep"),  # different user from task owner
            )

        assert response.status_code == 404

    async def test_cancel_queued_task(self, client):
        """POST /tasks/{id}/cancel on a queued task → 200, status=cancelled, cancelled=true."""
        task_id = str(uuid.uuid4())
        task_row = SimpleNamespace(
            id=task_id,
            task_ref="TASK-XYZ00001",
            status="queued",
        )

        # First execute: SELECT to find task
        select_result = MagicMock()
        select_result.fetchone.return_value = task_row

        # Second execute: UPDATE status='cancelled'
        update_result = MagicMock()
        update_result.fetchone.return_value = None

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(side_effect=[select_result, update_result])
        mock_db.commit = AsyncMock()

        # celery_app.control.revoke() is inside a try/except — mock to avoid import error
        with patch("app.tasks.celery_app.celery_app") as mock_celery_app, \
             db_override(mock_db):
            mock_celery_app.control.revoke.return_value = None

            response = await client.post(
                f"/tasks/{task_id}/cancel",
                headers=auth_headers("finance_manager"),
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "cancelled"
        assert data["cancelled"] is True

    async def test_retry_failed_task(self, client):
        """POST /tasks/{id}/retry on a failed task → 200 with new_task_id returned."""
        original_task_id = str(uuid.uuid4())
        failed_row = SimpleNamespace(
            id=original_task_id,
            task_ref="TASK-FAIL0001",
            session_id=str(uuid.uuid4()),
            department="finance",
            content="Research that failed",
            status="failed",
            queue_name="background",
        )

        # First execute: SELECT to find task
        select_result = MagicMock()
        select_result.fetchone.return_value = failed_row

        # Second execute: INSERT new task row
        insert_result = MagicMock()

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(side_effect=[select_result, insert_result])
        mock_db.commit = AsyncMock()

        # Mock process_agent_task.apply_async() — called by retry endpoint
        new_celery_id = str(uuid.uuid4())
        mock_celery_result = MagicMock()
        mock_celery_result.id = new_celery_id
        mock_celery_result.kwargs = {"task_data": {}}  # mutable dict for agent_task_id injection

        with patch("app.tasks.tasks.process_agent_task") as mock_agent_task, \
             db_override(mock_db):
            mock_agent_task.apply_async.return_value = mock_celery_result

            response = await client.post(
                f"/tasks/{original_task_id}/retry",
                headers=auth_headers("finance_manager"),
            )

        assert response.status_code == 200
        data = response.json()
        assert "new_task_id" in data
        assert data["original_task_id"] == original_task_id
        assert data["new_task_id"] != original_task_id
        assert data["status"] == "queued"
        # new_task_id must be a valid UUID
        uuid.UUID(data["new_task_id"])

    async def test_task_without_session_id(self, client):
        """
        Task with session_id=null still appears in GET /tasks/.
        Mobile handles null session_id gracefully by not linking to a chat session.
        """
        task = _make_task_row(session_id=None, status="running")
        mock_db = _mock_db_for_rows(task)

        with db_override(mock_db):
            response = await client.get("/tasks/", headers=auth_headers("finance_manager"))

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["tasks"][0]["session_id"] is None
