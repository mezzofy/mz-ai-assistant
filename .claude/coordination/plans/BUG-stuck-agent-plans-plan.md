# Bug Fix Plan: Stuck Agent Plans in Redis Never Cleaned Up

**Plan ID:** BUG-stuck-agent-plans
**Date:** 2026-03-24
**Priority:** High
**Version:** v1.35.0
**Assigned To:** Backend Agent
**Workflow:** workflow-bug-fix

---

## Bug Summary

**BUG-021:** Agent Plans stored in Redis DB3 can get stuck in `IN_PROGRESS` status indefinitely when the Celery worker executing a plan step dies. The existing `cleanup_stuck_tasks` beat task only cleans the `agent_tasks` PostgreSQL table — Redis-based plans are never cleaned.

**Confirmed stuck plan:** `3cdeb84d-d0a5-41ad-8fd7-20acd3271f4d`
- Step 1 status: `STARTED` since `2026-03-24T11:47:58`
- Celery task `59b6215e-3434-45e3-b54b-605070bda15c` — worker is dead
- Plan will never resolve without manual Redis intervention

---

## Root Cause

- `cleanup_stuck_tasks` in `app/tasks/tasks.py` only queries PostgreSQL `agent_tasks` table
- Agent Plans are stored in Redis DB3 under key `mz:plan:{plan_id}`
- Plan index is `mz:plan:index` (Redis hash: `plan_id → user_id`)
- No periodic task scans Redis plans for stuck steps
- No TTL set on plan keys

---

## Fix Scope

**Files to modify:**
1. `server/app/tasks/tasks.py` — add `cleanup_stuck_plans()` Celery task
2. `server/app/tasks/beat_schedule.py` — register new task in beat schedule

**Files to read first:**
- `server/app/tasks/tasks.py` — understand existing `cleanup_stuck_tasks` pattern
- `server/app/tasks/beat_schedule.py` — understand schedule registration
- `server/app/orchestrator/plan_manager.py` — understand Redis key structure and plan dataclass
- `server/app/tasks/orchestrator_tasks.py` — understand WebSocket notification pattern for plan completion/failure

---

## Implementation Spec

### Task: `cleanup_stuck_plans`

**Location:** `server/app/tasks/tasks.py` — add after `cleanup_stuck_tasks`

**Logic:**
```
1. Get sync Redis client on DB3 (use redis.Redis(db=3))
2. Get all plan IDs from mz:plan:index (HKEYS)
3. For each plan_id:
   a. GET mz:plan:{plan_id} → parse JSON
   b. If plan status != IN_PROGRESS → skip
   c. For each step in plan.steps:
      - If step.status == STARTED:
        - Parse step.started_at
        - If age > STUCK_PLAN_THRESHOLD (30 minutes):
          - Mark step.status = FAILED
          - Set step.error = "Worker died - step timed out after 30 minutes"
          - Set step.completed_at = utcnow().isoformat()
   d. If any step was just marked FAILED:
      - Mark plan.status = FAILED
      - Set plan.completed_at = utcnow().isoformat()
      - SET mz:plan:{plan_id} back to Redis DB3
      - Log: logger.warning(f"Plan {plan_id} marked FAILED - step timed out")
      - Send WebSocket notification to user (see pattern below)
4. Log summary: "cleanup_stuck_plans: checked N plans, marked M as failed"
```

**WebSocket notification pattern** (copy from `orchestrator_synthesise` in `orchestrator_tasks.py`):
```python
await ws_manager.send_to_session(
    session_id=plan["session_id"],
    message={
        "type": "agent_plan_failed",
        "plan_id": plan_id,
        "message": "Agent plan timed out. The worker processing this task stopped responding. Please try again."
    }
)
```

**STUCK_PLAN_THRESHOLD:** 30 minutes (1800 seconds). Define as module-level constant.

**Important:** This task uses Redis directly (sync, DB3). Do NOT use the async Redis client. Use `redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=3, decode_responses=True)`.

**Important:** Wrap entire task in try/except. Log errors but do NOT raise — cleanup tasks must never crash the worker.

**Important:** The task is a standard `@celery_app.task` (not async). Use `asyncio.run()` only for the WebSocket send if needed, OR use a fire-and-forget approach via `asyncio.create_task` if event loop is available.

### Beat Schedule Registration

**Location:** `server/app/tasks/beat_schedule.py`

Add to `STATIC_BEAT_SCHEDULE`:
```python
"cleanup-stuck-plans": {
    "task": "app.tasks.tasks.cleanup_stuck_plans",
    "schedule": crontab(minute="*/15"),  # Every 15 minutes
},
```

---

## Tests Required

**File:** `server/tests/test_cleanup_stuck_plans.py`

Test cases:
1. `test_cleanup_stuck_plans_marks_started_step_as_failed` — step STARTED >30min ago → marked FAILED, plan FAILED
2. `test_cleanup_stuck_plans_ignores_recent_steps` — step STARTED <30min ago → not touched
3. `test_cleanup_stuck_plans_ignores_completed_plans` — plan status COMPLETED → skipped
4. `test_cleanup_stuck_plans_ignores_pending_steps` — step PENDING → not touched
5. `test_cleanup_stuck_plans_handles_empty_index` — no plans in index → no error

Use mocked Redis with `unittest.mock.patch`.

---

## Acceptance Criteria

- [ ] `cleanup_stuck_plans` task exists and runs without error
- [ ] Plans with STARTED steps older than 30 min get marked FAILED
- [ ] Plans not stuck are not modified
- [ ] Beat schedule updated — task runs every 15 minutes
- [ ] 5 unit tests passing
- [ ] No new imports at module top (follow lazy import pattern if needed)
- [ ] Task logs warning for each plan marked FAILED

---

## Deploy Steps

1. Git push → EC2 git pull
2. Restart mezzofy-celery.service (picks up new beat schedule)
3. Restart mezzofy-api.service
4. Verify: `sudo journalctl -u mezzofy-celery.service -n 50` — should show cleanup_stuck_plans scheduled

---

## Version Tag

`v1.35.0` — BUG-021: Add cleanup_stuck_plans beat task for Redis plan timeout detection
