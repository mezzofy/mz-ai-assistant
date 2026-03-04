# Plan: Route Generated Files to {dept}/{email}/ Subdirectories
**Workflow:** change-request
**Date:** 2026-03-04
**Created by:** Lead Agent

---

## Problem Statement

All 4 document tools (`PDFOps`, `PPTXOps`, `DocxOps`, `CSVOps`) write generated files
to **flat legacy directories** (`/var/mezzofy/artifacts/pdfs/`, etc.). User identity is
not available at tool construction time, so there is no per-user routing.

**Target:** Generated files must land in `{base}/{dept}/{email}/{filename}` — same
structure as uploads (completed today).

---

## Root Cause Analysis

```
chat.py builds task dict           → has current_user (email, dept)
  ↓
router.py _execute_with_instance() → dispatches to agent.execute(task)
  ↓
agent.execute(task)                → calls LLMManager.run(task)
  ↓
LLMManager tool loop               → calls ToolExecutor.execute(tool_name, **llm_params)
  ↓
PDFOps._create_pdf(**llm_params)   → uses self._artifact_dir (set at startup, flat)
```

**Gap 1:** `email` is NOT in the task dict (only `department`, `user_id` are present).
**Gap 2:** No mechanism threads user identity through the tool call chain.

---

## Approach: Python `contextvars.ContextVar`

Idiomatic async-safe per-request context variable — threads user identity through the
call stack without modifying every function signature.

**Single set point:** `router.py._execute_with_instance()` — ALL task sources (mobile,
scheduler, webhook) pass through this single function before agent dispatch.

**Fallback:** Scheduler/webhook tasks have no email → ContextVar returns `""` → tools
fall back to existing flat `self._artifact_dir` (correct behaviour for system tasks).

---

## Task Breakdown

| # | Task | Files | Depends On |
|---|------|-------|-----------|
| 1 | Create `user_context.py` ContextVar module | `server/app/core/user_context.py` (NEW) | — |
| 2 | Add `email` to task dict in `chat.py` | `server/app/api/chat.py` | — |
| 3 | Set ContextVar in `router.py` before agent dispatch | `server/app/router.py` | Tasks 1, 2 |
| 4 | Route PDF output to user dir | `server/app/tools/document/pdf_ops.py` | Task 1 |
| 5 | Route PPTX output to user dir | `server/app/tools/document/pptx_ops.py` | Task 1 |
| 6 | Route DOCX output to user dir | `server/app/tools/document/docx_ops.py` | Task 1 |
| 7 | Route CSV output to user dir | `server/app/tools/document/csv_ops.py` | Task 1 |

**All 7 tasks can be completed in one Backend Agent session.**

---

## File-by-File Implementation Spec

### Task 1 — NEW `server/app/core/user_context.py`

```python
"""
Per-request user context using Python ContextVars.

Set once in router.py before agent dispatch.
Read by document tools to determine the per-user artifact directory.
"""
from contextvars import ContextVar

_user_dept: ContextVar[str] = ContextVar("user_dept", default="general")
_user_email: ContextVar[str] = ContextVar("user_email", default="")


def set_user_context(dept: str, email: str) -> None:
    """Set the current request's user context. Called by router before agent dispatch."""
    _user_dept.set(dept or "general")
    _user_email.set(email or "")


def get_user_dept() -> str:
    return _user_dept.get()


def get_user_email() -> str:
    return _user_email.get()
```

---

### Task 2 — `server/app/api/chat.py`

Locate where the task dict is built for mobile requests (the `POST /chat/send` handler
and related endpoints). Add `"email"` to the task dict:

```python
# BEFORE (existing):
"department": current_user.get("department", ""),
"role": current_user.get("role", ""),
"user_id": current_user["user_id"],

# AFTER (add one line):
"department": current_user.get("department", ""),
"role": current_user.get("role", ""),
"user_id": current_user["user_id"],
"email": current_user.get("email", ""),     # ← NEW
```

**Important:** Find ALL places in chat.py where a task dict is built and assembled
(there may be multiple — for REST send, send-media, send-url, and WebSocket).
Add `"email"` consistently to all of them.

---

### Task 3 — `server/app/router.py`

In `_execute_with_instance()` (line 135), set the ContextVar **before** dispatching:

```python
# Add import at top of file:
from app.core.user_context import set_user_context

# In _execute_with_instance(), add before agent.execute(task):
async def _execute_with_instance(agent, task: dict) -> dict:
    """Execute task with an already-constructed agent instance."""
    agent_label = agent.__class__.__name__.replace("Agent", "").lower()
    logger.info(
        f"Dispatching to {agent.__class__.__name__} "
        f"(source={task.get('source', 'mobile')}, "
        f"message={task.get('message', '')[:60]!r})"
    )
    # Set per-request user context for tool artifact routing
    set_user_context(
        dept=task.get("department", "general"),
        email=task.get("email", ""),
    )
    result = await agent.execute(task)
    result.setdefault("agent_used", agent_label)
    return result
```

---

### Task 4 — `server/app/tools/document/pdf_ops.py`

In `_create_pdf()` and `_merge_pdfs()`, resolve output dir at call-time rather than
using `self._artifact_dir`:

```python
# Add imports at top of file:
from app.core.user_context import get_user_dept, get_user_email
from app.context.artifact_manager import get_user_artifacts_dir

# Add this helper at module level (or inside class):
def _resolve_output_dir(self) -> Path:
    """Return per-user dir if user context is set, else fall back to flat dir."""
    email = get_user_email()
    if email:
        return get_user_artifacts_dir(get_user_dept(), email)
    return self._artifact_dir
```

In `_create_pdf()`, replace:
```python
output_path = self._artifact_dir / f"{filename}.pdf"
```
With:
```python
output_path = self._resolve_output_dir() / f"{filename}.pdf"
```

In `_merge_pdfs()`, replace:
```python
output_path = self._artifact_dir / f"{output_filename}.pdf"
```
With:
```python
output_path = self._resolve_output_dir() / f"{output_filename}.pdf"
```

---

### Task 5 — `server/app/tools/document/pptx_ops.py`

Same pattern as Task 4. Add imports + `_resolve_output_dir()` method.

In `_create_pptx()`, replace:
```python
output_path = self._artifact_dir / f"{filename}.pptx"
```
With:
```python
output_path = self._resolve_output_dir() / f"{filename}.pptx"
```

---

### Task 6 — `server/app/tools/document/docx_ops.py`

Same pattern as Task 4.

In `_create_docx()`, replace:
```python
output_path = self._artifact_dir / f"{filename}.docx"
```
With:
```python
output_path = self._resolve_output_dir() / f"{filename}.docx"
```

---

### Task 7 — `server/app/tools/document/csv_ops.py`

Same pattern as Task 4.

In `_create_csv()`, replace:
```python
output_path = self._artifact_dir / f"{filename}.csv"
```
With:
```python
output_path = self._resolve_output_dir() / f"{filename}.csv"
```

---

## Quality Gate

After Backend Agent completes all 7 tasks, Lead will verify:

- [ ] `user_context.py` has ContextVar with `default=""` (not None — avoids type errors)
- [ ] `chat.py` — `"email"` added to ALL task-building sites (search for `"user_id": current_user`)
- [ ] `router.py` — `set_user_context()` called BEFORE `agent.execute(task)`, not after
- [ ] All 4 doc tools use `_resolve_output_dir()` — no direct reference to `self._artifact_dir` in create handlers
- [ ] Fallback to `self._artifact_dir` when `email == ""` (scheduler/webhook safety)
- [ ] Existing tests still pass (`python -m pytest tests/ -x -q`)

---

## Resulting Behavior After Change

| Scenario | Before | After |
|----------|--------|-------|
| Sales rep generates PDF | `/var/mezzofy/artifacts/pdfs/Report_abc123.pdf` | `/var/mezzofy/artifacts/sales/sales.rep@mezzofy.com/Report_abc123.pdf` |
| Scheduler weekly KPI | `/var/mezzofy/artifacts/pdfs/kpi_xyz.pdf` | `/var/mezzofy/artifacts/pdfs/kpi_xyz.pdf` ← unchanged (no email) |
| Finance manager exports CSV | `/var/mezzofy/artifacts/csv/export_def456.csv` | `/var/mezzofy/artifacts/finance/finance.manager@mezzofy.com/export_def456.csv` |

---

## Agent Assignment

**Agent:** Backend Agent (1 session — all changes are surgical, no new abstractions)
**Session estimate:** 1 session (7 small changes in 7 files)
**Parallel opportunity:** None — all tasks share imports, better done sequentially

---

## Out of Scope

- `merge_pdfs` for scheduler tasks (no user context → flat dir fallback is correct)
- Tests update (existing tests mock artifact_manager — should pass; Backend should verify)
- `image_ops`, `video_ops`, `audio_ops` — these are processing tools, not generators
