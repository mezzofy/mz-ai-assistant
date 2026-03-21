# Plan: CR — Rename "Task/Title" → "Message/Content" (v1.48.0)
**Workflow:** change-request
**Date:** 2026-03-21
**Created by:** Lead Agent

---

## Context

Each `agent_tasks` record is created when a user sends a message that triggers a background Celery job.
The `title` column stores the first 80 characters of the user's message — so it IS the message content.
From a user perspective, what is displayed as "Task / Task ID / Title" should read "Message / Message ID / Content".

---

## Scope: What Changes vs What Stays

### ✅ RENAME
| Layer | From | To |
|-------|------|----|
| DB column | `agent_tasks.title` | `agent_tasks.content` |
| Backend API response field | `"title"` | `"content"` |
| Portal page heading | "Tasks" | "Messages" |
| Portal nav item label | "Tasks" | "Messages" |
| Portal column header | "Task ID" | "Message ID" |
| Portal column header | "Title" | "Content" |
| Portal TypeScript type | `AgentTask.title` | `AgentTask.content` |
| Mobile badge label | `"Task ID: "` | `"Message ID: "` |
| Mobile TypeScript type | `TaskSummary.title` (if present) | `TaskSummary.content` |

### ❌ DO NOT RENAME (out of scope)
| What | Why |
|------|-----|
| Table name `agent_tasks` | Huge blast radius, not requested |
| Python variable `task`, `task_data` | Internal code, not user-facing |
| Celery task names | Infrastructure, not user-facing |
| Internal route path `/tasks` in portal (URL) | Not mentioned — keep URL stable to avoid broken bookmarks |
| DB column `task_ref` | This is Celery's internal ID, not the user-facing ID |

---

## Files to Modify

### Backend (3 files + 1 migration)

#### 1. `server/scripts/migrate.py`
Add a new migration step at the end of the `main()` function:
```sql
ALTER TABLE agent_tasks RENAME COLUMN title TO content;
```
This is safe — if already renamed, wrap in a `DO $$ BEGIN ... EXCEPTION WHEN undefined_column THEN NULL; END $$;` guard.

#### 2. `server/app/api/tasks.py`
- `_row_to_dict()` helper (lines 302–324): change `"title": row.title` → `"content": row.content`
- Any SQL SELECT that references `title` column → rename to `content`
- Where `agent_tasks` is INSERTed with `title=...` → rename to `content=...`

#### 3. `server/app/api/admin_portal.py`
- GET `/api/admin-portal/tasks` endpoint (lines 1259–1329): change `"title"` → `"content"` in SELECT + response dict

#### 4. `server/app/api/chat.py` (and/or `server/app/tasks/tasks.py`)
- Where `agent_tasks.title` is SET when creating a task (INSERT) → rename param to `content`
- Search for: `"title"` in any INSERT INTO agent_tasks statement or task dict construction

---

### Portal Frontend (3 files)

#### 1. `portal/src/pages/TasksPage.tsx`
- Page heading: `"Tasks"` → `"Messages"`
- Column header: `"Task ID"` → `"Message ID"`
- Column header: `"Title"` → `"Content"`
- Data reference: `t.title` → `t.content`

#### 2. `portal/src/types/index.ts`
- `AgentTask` interface: `title: string` → `content: string`

#### 3. Portal nav component (find the nav file that lists "Tasks")
- Search for "Tasks" nav label in `portal/src/` → change to "Messages"

---

### Mobile App (2 files)

#### 1. `APP/src/screens/HistoryScreen.tsx`
- Badge label: `'Task ID: '` → `'Message ID: '`

#### 2. `APP/src/api/chat.ts`
- `TaskSummary` type: if `title` field exists → rename to `content`
- Any `.title` reference on TaskSummary objects → `.content`

---

## Task Breakdown

| # | Task | Agent | Files | Depends On | Est. Sessions | Status |
|---|------|-------|-------|-----------|:-------------:|--------|
| 1 | Backend: DB column rename + API field rename | Backend | migrate.py, tasks.py, admin_portal.py, chat.py/tasks.py | None | 1 | NOT STARTED |
| 2 | Portal: UI label + type rename | Frontend | TasksPage.tsx, index.ts, nav component | Can parallel Task 1 | 1 | NOT STARTED |
| 3 | Mobile: UI label + type rename | Mobile | HistoryScreen.tsx, chat.ts | Can parallel Task 1 | 1 | NOT STARTED |
| 4 | Tester: update tests | Tester | server/tests/, portal/tests (if any) | 1, 2, 3 | 1 | NOT STARTED |
| 5 | Lead review | Lead | plans/ | 4 | — | NOT STARTED |

## Parallel Opportunities
- Tasks 1, 2, 3 can all run in parallel (spec is fixed: field becomes `content`)
- Task 4 after all three complete

---

## Quality Gate

- [ ] `agent_tasks.content` column exists (migration ran successfully)
- [ ] `agent_tasks.title` column no longer exists
- [ ] Backend API responses return `"content"` not `"title"` for task records
- [ ] Portal "Tasks" page heading reads "Messages"
- [ ] Portal table headers read "Message ID" and "Content"
- [ ] Portal TypeScript type has `content` not `title`
- [ ] Mobile History badge reads "Message ID: " not "Task ID: "
- [ ] Mobile TypeScript type updated
- [ ] No TypeScript errors in portal or mobile
- [ ] All existing backend tests pass (no `title` field assertion regressions)
- [ ] EC2 deploy requires running `migrate.py` before restarting services

---

## Deploy Order (IMPORTANT)

```
1. git pull on EC2
2. cd server && python scripts/migrate.py   ← rename DB column FIRST
3. sudo systemctl restart mezzofy-api.service
4. sudo systemctl restart mezzofy-celery.service
5. Portal: npm run build on EC2 (portal/dist is gitignored)
6. Mobile: rebuild APK
```

**⚠️ Do NOT restart the API before running migrate.py — code expects `content` column but DB still has `title` until migration runs.**

---

## Version
- **Version:** v1.48.0
- **RN entry:** "Renamed 'Tasks' to 'Messages' across Portal and Mobile — Task ID → Message ID, Title → Content, reflecting that each item represents a user message sent to an AI agent"
