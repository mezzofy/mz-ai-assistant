# Plan: Scheduler v1.26.0 — next_run Fix + Card Enhancements
**Workflow:** bug-fix + change-request
**Date:** 2026-03-15
**Created by:** Lead Agent
**Version:** v1.26.0

---

## Summary

Three items from Tester BUG-017 report and user screenshots:

| Item | Type | Agent | Depends On |
|------|------|-------|-----------|
| BUG-017: `next_run` always NULL | Bug | Backend | — |
| FEAT-E01: Show Job ID on card | Enhancement | Mobile | — |
| FEAT-E02: Show delivery info + message on card | Enhancement | Mobile | — |

**Backend and Mobile can run in parallel — no dependency between them.**

---

## Task 1 — Backend Agent: Fix BUG-017 (`next_run` never populated)

### Files to Modify

#### `server/requirements.txt`
Add `croniter>=1.3.8` — standard Python cron next-run computation library.
(Already a Celery transitive dependency in many setups — pinning explicitly for clarity.)

#### `server/app/webhooks/scheduler.py`
1. Import `croniter` at top of file.
2. Add `compute_next_run(cron_expr: str) -> datetime` helper function:
   ```python
   def compute_next_run(cron_expr: str) -> datetime:
       """Compute the next UTC run time for a given 5-field cron expression."""
       from croniter import croniter as _croniter
       base = datetime.now(timezone.utc)
       return _croniter(cron_expr, base).get_next(datetime)
   ```
3. **`create_job`** endpoint: compute `next_run = compute_next_run(cron_expr)` after
   `cron_expr = _schedule_dto_to_cron(body.schedule)`, add to INSERT params and response.
4. **`run_job_now`** endpoint: change UPDATE to:
   `UPDATE scheduled_jobs SET last_run = NOW(), next_run = :next_run WHERE id = :id`
   Compute `next_run` from `row.schedule` before the UPDATE.

#### `server/app/tools/scheduler/scheduler_ops.py`
5. **`_create_scheduled_job`**: Import `compute_next_run` from
   `app.webhooks.scheduler`, compute after cron validation, add to INSERT + response.
6. **`_run_job_now`**: Same — compute and add `next_run` to UPDATE.

#### `server/tests/test_scheduler.py`
7. Remove the 4 `@pytest.mark.xfail` markers from `TestNextRunPopulated`.
   The tests must now PASS.

### Acceptance Criteria (BUG-017)
- `POST /scheduler/jobs` response includes non-null `next_run` ISO timestamp
- `GET /scheduler/jobs` returns non-null `next_run` for newly created jobs
- `POST /scheduler/jobs/{id}/run` updates BOTH `last_run` and `next_run`
- `compute_next_run("0 1 * * *")` returns a datetime > now (UTC)
- All 4 previously-xfail tests pass

---

## Task 2 — Mobile Agent: FEAT-E01 + FEAT-E02 (Scheduled Tasks Card Enhancements)

### Context
The `GET /scheduler/jobs` API already returns all needed data:
```json
{
  "id": "uuid",
  "name": "...",
  "agent": "sales",
  "schedule": "0 1 * * *",
  "message": "email lead report",
  "deliver_to": {"teams_channel": "sales"},
  "last_run": "...",
  "next_run": "..."   ← will be populated after BUG-017 fix
}
```
**No backend changes needed for FEAT-E01 or FEAT-E02.**

### File to Modify: `APP/src/screens/ScheduleStatsScreen` (or wherever the card is rendered)

Read the current screen first to understand the component structure.

#### FEAT-E01: Show Job ID
- Add a row to each job card showing the short job ID: `ID: {id.substring(0, 8)}`
- Style: small monospace text, muted colour (e.g. `#888`)
- Position: below the cron expression line

#### FEAT-E02: Show delivery info + message preview
- **Message preview:** Show `message` field truncated to ~60 chars with ellipsis
  - Label: message icon `✉` or small prompt icon
  - Only show if `message` is non-empty
- **Delivery target:** Compute from `deliver_to` dict:
  - `teams_channel` present → show `→ Teams: #<channel>`
  - `email` array present → show `→ Email: <first_email>` (+ `+N more` if multiple)
  - Both present → show both on separate sub-rows
  - Neither present → show `→ No delivery configured` (muted)
- Position: below the message preview, above the action buttons (if any)

### Acceptance Criteria (Mobile)
- Job card shows short ID (first 8 chars of UUID) in muted monospace
- Job card shows message preview (truncated at 60 chars)
- Job card shows delivery target (Teams channel / email / none) from `deliver_to`
- No TypeScript errors
- No layout overflow on standard phone viewport (375px wide)

---

## Parallel Execution

```
Terminal A: /boot-backend  → Fix BUG-017 (requirements.txt + scheduler.py + scheduler_ops.py + tests)
Terminal B: /boot-mobile   → FEAT-E01 + FEAT-E02 (ScheduleStatsScreen card enhancements)
```

Both can start simultaneously. No shared files touched.

---

## Quality Gate (Lead reviews after both complete)

- [ ] `next_run` populated in DB after create and run_now (verified via GET /scheduler/jobs)
- [ ] All 4 TestNextRunPopulated tests pass (xfail markers removed)
- [ ] No regression in existing scheduler test suite
- [ ] Mobile card shows ID, message, delivery info
- [ ] No TypeScript errors in mobile build
- [ ] `croniter` version pinned in requirements.txt

---

## Session Estimates

| Agent | Tasks | Est. Sessions |
|-------|-------|:---:|
| Backend | BUG-017 (6 edit points) | 1 |
| Mobile | FEAT-E01 + FEAT-E02 | 1 |
