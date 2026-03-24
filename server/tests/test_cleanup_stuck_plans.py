"""
Unit tests for the cleanup_stuck_plans Celery task.

Covers:
  1. test_cleanup_stuck_plans_marks_started_step_as_failed
       — step in STARTED status older than 30 min → step FAILED, plan FAILED
  2. test_cleanup_stuck_plans_ignores_recent_steps
       — step in STARTED status but less than 30 min old → not touched
  3. test_cleanup_stuck_plans_ignores_completed_plans
       — plan status COMPLETED → skipped entirely
  4. test_cleanup_stuck_plans_ignores_pending_steps
       — step in PENDING status (never started) → not touched
  5. test_cleanup_stuck_plans_handles_empty_index
       — no plans in index → task completes without error
"""

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch, call

import pytest

pytestmark = pytest.mark.unit


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_plan(
    plan_id: str = "plan-aaa-111",
    status: str = "IN_PROGRESS",
    step_status: str = "STARTED",
    step_started_at: str = None,
    user_id: str = "user-xyz",
    session_id: str = "sess-xyz",
) -> dict:
    """Build a minimal plan dict that matches PlanManager's Redis JSON format."""
    return {
        "plan_id": plan_id,
        "goal": "Test goal",
        "user_id": user_id,
        "session_id": session_id,
        "status": status,
        "created_at": datetime.utcnow().isoformat(),
        "completed_at": None,
        "final_output": None,
        "execution_mode": "sequential",
        "shared_context": {},
        "total_retries": 0,
        "original_task": {},
        "steps": [
            {
                "step_id": "step_1",
                "step_number": 1,
                "agent_id": "agent_management",
                "description": "Do something",
                "depends_on": [],
                "can_run_parallel": False,
                "status": step_status,
                "celery_task_id": "celery-abc",
                "instructions": "",
                "context_keys": [],
                "expected_output_type": "general",
                "output": None,
                "review": None,
                "retry_count": 0,
                "max_retries": 2,
                "started_at": step_started_at,
                "completed_at": None,
                "error": None,
            }
        ],
    }


def _make_mock_redis(plan_id: str = None, plan_dict: dict = None):
    """
    Build a MagicMock that mimics a sync redis.Redis client.

    hkeys("mz:plan:index") returns [plan_id] when plan_id is given, else [].
    get("mz:plan:{plan_id}") returns JSON-serialised plan_dict when supplied.
    """
    r = MagicMock()

    if plan_id is not None:
        r.hkeys.return_value = [plan_id]
    else:
        r.hkeys.return_value = []

    if plan_dict is not None:
        r.get.return_value = json.dumps(plan_dict)
    else:
        r.get.return_value = None

    return r


def _old_started_at(minutes: int = 45) -> str:
    """Return an ISO timestamp N minutes in the past (UTC, no timezone info)."""
    return (datetime.utcnow() - timedelta(minutes=minutes)).isoformat()


def _recent_started_at(minutes: int = 5) -> str:
    """Return an ISO timestamp N minutes in the past — within the threshold."""
    return (datetime.utcnow() - timedelta(minutes=minutes)).isoformat()


# ── Patch target helpers ──────────────────────────────────────────────────────

_REDIS_FROM_URL = "redis.from_url"
_GET_CONFIG = "app.tasks.tasks.get_config"  # patched inside the lazy import block


def _run_task_with_mock_redis(mock_redis):
    """
    Import and invoke cleanup_stuck_plans with redis.from_url patched to return
    mock_redis.  Also patches get_config to return an empty dict so no real
    YAML loading happens.
    """
    # We patch at the source where redis.from_url is called inside the task.
    # The task does `import redis as _redis` then `_redis.from_url(...)`, so we
    # patch the redis module's from_url directly.
    with patch("redis.from_url", return_value=mock_redis), \
         patch("app.core.config.get_config", return_value={}), \
         patch("os.getenv", return_value="redis://localhost:6379"):
        from app.tasks.tasks import cleanup_stuck_plans
        cleanup_stuck_plans()


# ── 1. Stuck step is marked FAILED and plan is marked FAILED ──────────────────

class TestCleanupStuckPlansMarksFailedStep:

    def test_cleanup_stuck_plans_marks_started_step_as_failed(self):
        """
        A STARTED step older than 30 minutes must be marked FAILED,
        and the plan status must be set to FAILED.
        """
        plan_id = "plan-stuck-001"
        plan = _make_plan(
            plan_id=plan_id,
            status="IN_PROGRESS",
            step_status="STARTED",
            step_started_at=_old_started_at(45),
        )
        mock_redis = _make_mock_redis(plan_id=plan_id, plan_dict=plan)

        with patch("redis.from_url", return_value=mock_redis), \
             patch("app.core.config.get_config", return_value={}), \
             patch("os.getenv", return_value="redis://localhost:6379"):
            from app.tasks.tasks import cleanup_stuck_plans
            cleanup_stuck_plans()

        # redis.set must have been called with the updated plan
        assert mock_redis.set.called, "Expected redis.set to be called for the stuck plan"

        set_args = mock_redis.set.call_args
        saved_key = set_args[0][0]
        saved_plan = json.loads(set_args[0][1])

        assert saved_key == f"mz:plan:{plan_id}"
        assert saved_plan["status"] == "FAILED", "Plan status should be FAILED"
        assert saved_plan["completed_at"] is not None, "Plan completed_at should be set"
        assert saved_plan["steps"][0]["status"] == "FAILED", "Step status should be FAILED"
        assert saved_plan["steps"][0]["error"] is not None, "Step error should be set"
        assert saved_plan["steps"][0]["completed_at"] is not None, "Step completed_at should be set"

    def test_ws_notification_published_for_stuck_plan(self):
        """
        A Redis pub/sub notification must be published for the user when a
        plan is marked FAILED.
        """
        plan_id = "plan-stuck-002"
        user_id = "user-notify-test"
        plan = _make_plan(
            plan_id=plan_id,
            status="IN_PROGRESS",
            step_status="STARTED",
            step_started_at=_old_started_at(60),
            user_id=user_id,
        )
        mock_redis = _make_mock_redis(plan_id=plan_id, plan_dict=plan)

        with patch("redis.from_url", return_value=mock_redis), \
             patch("app.core.config.get_config", return_value={}), \
             patch("os.getenv", return_value="redis://localhost:6379"):
            from app.tasks.tasks import cleanup_stuck_plans
            cleanup_stuck_plans()

        assert mock_redis.publish.called, "Expected redis.publish to be called"
        publish_channel = mock_redis.publish.call_args[0][0]
        assert publish_channel == f"user:{user_id}:notifications"

        published_payload = json.loads(mock_redis.publish.call_args[0][1])
        assert published_payload["type"] == "agent_plan_failed"
        assert published_payload["plan_id"] == plan_id


# ── 2. Recent steps are not touched ──────────────────────────────────────────

class TestCleanupStuckPlansIgnoresRecentSteps:

    def test_cleanup_stuck_plans_ignores_recent_steps(self):
        """
        A STARTED step younger than 30 minutes must NOT be modified.
        No redis.set call should occur for the plan.
        """
        plan_id = "plan-recent-001"
        plan = _make_plan(
            plan_id=plan_id,
            status="IN_PROGRESS",
            step_status="STARTED",
            step_started_at=_recent_started_at(5),
        )
        mock_redis = _make_mock_redis(plan_id=plan_id, plan_dict=plan)

        with patch("redis.from_url", return_value=mock_redis), \
             patch("app.core.config.get_config", return_value={}), \
             patch("os.getenv", return_value="redis://localhost:6379"):
            from app.tasks.tasks import cleanup_stuck_plans
            cleanup_stuck_plans()

        mock_redis.set.assert_not_called()
        mock_redis.publish.assert_not_called()


# ── 3. Completed plans are skipped ────────────────────────────────────────────

class TestCleanupStuckPlansIgnoresCompletedPlans:

    def test_cleanup_stuck_plans_ignores_completed_plans(self):
        """
        A plan with status COMPLETED must be skipped — redis.set must not be
        called even if a step appears to have an old started_at.
        """
        plan_id = "plan-done-001"
        plan = _make_plan(
            plan_id=plan_id,
            status="COMPLETED",
            step_status="COMPLETED",
            step_started_at=_old_started_at(90),
        )
        plan["steps"][0]["completed_at"] = datetime.utcnow().isoformat()
        mock_redis = _make_mock_redis(plan_id=plan_id, plan_dict=plan)

        with patch("redis.from_url", return_value=mock_redis), \
             patch("app.core.config.get_config", return_value={}), \
             patch("os.getenv", return_value="redis://localhost:6379"):
            from app.tasks.tasks import cleanup_stuck_plans
            cleanup_stuck_plans()

        mock_redis.set.assert_not_called()

    def test_cleanup_stuck_plans_ignores_failed_plans(self):
        """
        A plan already in FAILED status must be skipped.
        """
        plan_id = "plan-failed-001"
        plan = _make_plan(
            plan_id=plan_id,
            status="FAILED",
            step_status="FAILED",
            step_started_at=_old_started_at(90),
        )
        mock_redis = _make_mock_redis(plan_id=plan_id, plan_dict=plan)

        with patch("redis.from_url", return_value=mock_redis), \
             patch("app.core.config.get_config", return_value={}), \
             patch("os.getenv", return_value="redis://localhost:6379"):
            from app.tasks.tasks import cleanup_stuck_plans
            cleanup_stuck_plans()

        mock_redis.set.assert_not_called()


# ── 4. PENDING steps are not touched ─────────────────────────────────────────

class TestCleanupStuckPlansIgnoresPendingSteps:

    def test_cleanup_stuck_plans_ignores_pending_steps(self):
        """
        A step with status PENDING (never dispatched) must not be modified.
        No redis.set call should occur.
        """
        plan_id = "plan-pending-001"
        plan = _make_plan(
            plan_id=plan_id,
            status="IN_PROGRESS",
            step_status="PENDING",
            step_started_at=None,
        )
        mock_redis = _make_mock_redis(plan_id=plan_id, plan_dict=plan)

        with patch("redis.from_url", return_value=mock_redis), \
             patch("app.core.config.get_config", return_value={}), \
             patch("os.getenv", return_value="redis://localhost:6379"):
            from app.tasks.tasks import cleanup_stuck_plans
            cleanup_stuck_plans()

        mock_redis.set.assert_not_called()
        mock_redis.publish.assert_not_called()


# ── 5. Empty index — no plans ─────────────────────────────────────────────────

class TestCleanupStuckPlansHandlesEmptyIndex:

    def test_cleanup_stuck_plans_handles_empty_index(self):
        """
        When mz:plan:index returns no plan IDs, the task must complete without
        error and must not attempt any redis.get or redis.set calls.
        """
        mock_redis = _make_mock_redis(plan_id=None)  # hkeys returns []

        with patch("redis.from_url", return_value=mock_redis), \
             patch("app.core.config.get_config", return_value={}), \
             patch("os.getenv", return_value="redis://localhost:6379"):
            from app.tasks.tasks import cleanup_stuck_plans
            # Must not raise
            cleanup_stuck_plans()

        mock_redis.get.assert_not_called()
        mock_redis.set.assert_not_called()
        mock_redis.publish.assert_not_called()
