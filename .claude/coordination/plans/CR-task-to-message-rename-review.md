# Review: CR — Rename Task/Title → Message/Content (v1.48.0)
**Date:** 2026-03-21
**Reviewer:** Lead Agent
**Plan:** CR-task-to-message-rename-plan.md

---

## Quality Gate Checklist

### DB Migration
- [x] `migrate.py` has idempotent rename: `IF EXISTS (title) → RENAME TO content`
- [x] CREATE TABLE DDL updated: `content TEXT NOT NULL` (was `title`)

### Backend API
- [x] `tasks.py` — all SQL SELECTs, INSERTs, `_row_to_dict()` use `content`
- [x] `admin_portal.py` — tasks list endpoint + agents status endpoint use `content`
- [x] `chat.py` — INSERT `content: body.message[:80]`
- [x] `tasks.py` (Celery) — `task_row.content` in status helpers
- [x] `processor.py` — INSERT `content: user_message[:80]`
- [x] **Bonus fix:** `admin_portal.py` `MAX(title)` SQL caught and fixed by Tester

### Portal
- [x] Page heading "Tasks" → "Messages"
- [x] Column header "Task ID" → "Message ID"
- [x] Column header "Title" → "Content"
- [x] Empty-state "No tasks" → "No messages"
- [x] Pagination "total tasks" → "total messages"
- [x] Nav item "Tasks" → "Messages" (URL `/mission-control/tasks` unchanged)
- [x] `AgentTask` TypeScript type: `title` → `content`
- [x] Zero remaining `t.title` references in portal

### Mobile
- [x] History tab badge "Task ID: " → "Message ID: "
- [x] `TaskSummary` TypeScript type: `title` → `content`
- [x] Zero remaining `Task ID` strings in `APP/src/`

### Tests
- [x] `test_task_management.py` — 5 fixture/assertion fixes, 26/26 pass
- [x] No new test failures introduced
- [x] Pre-existing Redis failure unchanged

---

## Decision: ✅ PASS

All layers clean — zero stale `title` references on `agent_tasks` objects confirmed by grep.

---

## Deploy Instructions (ORDER MATTERS)

```bash
# On EC2:
git pull
cd server && python scripts/migrate.py    # ← MUST run FIRST (renames DB column)
sudo systemctl restart mezzofy-api.service
sudo systemctl restart mezzofy-celery.service

# Portal rebuild (portal/dist is gitignored):
cd portal && npm install && npm run build

# Mobile: rebuild APK in next release
```

**⚠️ Do NOT restart the API before running migrate.py — the code now expects `content` column.**

**Version:** v1.48.0
