# Change Request Plan: Token & Model Display in Tasks Page

**Plan ID:** CR-tasks-token-display
**Date:** 2026-03-24
**Priority:** Medium
**Version:** v1.37.0
**Workflow:** workflow-change-request

---

## Goal

Under Portal > Tasks, surface LLM token usage and model name in all three tabs:
- **Active Tasks** — tokens consumed + model per task row
- **Scheduled Tasks** — tokens column (shows "—" — no direct session linkage)
- **Agent Plans** — tokens consumed + model per plan row

Token data lives in the `llm_usage` PostgreSQL table, linked to tasks/plans via `session_id`.

---

## Scope

| Agent | Files | Scope |
|-------|-------|-------|
| Backend | `server/app/api/tasks.py` | Add token totals to active tasks response |
| Backend | `server/app/api/plans.py` | Add token totals to plans list response |
| Frontend | `portal/src/types/index.ts` | Add token fields to `AgentTask`, `Plan`, `PlanDetail` types |
| Frontend | `portal/src/pages/BackgroundTasksPage.tsx` | Render token/model in all 3 tabs |

Agents work **in parallel** — backend and frontend can be done simultaneously.

---

## Data Architecture

### Source of truth
- `llm_usage` table: `session_id`, `model`, `input_tokens`, `output_tokens`, `cost_usd`
- `agent_tasks` table: `id`, `session_id` — links tasks to llm_usage
- Redis plans: `plan["session_id"]` — links plans to llm_usage

### Why Scheduled Tasks show "—"
Scheduled jobs (cron) run as their own session without a direct `job_id → session_id` mapping in the database. No reliable join possible. Display "—" in the UI.

---

## Backend Spec

### Read first
- `server/app/api/tasks.py` — full file (understand `GET /api/admin-portal/tasks` response shape)
- `server/app/api/plans.py` — full file (understand `GET /api/plans` response shape)
- `server/scripts/migrate.py` lines 140–165 — llm_usage table schema
- `server/scripts/migrate.py` lines 227–260 — agent_tasks table schema

---

### Fix 1: `server/app/api/tasks.py`

**Goal:** Add `total_tokens`, `input_tokens`, `output_tokens`, `llm_model` to each task in `GET /api/admin-portal/tasks`.

**Logic:** In the endpoint that returns the list of agent tasks, after fetching the task rows, run a **batch lookup** joining `agent_tasks` with `llm_usage` on `session_id`:

```sql
SELECT
    at.id                          AS task_id,
    COALESCE(SUM(lu.input_tokens),  0) AS input_tokens,
    COALESCE(SUM(lu.output_tokens), 0) AS output_tokens,
    COALESCE(SUM(lu.input_tokens + lu.output_tokens), 0) AS total_tokens,
    STRING_AGG(DISTINCT lu.model, ', ' ORDER BY lu.model) AS llm_model
FROM agent_tasks at
LEFT JOIN llm_usage lu ON lu.session_id = at.session_id
WHERE at.id = ANY(:task_ids)
GROUP BY at.id
```

- Collect `task_ids` from the existing task rows already fetched
- Run one batch query (not N+1 per task)
- Merge results back into each task dict by `task_id`
- If a task has no `session_id` or no llm_usage rows → `total_tokens=0`, `llm_model=None`

**New fields to add to each task dict in the response:**
```python
{
  ...existing fields...,
  "total_tokens": int,       # sum of input + output tokens
  "input_tokens": int,
  "output_tokens": int,
  "llm_model": str | None,   # e.g. "claude-sonnet-4-6" or "claude-sonnet-4-6, claude-haiku-4-5"
}
```

**All imports are lazy** (inside function body — follow project pattern).

---

### Fix 2: `server/app/api/plans.py`

**Goal:** Add `total_tokens`, `input_tokens`, `output_tokens`, `llm_model` to each plan in `GET /api/plans`.

**Logic:** Plans are loaded from Redis. Each plan dict has a `session_id`. After loading the plan list from Redis, run a **batch query** against `llm_usage`:

```sql
SELECT
    session_id,
    COALESCE(SUM(input_tokens),  0) AS input_tokens,
    COALESCE(SUM(output_tokens), 0) AS output_tokens,
    COALESCE(SUM(input_tokens + output_tokens), 0) AS total_tokens,
    STRING_AGG(DISTINCT model, ', ' ORDER BY model) AS llm_model
FROM llm_usage
WHERE session_id = ANY(:session_ids)
GROUP BY session_id
```

- Collect `session_ids` from all plan dicts loaded from Redis
- Run one batch query using async SQLAlchemy (same pattern as other endpoints in plans.py)
- Merge token totals into each plan dict keyed by `session_id`
- If plan has no `session_id` or no llm_usage rows → `total_tokens=0`, `llm_model=None`

**New fields added to each plan in the list response:**
```python
{
  ...existing fields...,
  "total_tokens": int,
  "input_tokens": int,
  "output_tokens": int,
  "llm_model": str | None,
}
```

**Use async SQLAlchemy** (same as existing code in plans.py — check the existing pattern for DB access).

---

## Frontend Spec

### Read first
- `portal/src/pages/BackgroundTasksPage.tsx` — full file (find all 3 tab components)
- `portal/src/types/index.ts` — current type definitions

### Fix 1: `portal/src/types/index.ts`

Add token fields to existing interfaces:

```typescript
export interface AgentTask {
  // ...existing fields...
  total_tokens?: number
  input_tokens?: number
  output_tokens?: number
  llm_model?: string | null
}

export interface Plan {
  // ...existing fields...
  total_tokens?: number
  input_tokens?: number
  output_tokens?: number
  llm_model?: string | null
}

export interface PlanDetail extends Plan {
  // ...existing fields (no additional token fields needed at step level)...
}
```

---

### Fix 2: `portal/src/pages/BackgroundTasksPage.tsx`

#### Tab 1: Active Tasks

Find the table that renders active task rows (look for the task list/table, it maps over `AgentTask[]`).

Add two new table header cells after the existing columns:
```
| Model | Tokens |
```

In each task row, add:
- **Model cell**: Show a small pill/badge with the model short name
  - Shorten long model names: `"claude-sonnet-4-6"` → `"Sonnet 4.6"`, `"claude-haiku-4-5-20251001"` → `"Haiku 4.5"`
  - If `llm_model` is null/undefined → show `"—"`
  - Style: small dark pill, `#1a1a1a` bg, `#ffffff` text, `text-xs`
- **Tokens cell**: Show total token count
  - Format with commas: `1234` → `"1,234"`, `0` → `"—"`
  - Show as `"{total_tokens.toLocaleString()}"`
  - Style: `text-xs text-gray-400 font-mono`

#### Tab 2: Scheduled Tasks

Find the table that renders scheduled job rows (maps over `ScheduledJob[]`).

Add two new header cells:
```
| Model | Tokens |
```

In each scheduled job row, show `"—"` for both cells (no token data available for cron jobs).
- Style: `text-xs text-gray-500`

#### Tab 3: Agent Plans

Find the `PlanRow` component (around line 675 per previous plan).

Add token/model display inside the plan row, **next to the existing status badge** or below the goal text — position it naturally in the row layout.

- **Model badge**: Same short-name pill as Active Tasks
  - If `llm_model` is null → `"—"`
- **Tokens**: `{plan.total_tokens?.toLocaleString() ?? '—'} tokens`
  - Style: `text-xs text-gray-400 font-mono`

**Model name shortener helper** (add near top of file or as a local util):
```typescript
function shortModelName(model: string | null | undefined): string {
  if (!model) return '—'
  if (model.includes('sonnet-4-6')) return 'Sonnet 4.6'
  if (model.includes('sonnet-4-5')) return 'Sonnet 4.5'
  if (model.includes('opus-4')) return 'Opus 4'
  if (model.includes('haiku-4-5')) return 'Haiku 4.5'
  if (model.includes('haiku-3')) return 'Haiku 3'
  if (model.includes('kimi')) return 'Kimi'
  // fallback: truncate to 16 chars
  return model.length > 16 ? model.slice(0, 14) + '…' : model
}
```

---

## Acceptance Criteria

### Backend
- [ ] `GET /api/admin-portal/tasks` returns `total_tokens`, `input_tokens`, `output_tokens`, `llm_model` per task
- [ ] `GET /api/plans` returns `total_tokens`, `input_tokens`, `output_tokens`, `llm_model` per plan
- [ ] Both use batch queries (no N+1)
- [ ] Tasks/plans with no llm_usage data return `total_tokens=0`, `llm_model=null`
- [ ] Lazy imports only

### Frontend
- [ ] Active Tasks table shows Model + Tokens columns
- [ ] Scheduled Tasks table shows Model + Tokens columns (both "—")
- [ ] Agent Plans rows show model badge + token count
- [ ] Model names are shortened to readable labels (Sonnet 4.6, Haiku 4.5, etc.)
- [ ] Zero tokens shows "—" not "0"
- [ ] Null/undefined model shows "—"
- [ ] Mezzofy brand styling (dark bg pills, orange accent optional)

---

## Version Tag

`v1.37.0` — CR: Token & Model display in Tasks page (Active Tasks, Scheduled Tasks, Agent Plans)
