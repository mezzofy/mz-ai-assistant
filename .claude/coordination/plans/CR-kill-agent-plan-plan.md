# Change Request Plan: Kill Agent Plan Button

**Plan ID:** CR-kill-agent-plan
**Date:** 2026-03-24
**Priority:** High
**Version:** v1.36.0
**Workflow:** workflow-change-request

---

## Goal

Add a "Kill Job" button to the Agent Plans UI in Mission Control Portal. The button appears next to "View Detail" when a plan's status is `IN_PROGRESS`. Clicking it calls a new backend endpoint that revokes all running Celery tasks for that plan and marks the plan as `FAILED`.

---

## Scope

| Agent | Files | Scope |
|-------|-------|-------|
| Backend | `server/app/api/plans.py` | Add `POST /api/plans/{plan_id}/kill` endpoint |
| Frontend | `portal/src/pages/BackgroundTasksPage.tsx` | Add Kill Job button to `PlanRow` component |

Agents work **in parallel** — no dependency between backend and frontend changes.

---

## Backend Spec

### File: `server/app/api/plans.py`

**Add endpoint:** `POST /api/plans/{plan_id}/kill`

**Logic:**
```
1. Load plan from Redis (plan_manager.load_plan)
   - If not found → 404
2. Check plan status:
   - If NOT IN_PROGRESS → 400 "Plan is not in progress (status: {status})"
3. For each step in plan.steps:
   - If step.status == "STARTED" AND step.celery_task_id is not None:
     - Call celery_app.control.revoke(step.celery_task_id, terminate=True)
     - Log: logger.info(f"kill_plan: revoked celery task {step.celery_task_id} for step {step.step_id}")
4. Update all non-COMPLETED steps to FAILED:
   - For each step where status NOT IN ("COMPLETED",):
     - step["status"] = "FAILED"
     - step["error"] = "Killed by admin"
     - step["completed_at"] = datetime.utcnow().isoformat()
5. Mark plan as FAILED:
   - plan["status"] = "FAILED"
   - plan["completed_at"] = datetime.utcnow().isoformat()
6. Save plan back to Redis DB3 (r.set f"mz:plan:{plan_id}")
7. Return 200: {"status": "killed", "plan_id": plan_id, "steps_cancelled": N}
```

**All imports are lazy** (inside function body — follow project pattern).
**Use sync Redis DB3** (same as cleanup_stuck_plans — `redis.Redis(host=..., port=..., db=3, decode_responses=True)`).
**Use celery_app.control.revoke** (same pattern as existing `/tasks/{task_id}/kill` endpoint in tasks.py).

**Read first:**
- `server/app/api/plans.py` — full file to understand existing patterns
- `server/app/api/tasks.py` — find the kill endpoint for the `revoke` pattern
- `server/app/orchestrator/plan_manager.py` — Redis key format and how to load/save plans sync
- `server/app/tasks/tasks.py` lines 150-290 — see `cleanup_stuck_plans` for the sync Redis DB3 pattern

**Response schema:**
```python
return {
    "status": "killed",
    "plan_id": plan_id,
    "steps_cancelled": count_of_non_completed_steps_that_were_updated
}
```

---

## Frontend Spec

### File: `portal/src/pages/BackgroundTasksPage.tsx`

**Component:** `PlanRow` (around line 675)

**Add "Kill Job" button:**
- Show ONLY when `plan.status === "IN_PROGRESS"`
- Position: next to the existing "View Detail" / "Hide Detail" toggle button
- Style: Mezzofy brand — small red/danger button matching existing UI patterns
- Text: "Kill Job"
- Icon: use a Stop or X icon from the existing icon library (look at what icons are imported)
- On click: show confirmation dialog ("Are you sure you want to kill this plan?"), then call API

**API call:**
```typescript
const res = await fetch(`/api/plans/${plan.plan_id}/kill`, {
  method: 'POST',
  headers: { Authorization: `Bearer ${token}` }
})
```

**After success:**
- Show a brief success toast/notification: "Plan killed successfully"
- Refresh the plan list (trigger the existing refresh mechanism)
- The plan row should update to show FAILED status

**After error:**
- Show error message (use existing error handling pattern in the file)

**State needed:**
- `killingPlanId: string | null` — tracks which plan is being killed (for loading state on the button)
- Reset to null after API response

**Read first:**
- `portal/src/pages/BackgroundTasksPage.tsx` — full `PlanRow` component and surrounding context
- Look for: how auth tokens are accessed, how refresh is triggered, what icon library is imported, how other action buttons are styled

---

## Acceptance Criteria

### Backend
- [ ] `POST /api/plans/{plan_id}/kill` returns 200 for IN_PROGRESS plans
- [ ] Returns 404 for unknown plan_id
- [ ] Returns 400 for plans not IN_PROGRESS
- [ ] All STARTED steps have their Celery tasks revoked
- [ ] Plan status set to FAILED in Redis DB3
- [ ] Lazy imports only

### Frontend
- [ ] "Kill Job" button visible only on IN_PROGRESS plans
- [ ] Button shows loading state while API call is in flight
- [ ] Confirmation dialog before kill
- [ ] Success: plan list refreshes, plan shows FAILED
- [ ] Error: error message shown
- [ ] Mezzofy brand styling (orange/black/white theme)

---

## Version Tag

`v1.36.0` — CR: Kill Agent Plan button in Mission Control Portal
