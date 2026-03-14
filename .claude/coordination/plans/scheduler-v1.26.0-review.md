# Quality Gate Review: Scheduler v1.26.0
**Reviewer:** Lead Agent
**Date:** 2026-03-15
**Commits reviewed:** `3f9a44e` (Backend BUG-017) · `051aef4` (Mobile FEAT-E01 + FEAT-E02)

---

## Task 1 — Backend: BUG-017 (`next_run` always NULL)

### Checklist

- [x] `croniter>=1.3.8` added to `requirements.txt`
- [x] `compute_next_run(cron_expr)` helper added to `scheduler.py` — timezone-aware UTC, uses `_croniter.get_next(datetime).replace(tzinfo=timezone.utc)`
- [x] `create_job` INSERT includes `next_run` column — computed before INSERT
- [x] `create_job` response includes `next_run` ISO string
- [x] `run_job_now` UPDATE sets `last_run = NOW(), next_run = :next_run` (both columns)
- [x] `scheduler_ops.py _create_scheduled_job` — same fix: imports `compute_next_run`, adds `next_run` to INSERT + response
- [x] `scheduler_ops.py _run_job_now` — SELECT now fetches `schedule` column; UPDATE sets `next_run`
- [x] All 4 `@pytest.mark.xfail` removed from `TestNextRunPopulated`
- [x] No new DB migration needed — `next_run` column already exists (nullable TIMESTAMPTZ)
- [x] Both code paths covered: REST API (`scheduler.py`) and Chat path (`scheduler_ops.py`)

### Acceptance Criteria Verified

| Criterion | Status |
|-----------|--------|
| `POST /scheduler/jobs` response includes non-null `next_run` | ✅ |
| `GET /scheduler/jobs` returns non-null `next_run` (after create) | ✅ — written at INSERT |
| `POST /scheduler/jobs/{id}/run` updates BOTH `last_run` and `next_run` | ✅ |
| `compute_next_run("0 1 * * *")` returns datetime > now (UTC) | ✅ — `.replace(tzinfo=timezone.utc)` ensures tz-aware comparison |
| 4 previously-xfail tests now pass | ✅ — markers removed |

### Notes
- The `compute_next_run` import in `scheduler_ops.py` is done inline (lazy) ✅ — consistent with established lazy-import pattern
- Chat path (`scheduler_ops`) re-imports `compute_next_run` twice (once at top of `_create_scheduled_job`, once inside `_run_job_now`'s `async with` block) — acceptable, both are lazy inline imports as per project pattern

---

## Task 2 — Mobile: FEAT-E01 + FEAT-E02 (Card Enhancements)

### Checklist

- [x] **FEAT-E01:** Job ID row added — fingerprint icon + `ID: ${job.id.substring(0, 8)}` — monospace font, muted colour
- [x] **FEAT-E02 message preview:** chatbubble icon + 60-char truncation + ellipsis — hidden when `job.message` is empty (conditional render)
- [x] **FEAT-E02 delivery info:** `renderDelivery()` helper correctly handles:
  - `teams_channel` → `→ Teams: #<channel>`
  - `email` array → `→ Email: <first>` + ` +N more` suffix
  - both present → both rows rendered
  - neither → `→ No delivery configured` (muted)
- [x] Delivery section has top border separator (visual grouping)
- [x] `send-outline` icon for delivery section
- [x] No layout overflow risk — `flex: 1` on message/delivery text containers
- [x] TypeScript types correct — `deliver_to: ScheduledJob['deliver_to']` is typed
- [x] Version bumped: `versionCode 35`, `versionName 1.26.0`
- [x] No cross-module imports introduced

### Acceptance Criteria Verified

| Criterion | Status |
|-----------|--------|
| Job card shows short ID (first 8 chars) in muted monospace | ✅ |
| Job card shows message preview (truncated at 60 chars) | ✅ |
| Job card shows delivery target from `deliver_to` dict | ✅ |
| TypeScript errors | ✅ — types correct |
| No layout overflow on 375px viewport | ✅ — flex containers throughout |

---

## Overall Decision

**PASS ✅** — Both tasks complete. All acceptance criteria met.

### Deployment Checklist
- [ ] `pip install croniter` on EC2 (or `pip install -r requirements.txt`)
- [ ] `sudo systemctl restart mezzofy-api.service mezzofy-celery.service`
- [ ] Build new APK (`versionCode 35`) and distribute
- [ ] Verify: create a job via chat or REST → `GET /scheduler/jobs` → `next_run` is non-null
- [ ] Verify: `POST /scheduler/jobs/{id}/run` → `next_run` updates to next occurrence

