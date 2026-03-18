# Release Notes — mz-ai-assistant v1.33.0
**Date:** 2026-03-18
**Type:** Feature — Mission Control Admin Portal
**Commit:** ae04c18
**Branch:** eric-design
**Deployed:** EC2 `ubuntu@3.1.255.48` ✅

---

## Summary

Adds a secure React admin web portal at `/mission-control` — accessible to `admin@mezzofy.com` only. Provides real-time visibility into AI sessions, LLM cost tracking, system health, agent office status, scheduled tasks, RAG knowledge, file management, and user management.

---

## What's New

### Backend — `/api/admin-portal/*` (20 endpoints)

**Auth**
- `GET /api/admin-portal/auth/me` — Verify admin token, return user info

**Dashboard** (4 endpoints)
- `GET /dashboard/sessions` — Active sessions across all users (polls every 30s in UI)
- `GET /dashboard/llm-usage?period=today|week|month` — Token + cost usage by model, with daily budget % tracking
- `GET /dashboard/system-vitals` — CPU %, memory, disk (via psutil) + service health checks (FastAPI, PostgreSQL, Redis, Celery workers)
- `GET /dashboard/agent-status` — Per-department busy state + tasks completed today from `agent_tasks` table

**Scheduler** (4 endpoints)
- `GET /scheduler/jobs` — All scheduled jobs with owner info
- `GET /scheduler/jobs/{id}/history` — Last 50 run records from `agent_tasks`
- `POST /scheduler/jobs/{id}/trigger` — Manual job trigger via Celery + audit log
- `PATCH /scheduler/jobs/{id}/toggle` — Toggle `is_active` + audit log

**Agents** (2 endpoints)
- `GET /agents` — Agent registry with real-time task counts + RAG file counts
- `GET /agents/{name}/rag-memory` — List knowledge files in `knowledge/{dept}/`

**Files** (2 endpoints)
- `GET /files?user_id=&type=&page=&per_page=20` — Paginated artifact list with owner info
- `DELETE /files/{id}` — Delete DB record + physical file + audit log

**Users** (5 endpoints)
- `GET /users` — All active users (soft-delete aware) with session counts
- `POST /users` — Create user + generate `invite_token` + send invite via Outlook
- `GET /users/{id}` — Full profile + recent sessions
- `PATCH /users/{id}` — Update name/department/role/is_active + audit log
- `DELETE /users/{id}` — Soft-delete (sets `deleted_at`, `is_active=FALSE`) + blacklist all tokens + audit log

### Database Migration (migrate.py)

Two new columns added to `users` table:
```sql
ALTER TABLE users ADD COLUMN IF NOT EXISTS invite_token VARCHAR(64);
ALTER TABLE users ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;
```

### Configuration (config.example.yaml)

New `admin_portal:` block:
```yaml
admin_portal:
  allowed_email: "${ADMIN_EMAIL}"
  session_idle_minutes: 30
  portal_domain: "${PORTAL_DOMAIN}"
  llm_budgets:
    claude-sonnet: { daily_usd: 50.0 }
    claude-haiku: { daily_usd: 10.0 }
    claude-opus: { daily_usd: 100.0 }
    kimi: { daily_usd: 20.0 }
  file_retention_days: 90
```

### Frontend — `portal/` (React + TypeScript + Vite)

**Auth Pages**
- `LoginPage` — Dark glassmorphism card with animated grid background
- `OtpPage` — 6 separate digit inputs with auto-advance focus, 60-second resend timer

**Dashboard Page** — 4 sections:
1. **Session Monitor** — live table: User · Dept · Agent · Messages · Last Active · Status badge
2. **LLM Fuel Gauges** — horizontal bar per model; green → amber at 80% → red at 95% of daily budget
3. **System Vitals** — CPU radial gauge, memory/disk bars, service status dot grid
4. **Agent Office Pixel Art** — HTML5 canvas (800×400, responsive), 6 department sprites:
   - Manager (center, larger desk, glasses + purple tie)
   - Finance (green visor), Sales (blue headset), Marketing (orange beret)
   - Support (teal headset), HR (pink folder)
   - Idle: 2s bob animation. Busy: animated `●●●` speech bubble.

**Scheduler Page** — Split panel: jobs table (▶ trigger, ⏸ toggle) + run history timeline

**Agents Page** — 3-column card grid: name, status dot, tasks today, skills chips, "View Memory ›" accordion with file list

**Files Page** — Full-width table with type filter + pagination (20/page) + delete confirmation modal

**Users Page** — Table with Avatar + "New User" invite modal + edit modal (active toggle) + soft-delete modal

**Tech stack:** React 18 + TypeScript + Vite 5 + React Query + Zustand + Tailwind CSS + Recharts
**Auth security:** Tokens stored in Zustand only — never localStorage/sessionStorage. Page refresh = re-authenticate (intentional for admin security). `AdminRoute` guard checks `role === "admin"` from JWT.
**Build:** 289KB JS bundle (gzip: 91KB), zero TypeScript errors.

---

## Infrastructure Changes

**`server/requirements.txt`**
- Added: `psutil==5.9.8`

**`server/config/nginx.conf`**
```nginx
location /mission-control {
    alias /home/ubuntu/mz-ai-assistant/portal/dist;
    try_files $uri $uri/ /mission-control/index.html;
}
location /api/admin-portal/ {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
}
```

---

## Tests

`server/tests/test_admin_portal.py` — 8 new unit tests:
1. `test_non_admin_email_rejected` — executive role → 403
2. `test_unauthenticated_request_401` — missing token → 401
3. `test_wrong_role_403` — sales_rep → 403
4. `test_create_user_sets_invite_token` — invite_token is 32-char UUID hex
5. `test_delete_user_soft_deletes` — UPDATE with deleted_at set, not hard DELETE
6. `test_system_vitals_returns_required_fields` — cpu/memory/disk/services all present
7. `test_manual_trigger_returns_task_id` — task_id returned in response
8. `test_llm_usage_today_period` — period=today returns model list

---

## Deploy Steps (Completed)

```bash
# On EC2: ubuntu@3.1.255.48
git pull origin eric-design
cd server && python scripts/migrate.py       # added invite_token + deleted_at
pip install psutil==5.9.8
cd ../portal && npm install && npm run build  # outputs to portal/dist/
sudo nginx -s reload
sudo systemctl restart mezzofy-api.service
```

---

## Security Notes

- All `/api/admin-portal/*` endpoints use `Depends(require_role("admin"))` — no middleware, no separate auth system
- Non-admin JWTs receive HTTP 403 on all portal endpoints
- `DELETE /users/{id}` calls `blacklist_all_user_tokens()` — invalidates all active sessions immediately
- `invite_token` stored but no auto-activation flow in v1.33.0 — admin must manually activate user (`PATCH /users/{id}` with `is_active: true`)
- Frontend holds no tokens in persistent storage — intentional security tradeoff

---

## Known Limitations (v1.33.0)

- **No invite activation flow:** `invite_token` is generated and emailed but no `/auth/activate?token=` endpoint exists yet. Admin must manually set `is_active=TRUE` via PATCH endpoint or DB.
- **Celery worker count:** System vitals `celery_workers` count comes from `inspect.active()` with 2s timeout — may show 0 under high load if workers are all busy.
- **Canvas `roundRect`:** Uses `// @ts-ignore` for older TS DOM lib versions that don't include `CanvasRenderingContext2D.roundRect`. Works in modern Chromium browsers.
- **Portal not yet on eric-design → main:** Merge + push to main pending.

---

## Version History

| Version | Date | Description |
|---------|------|-------------|
| v1.33.0 | 2026-03-18 | Mission Control admin portal |
| v1.32.0 | 2026-03-18 | Shared folder delivery fix |
| v1.31.0 | 2026-03-16 | Webhook push + notification logging fix |
| v1.30.0 | 2026-03-16 | Notification history screen |
| v1.29.1 | 2026-03-16 | Celery timezone UTC fix |
| v1.28.0 | 2026-03-16 | Push notifications |
| v1.27.0 | 2026-03-15 | Artifact routing ContextVar fix |
| v1.26.1 | 2026-03-15 | next_run backfill script |
| v1.26.0 | 2026-03-15 | SchedulerAgent + next_run fix |
| v1.25.0 | 2026-03-15 | Scheduler chat tools |
| v1.23.0 | 2026-03-14 | ResearchAgent + DeveloperAgent |
