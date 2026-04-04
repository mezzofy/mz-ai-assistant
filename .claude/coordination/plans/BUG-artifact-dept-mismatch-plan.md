# Bug Fix Plan: Artifact Saved to Agent Department Instead of User's Own Department
**Date:** 2026-04-05
**Lead:** Lead Agent
**Agent:** Backend (1 session)
**Workflow:** Bug Fix
**Branch:** eric-design

---

## Bug Summary

When a scheduler job uses `agent: support` (or any agent that differs from the owner's department), files saved with `storage_scope="user"` go to the **agent's** department folder instead of the **user's own** department folder.

**Example:**
- Owner: `eric@mezzofy.com` (department: `management`)
- Scheduler job agent: `support`
- File saved to: `/var/mezzofy/artifacts/support/eric@mezzofy.com/Email_Summary_030426.txt` ❌
- Expected:       `/var/mezzofy/artifacts/management/eric@mezzofy.com/Email_Summary_030426.txt` ✅

---

## Root Cause

**File:** `server/app/tasks/tasks.py`

Three locations all contain the same pattern:
```python
_dept = task_data.get("department", "general")   # ← bug: agent dept, not user dept
_email, _role = await _fetch_user_context(_uid)
set_user_context(dept=_dept, email=_email, role=_role, user_id=_uid)
```

- `task_data["department"]` reflects the **agent being dispatched** (e.g., "support")
- But `get_user_dept()` (used by `_resolve_output_dir` in text_ops.py) should return the **user's own department** (e.g., "management")
- `_fetch_user_context` only fetches `(email, role)` — it doesn't fetch the user's real department

**File:** `server/app/tools/document/text_ops.py` — `_resolve_output_dir`:
```python
def _resolve_output_dir(self, storage_scope: str = "user") -> Path:
    dept = get_user_dept()   # ← returns agent dept, not owner dept
    email = get_user_email()
    if email:
        return get_user_artifacts_dir(dept, email)  # wrong dept
```

---

## Fix: Two Changes Only

### Change 1 — `server/app/tasks/tasks.py`

**Extend `_fetch_user_context` to also return the user's real department:**

Current signature: `async def _fetch_user_context(user_id: str) -> tuple:`
Returns: `(email, role)`
SQL: `SELECT email, role FROM users WHERE id = :uid`

New signature: same (no change to signature)
Returns: `(email, role, dept)` — add `department` to the SELECT
SQL: `SELECT email, role, department FROM users WHERE id = :uid`

Return value when user not found: `("", "user", "")` — empty dept triggers fallback below.

**Update the 3 call sites** (lines ~360, ~617, ~1145) from:
```python
_dept = task_data.get("department", "general")
_email, _role = await _fetch_user_context(_uid)
set_user_context(dept=_dept, email=_email, role=_role, user_id=_uid)
```
To:
```python
_agent_dept = task_data.get("department", "general")
_email, _role, _user_dept = await _fetch_user_context(_uid)
_dept = _user_dept or _agent_dept   # use real dept; fall back to agent dept if empty
set_user_context(dept=_dept, email=_email, role=_role, user_id=_uid)
```

**Important:** `task_data["department"]` is still used for agent routing (AGENT_MAP lookup on the lines below each set_user_context call) — do NOT change those references.

---

### Change 2 — Verify `users` table has `department` column

Before writing the fix, confirm the column exists:
```sql
SELECT column_name FROM information_schema.columns
WHERE table_name = 'users' AND column_name = 'department';
```

If the column is named differently (e.g., `dept`), adjust the SELECT accordingly.
If the column does not exist, skip the DB lookup and use a different approach (see note below).

> **Note if column missing:** An alternative fix is to pass the owner's department in the `task_data` payload itself when the scheduler creates tasks. In that case, the scheduler job creation API should store `owner_dept` separately from `agent`. But this is more invasive. Prefer the DB lookup fix if the column exists.

---

## Files to Modify

| File | Change |
|------|--------|
| `server/app/tasks/tasks.py` | Extend `_fetch_user_context` return to include dept; update 3 call sites |

No other files need changing.

---

## Quick Fix (User Action — Do This Now)

Separately from the code fix, update the scheduler job via the Mission Control UI:
- Go to Scheduler → "Daily Email Summary to TXT" → Edit
- Change **Agent** from `support` to `management`
- Save

This immediately fixes the job for eric@mezzofy.com. The code fix prevents the issue for any user/agent combination.

---

## Quality Gate

- [ ] `users` table has `department` column — confirmed before coding
- [ ] `_fetch_user_context` returns `(email, role, dept)` tuple
- [ ] All 3 call sites in tasks.py updated to use `_user_dept or _agent_dept`
- [ ] `task_data["department"]` (agent routing) is NOT changed
- [ ] Test: scheduler job with `agent: support` owned by management user → file saves to `management/user@email/`
- [ ] No regression: live chat tasks still save files to the correct user dept
- [ ] Commit to `eric-design` branch

---

## Constraints

- Do not change `router.py` — live chat correctly passes the user's own department from their JWT
- Do not change agent routing logic — only `set_user_context` dept argument is being corrected
- `_agent_dept` local variable name distinguishes it from `_dept` (real user dept) for clarity
