# Plan: BUG-019 — Artifact Routing Wrong Department in Celery Tasks
**Workflow:** bug-fix
**Date:** 2026-03-15
**Created by:** Lead Agent

---

## Bug Summary

**Symptom:** `Mezzofy_AI_Assistant_Features_List.txt` saved to
`/var/mezzofy/artifacts/general/shared` instead of
`/var/mezzofy/artifacts/management/shared`.

**Root Cause:** Python `ContextVar` values set by `router.py` via
`set_user_context()` are **not propagated to Celery worker processes**.
ContextVars are coroutine-scoped and do not cross process boundaries.

When `process_agent_task` or `process_chat_task` runs in a Celery worker:
- `get_user_dept()` returns the default `"general"` (not "management")
- `get_user_email()` returns `""` (not the user's email)

Result: `text_ops._resolve_output_dir("department")` routes to
`/var/mezzofy/artifacts/general/shared` for every Celery task regardless
of the actual user's department.

**Affected tools:** `create_txt`, `create_pdf`, `create_csv`, `create_pptx`,
`create_docx` — any tool that calls `_resolve_output_dir()` when invoked
from a Celery background task.

**Affected code paths:**
- Scheduled jobs via Beat (`process_agent_task`)
- Manual job runs via `POST /scheduler/jobs/{id}/run` (`process_agent_task`)
- Long-running chat tasks via `process_chat_task`

---

## Agents Required

| Agent | Work |
|-------|------|
| **Backend** | Fix `tasks.py` — call `set_user_context()` in both async functions |

Single-agent fix. No frontend or mobile changes needed.

---

## Fix Design

### File: `server/app/tasks/tasks.py`

**Change 1 — `_run_agent_task()` (line ~181)**

After `config = get_config()` and before `agent.execute(task_data)`,
inject user context into the ContextVars:

```python
# Restore user context (not propagated across Celery process boundary)
from app.core.user_context import set_user_context
dept = task_data.get("department", "general")
user_id_val = task_data.get("user_id", "")
# Look up email + role from DB so doc tools route files to correct dir
_email, _role = await _fetch_user_context(user_id_val)
set_user_context(dept=dept, email=_email, role=_role, user_id=user_id_val)
```

**Change 2 — `_run_chat_task()` (line ~341)**

Same injection, placed right after config is loaded and before agent execution:

```python
from app.core.user_context import set_user_context
dept = task_data.get("department", "general")
user_id_val = task_data.get("user_id", "")
_email, _role = await _fetch_user_context(user_id_val)
set_user_context(dept=dept, email=_email, role=_role, user_id=user_id_val)
```

**Change 3 — new helper `_fetch_user_context()`**

Add a small async helper that fetches email + role from the users table.
Falls back gracefully if user_id is empty (Beat tasks without a user):

```python
async def _fetch_user_context(user_id: str) -> tuple[str, str]:
    """Fetch email + role for the given user_id. Returns ('', 'user') on failure."""
    if not user_id:
        return ("", "user")
    try:
        from app.core.database import AsyncSessionLocal
        from sqlalchemy import text
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                text("SELECT email, role FROM users WHERE id = :uid"),
                {"uid": user_id},
            )
            row = result.fetchone()
            if row:
                return (row.email or "", row.role or "user")
    except Exception as e:
        logger.warning(f"_fetch_user_context failed for user_id={user_id!r}: {e}")
    return ("", "user")
```

**Why DB lookup instead of passing email in task_data:**
- Scheduled job `task_data` (built in `scheduler.py`) does not include email.
- Many existing Beat tasks and webhook tasks also omit email.
- Centralizing the lookup in `tasks.py` fixes all callers without changing every
  task dispatch site.

---

## EC2 Steps After Code Fix

No DB migration needed — this is a code-only fix.

```bash
# On EC2
cd /home/ubuntu/mz-ai-assistant
git pull
sudo systemctl restart mezzofy-api.service
sudo systemctl restart mezzofy-celery.service
sudo systemctl restart mezzofy-beat.service
```

---

## Verification

```bash
# 1. Trigger a management scheduled job (run_now)
curl -X POST -H "Authorization: Bearer <mgmt-token>" \
  http://localhost:8000/scheduler/jobs/<job-id>/run

# 2. Wait for task to complete, then check EC2 filesystem
ls /var/mezzofy/artifacts/management/shared/
# Expected: Mezzofy_AI_Assistant_Features_List.txt present here

ls /var/mezzofy/artifacts/general/shared/
# Expected: NO new .txt file here
```

---

## Tests to Update

```bash
cd server && venv/bin/pytest tests/test_tasks.py -v
```

If `test_tasks.py` mocks `_run_agent_task`, ensure the test still passes after
the `set_user_context` call is added. No new test cases required for this patch
(existing scheduler tests exercise the code path).

---

## Files Modified

| File | Change |
|------|--------|
| `server/app/tasks/tasks.py` | Add `_fetch_user_context()` helper; call `set_user_context()` in `_run_agent_task()` + `_run_chat_task()` |

---

## Status

| Task | Agent | Status |
|------|-------|--------|
| Fix `tasks.py` | Backend | NOT STARTED |
