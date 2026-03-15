# Lead Review: BUG-019 — Artifact Routing Wrong Department in Celery Tasks
**Date:** 2026-03-15
**Reviewer:** Lead Agent
**File reviewed:** `server/app/tasks/tasks.py`

---

## Review Checklist

### Correctness
- [x] Root cause addressed: `set_user_context()` now called in both Celery async functions before agent execution
- [x] `_fetch_user_context()` placed before `_run_agent_task()` — correct position (used by both task functions)
- [x] `_run_agent_task()`: context injected after `get_config()` but before `agent.execute()` ✅
- [x] `_run_chat_task()`: context injected after config defaults but before agent resolution ✅
- [x] DB query is parameterized — no SQL injection risk ✅
- [x] `try/except` wraps entire DB lookup — failure returns safe defaults `("", "user")` ✅
- [x] Empty `user_id` guard: returns early with defaults without DB hit ✅
- [x] `_dept` sourced from `task_data["department"]` — available in all call sites ✅

### Safety
- [x] `_fetch_user_context` failures are **non-fatal** (warns + falls back) — existing tasks cannot break
- [x] Default fallback `("", "user")` means Beat tasks without a user_id still work — files go to `self._artifact_dir` (safe flat fallback), not crash
- [x] No changes to any existing function signatures or task data contracts

### Scope
- [x] Single file changed: `tasks.py` only ✅
- [x] No migration needed (code-only fix) ✅
- [x] No frontend or mobile changes required ✅

### One Concern (Non-blocking)
`_run_chat_task` sets `user_id = task_data["user_id"]` on line 414 — same as `_uid_ctx` used in the context injection above. Minor variable duplication but harmless; `user_id` is used extensively below and renaming would be a larger diff.

---

## Decision: ✅ PASS

Fix is correct, minimal, safe, and complete. No revisions needed.

**Deploy steps:**
```bash
cd /home/ubuntu/mz-ai-assistant && git pull
sudo systemctl restart mezzofy-celery.service
sudo systemctl restart mezzofy-beat.service
```

**Verify:**
- Trigger a management scheduled job (`POST /scheduler/jobs/<id>/run`)
- Confirm `.txt` file appears in `/var/mezzofy/artifacts/management/shared/`
- Confirm `/var/mezzofy/artifacts/general/shared/` gets no new files

---

## Version: v1.27.0 (part of this release)
