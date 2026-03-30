# Plan: Scheduler Portal Enhancement v1.57.0
**Workflow:** change-request
**Date:** 2026-03-30
**Created by:** Lead Agent

## Summary

Enhance the Portal Scheduler page with Create Job + Delete Job operations,
and fix a broken Edit (PUT) that silently fails due to `updated_at` column not existing.

## Current State

| Feature | Backend | Frontend |
|---------|---------|---------|
| List jobs | ✅ GET /api/admin-portal/scheduler/jobs | ✅ Implemented |
| Edit job | ✅ PUT /scheduler/jobs/{id} — **BUT BROKEN** (references `updated_at` column that doesn't exist) | ✅ Edit form exists |
| Run now | ✅ POST /scheduler/jobs/{id}/trigger | ✅ ▶ button |
| Pause/Resume | ✅ PATCH /scheduler/jobs/{id}/toggle | ✅ ⏸/▶ toggle |
| Run history | ✅ GET /scheduler/jobs/{id}/history | ✅ History panel |
| **Create job** | ❌ No POST in admin portal | ❌ No UI |
| **Delete job** | ❌ No DELETE in admin portal | ❌ No UI |

## Bug to Fix

**`server/app/api/admin_portal.py` line 1679:**
```python
text(f"UPDATE scheduled_jobs SET {set_clauses}, updated_at = NOW() WHERE id = :id")
```
The `scheduled_jobs` table has NO `updated_at` column → every Edit save throws a PostgreSQL error.
Fix: remove `, updated_at = NOW()` from the UPDATE statement.

## Task Breakdown

| # | Task | Agent | File(s) | Depends On | Status |
|---|------|-------|---------|-----------|--------|
| 1 | Backend: Fix PUT bug + add POST create + DELETE | Backend | `server/app/api/admin_portal.py` | — | NOT STARTED |
| 2 | Frontend: Add createJob/deleteJob API + UI | Frontend | `portal/src/api/portal.ts`, `portal/src/pages/SchedulerPage.tsx` | Task 1 | NOT STARTED |
| 3 | Deploy & verify | Backend | EC2 | Tasks 1+2 | NOT STARTED |

## Task 1 — Backend (admin_portal.py)

### Fix 1A — Remove broken `updated_at` from PUT endpoint (~line 1679)
Change:
```python
text(f"UPDATE scheduled_jobs SET {set_clauses}, updated_at = NOW() WHERE id = :id")
```
To:
```python
text(f"UPDATE scheduled_jobs SET {set_clauses} WHERE id = :id")
```

### Fix 1B — Add POST `/scheduler/jobs` (create new job)
After the GET `/scheduler/jobs` endpoint, add:
- Method: POST
- Path: `/scheduler/jobs`
- Auth: Requires admin (same pattern as other endpoints in this file)
- Request body fields: `name` (str), `message` (str), `agent` (str), `schedule` (str — cron),
  `workflow_name` (str, optional), `deliver_to` (dict, optional, default `{}`)
- Logic:
  - Validate `agent` is one of: finance, sales, marketing, support, management, hr
  - Validate `schedule` is a valid 5-field cron expression (basic split check)
  - Compute `next_run` using `compute_next_run(schedule)` (already exists in scheduler.py)
  - INSERT into `scheduled_jobs` with a system user_id (use a sentinel UUID or
    look up admin user — check how existing code gets user context)
  - Return the created job dict
- Pattern to follow: look at `/scheduler/jobs` (user-facing) POST endpoint in
  `server/app/webhooks/scheduler.py` for the INSERT logic and next_run computation

### Fix 1C — Add DELETE `/scheduler/jobs/{job_id}`
After the PUT endpoint, add:
- Method: DELETE
- Path: `/scheduler/jobs/{job_id}`
- Auth: Requires admin
- Logic:
  - Check job exists
  - DELETE FROM scheduled_jobs WHERE id = :id
  - Return `{"deleted": True, "job_id": job_id}`

## Task 2 — Frontend (portal files)

### Fix 2A — Add API functions to portal.ts
Add two new functions near the existing scheduler functions:
```typescript
createJob: (data: { name: string; message: string; agent: string; schedule: string; workflow_name?: string }) =>
  apiClient.post('/api/admin-portal/scheduler/jobs', data),

deleteJob: (jobId: string) =>
  apiClient.delete(`/api/admin-portal/scheduler/jobs/${jobId}`),
```

### Fix 2B — Enhance SchedulerPage.tsx
Read the current SchedulerPage.tsx first to understand the existing state/mutations.

**Add "New Job" button** in the page header (top-right, orange, beside the title).

**Add Create Job modal/form** (inline slide-down or modal) with fields:
- Name (text input, required)
- Agent (select: finance / sales / marketing / support / management / hr)
- Message (textarea, required — the natural language task description)
- Schedule (text input for cron expression, required, with helper text "e.g. 0 9 * * 1-5")
- Workflow Name (text input, optional — display label)
- Submit / Cancel buttons
- On success: close form, refetch jobs list, clear form

**Add "Delete" button** per job row (trash icon, red, after the existing action buttons).
On click: show inline confirmation ("Delete this job?  Yes / No") before calling deleteJob mutation.
On success: if deleted job was selected, clear selection; refetch jobs.

**Add createJobMutation** using useMutation → portalApi.createJob()
**Add deleteJobMutation** using useMutation → portalApi.deleteJob()

## Acceptance Criteria
- [ ] Edit/Save a job works (no PostgreSQL error)
- [ ] "New Job" button opens create form
- [ ] Create form validates required fields before submitting
- [ ] Created job appears in list within 60 seconds (Beat polling)
- [ ] Delete button with confirmation removes job from list
- [ ] Deleted job no longer runs (Beat picks up deactivation within 60s)
- [ ] Run Now, Pause/Resume, Run History all still work (no regression)

## Deploy
Backend: SCP admin_portal.py to EC2 + restart mezzofy-api.service
Frontend: npm run build in portal/ + sudo cp -r dist/* /var/www/mission-control/
