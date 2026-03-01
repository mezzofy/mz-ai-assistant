# Context Checkpoint: Backend Agent
**Date:** 2026-02-28
**Project:** mz-ai-assistant
**Session:** 10 (BUG-001 hotfix)
**Context:** ~10% at checkpoint
**Reason:** BUG-001 fixed — `_build_payload` KeyError on token refresh

## BUG-001 Fix (2026-02-28)

**File:** `server/app/core/auth.py`
**Change:** `_build_payload()` — replaced `user["id"]` with `user.get("id") or user.get("user_id")`
**Result:** `POST /auth/refresh` now returns 200. Test shows XPASS (confirms fix works).
**Pending:** Tester Agent must remove `@pytest.mark.xfail(strict=True)` from `test_auth.py::TestRefreshToken::test_refresh_valid_token`

---

## Completed This Session (Phase 6)

| # | File | Status |
|---|------|--------|
| 1 | `server/app/tasks/celery_app.py` | ✅ Created — Celery init, Redis broker/backend, all settings |
| 2 | `server/app/tasks/webhook_tasks.py` | ✅ Created — handle_mezzofy_event, handle_teams_mention, handle_custom_event + delivery |
| 3 | `server/app/tasks/tasks.py` | ✅ Created — process_agent_task, health_check, _run_agent_task |
| 4 | `server/app/tasks/beat_schedule.py` | ✅ Created — 5 static schedules + DatabaseScheduler + DB job loader |
| 5 | `server/app/webhooks/webhooks.py` | ✅ Full implementation (was stub) — HMAC auth, 3 webhook endpoints + events audit |
| 6 | `server/app/webhooks/scheduler.py` | ✅ Full implementation (was stub) — CRUD + manual trigger |

---

## Key Architectural Decisions (Phase 6)

| Decision | Reasoning |
|----------|-----------|
| Tasks in `app.tasks` module path | Plan takes precedence over INFRASTRUCTURE.md (confirmed in memory.md) |
| Celery tasks are sync + `asyncio.run()` | Celery workers don't run asyncio event loop; async agent code wrapped in asyncio.run() |
| `DatabaseScheduler(PersistentScheduler)` | Custom scheduler merges static + DB jobs at Beat startup — no redbeat dependency needed |
| DB jobs loaded at Beat startup only | v1.0 simplicity: jobs become active after Beat restart. POST /jobs/{id}/run for immediate execution |
| HMAC verification skipped if WEBHOOK_SECRET unset | Dev-mode safety: logs warning, doesn't crash. Production requires WEBHOOK_SECRET env var |
| Teams auth via TEAMS_BOT_SECRET | Phase 6 uses simple bearer token. Production needs full MS Bot Framework JWT validation |
| Webhook endpoints: lazy import Celery tasks | Avoids circular imports at FastAPI startup before Celery is fully configured |
| `/webhooks/events` uses `Depends(require_role)` | Not on `/chat/*` path so ChatGatewayMiddleware doesn't set request.state.user |
| `deliver_to` graceful degradation | Teams/email/push delivery failures log warning and continue — don't fail the task |

---

## Phase 6 All Files (Complete)

### New in Session 6A
- ✅ `server/app/tasks/celery_app.py`
- ✅ `server/app/tasks/webhook_tasks.py`
- ✅ `server/app/tasks/tasks.py`
- ✅ `server/app/tasks/beat_schedule.py`
- ✅ `server/app/webhooks/webhooks.py` (full implementation replacing stub)
- ✅ `server/app/webhooks/scheduler.py` (full implementation replacing stub)

### Still From Phase 5 (Complete)
- ✅ `server/app/router.py`
- ✅ `server/app/input/` (8 handlers)
- ✅ `server/app/context/` (3 files)
- ✅ `server/app/output/` (2 files)
- ✅ `server/app/api/chat.py`, `files.py`, `admin.py`
- ✅ `server/app/main.py`
- ✅ `server/app/core/config.py`

---

## Quality Gate Criteria (Phase 6)

- Celery Beat fires `weekly_kpi_report` job: ✅ in `STATIC_BEAT_SCHEDULE` with `crontab(hour=1, minute=0, day_of_week=1)` (9AM SGT = 1AM UTC)
- Webhooks return 200 immediately + enqueue Celery task: ✅ all 3 webhook endpoints enqueue task via `.delay()` then return immediately
- Scheduler API: users can CRUD their own scheduled tasks: ✅ GET/POST/GET/{id}/PUT/{id}/DELETE/{id}/POST/{id}/run

---

## Env Vars Required for Phase 6

| Variable | Used For | Default |
|----------|----------|---------|
| `REDIS_URL` | Celery broker | `redis://localhost:6379/0` |
| `REDIS_RESULT_BACKEND` | Celery result backend | `redis://localhost:6379/1` |
| `CELERY_CONCURRENCY` | Worker concurrency | `4` |
| `WEBHOOK_SECRET` | HMAC webhook signature verification | `""` (skips verification in dev) |
| `TEAMS_BOT_SECRET` | Teams bot bearer token | `""` (skips verification in dev) |

---

## Correct Import Paths (Phase 6 reference)

| Class/Function | Correct Import |
|----------------|----------------|
| `celery_app` | `from app.tasks.celery_app import celery_app` |
| `process_agent_task` | `from app.tasks.tasks import process_agent_task` |
| `handle_mezzofy_event` | `from app.tasks.webhook_tasks import handle_mezzofy_event` |
| `handle_teams_mention` | `from app.tasks.webhook_tasks import handle_teams_mention` |
| `handle_custom_event` | `from app.tasks.webhook_tasks import handle_custom_event` |
| `DatabaseScheduler` | `from app.tasks.beat_schedule import DatabaseScheduler` |

---

## How to Run (Phase 6+)

```bash
# Terminal 1: FastAPI server
cd server && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2: Celery workers (4 concurrent)
cd server && celery -A app.tasks.celery_app worker --loglevel=info --concurrency=4

# Terminal 3: Celery Beat (scheduled jobs)
cd server && celery -A app.tasks.celery_app beat --loglevel=info \
    --scheduler app.tasks.beat_schedule:DatabaseScheduler
```

---

## What's Left (Phase 7+)

- Phase 7: Server Tests — pytest suite (auth, 5 department workflows, scheduler, webhook, security, LLM)
- Phase 8: Mobile Integration — replace DEMO_RESPONSES with real API calls in APP/
- Phase 9: E2E Tests
- Phase 10: Docs

Phase 6 is complete. Ready for Lead Agent Phase 6 quality gate review.
Return to Lead terminal for Phase 6 quality gate review.

---

## Resume Instructions (if needed)

After /clear, load in order:
1. CLAUDE.md
2. .claude/agents/backend.md
3. .claude/skills/backend-developer.md
4. .claude/coordination/memory.md
5. This checkpoint file
6. .claude/coordination/plans/mz-ai-assistant-server-v1.0.md

Phase 6 is complete. No resume needed — go to Lead terminal for review.
