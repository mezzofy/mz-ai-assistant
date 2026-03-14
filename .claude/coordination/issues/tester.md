# Tester Issues — 2026-03-15

## BUG-017: `next_run` always NULL in `scheduled_jobs`

**Severity:** High (UX — mobile shows "—" / "Not yet scheduled" for every job)
**Reported by:** User screenshot 2026-03-15 01:15 SGT
**Affects:** All users — REST API and Chat path both affected

### Root Cause (confirmed by code review)

The `next_run` column (`TIMESTAMPTZ`, nullable) is never written by any application code:

| Code path | What it writes | Missing |
|-----------|---------------|---------|
| `scheduler.py` `create_job` | INSERT without `next_run` | ❌ `next_run` |
| `scheduler.py` `run_job_now` | `UPDATE SET last_run = NOW()` | ❌ `next_run` |
| `scheduler_ops.py` `_create_scheduled_job` | INSERT without `next_run` | ❌ `next_run` |
| `scheduler_ops.py` `_run_job_now` | `UPDATE SET last_run = NOW()` | ❌ `next_run` |
| `beat_schedule.py` `DatabaseScheduler` | Reads DB only (one-way loader) | — never writes back |

Celery Beat's `PersistentScheduler` stores schedule state in `celerybeat-schedule`
(shelve file on disk) — it does NOT write `next_run` back to `scheduled_jobs`.

### Fix Required (Backend Agent)

1. **Add `croniter` to `requirements.txt`** — standard cron next-run calculation library.

2. **Add `compute_next_run(cron_expr: str) -> datetime` helper** in `scheduler.py`:
   ```python
   from croniter import croniter
   from datetime import datetime, timezone

   def compute_next_run(cron_expr: str) -> datetime:
       base = datetime.now(timezone.utc)
       return croniter(cron_expr, base).get_next(datetime)
   ```

3. **`scheduler.py` `create_job`**: Add `next_run` to INSERT params.

4. **`scheduler.py` `run_job_now`**: Change UPDATE to also set `next_run`.

5. **`scheduler_ops.py` `_create_scheduled_job`**: Same as #3 (import `compute_next_run`
   from `app.webhooks.scheduler` or a shared utility).

6. **`scheduler_ops.py` `_run_job_now`**: Same as #4.

### Acceptance Tests

4 xfail tests added to `server/tests/test_scheduler.py` (class `TestNextRunPopulated`):
- `test_create_job_response_includes_next_run` — response has non-null `next_run`
- `test_create_job_inserts_next_run_into_db` — INSERT params contain `next_run`
- `test_run_job_now_updates_next_run` — UPDATE SQL sets both `last_run` and `next_run`
- `test_next_run_is_in_future` — `compute_next_run()` returns future datetime

Remove `xfail` markers once the fix is merged.

---

## FEAT-E01: Display Job ID on Mobile Scheduled Tasks Screen

**Type:** Enhancement (Mobile scope)
**Requested by:** User 2026-03-15

The mobile ScheduleStatsScreen should show the job UUID (or short prefix, e.g.
`ID: abc12345`) on each job card. Helps users reference a specific job when
asking the chat agent to "delete" or "run" a job by ID, and for troubleshooting.

**Backend:** No change needed — `id` already returned in `GET /scheduler/jobs` response.
**Mobile scope:** ScheduleStatsScreen job card — add ID row below the cron expression.

---

## FEAT-E02: Display Output Information on Scheduled Tasks Screen

**Type:** Enhancement (Backend + Mobile scope)
**Requested by:** User 2026-03-15

Users want to see WHERE results go: which Teams channel, which email address,
or what file the job generates. Currently the `deliver_to` JSON is returned
by the API but not surfaced on the mobile card.

**Backend change:** `GET /scheduler/jobs` already returns `deliver_to` dict.
Optionally add a `deliver_to_summary` string field (e.g. "Teams: #sales, Email: 2 recipients")
computed server-side for cleaner mobile rendering.

**Mobile scope:** ScheduleStatsScreen job card — add a delivery target row
(e.g. `→ Teams: #sales` or `→ Email: cfo@mezzofy.com`).
Also display `message` (the prompt text) as a preview — already in API response.
