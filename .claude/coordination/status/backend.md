# Context Checkpoint: Backend Agent
**Date:** 2026-03-29 14:10 UTC
**Session:** leave-fix-and-leads-detail (all backend tasks in one run)
**Context:** ~40%
**Reason:** All backend tasks complete

## Completed This Session

- ✅ TASK 1 — Fixed `GET /leave/applications` self-service scoping
  → `server/app/api/hr.py` (list_leave_applications)
  → Self-service users (lacking hr_read/hr_leave_manage/hr_reports/management_read) now auto-scoped to own employee record
  → Uses `_has_perm()` helper + `_resolve_employee_by_user()` pattern (same as get_my_leave_balance)
  → Returns `{"applications": [], "count": 0}` gracefully when no employee linked

- ✅ TASK 2 — EC2 investigation complete
  → EC2 already had `_to_date` date fix deployed (commit `2de841f`)
  → Eric's employee record: employee_id=`7f2b48e1-0590-4ca3-bd22-3dea28af6484`, staff_id=`MZ-EMP-002`, user_id linked ✅
  → Leave applications: 0 rows (no applications submitted successfully yet)
  → No `user_id` linkage fix needed — already correct

- ✅ TASK 3 — Added `lead_activities` table to migrate.py
  → `server/scripts/migrate.py` (section "3b. lead_activities", after sales_leads block)
  → CHECK constraint on `type`, INDEX on `(lead_id, created_at DESC)`
  → Migration ran on EC2 successfully

- ✅ TASK 4 — Added CRM lead activities API endpoints to sales_leads.py
  → `server/app/api/sales_leads.py`
  → `GET /sales/leads/{lead_id}/activities` — returns activity log DESC
  → `POST /sales/leads/{lead_id}/activities` — logs manual activity (note/call/meeting/email_sent/follow_up_set)
  → `PATCH /sales/leads/{lead_id}/status` updated: auto-logs `status_changed` activity
  → `PATCH /sales/leads/{lead_id}/assign` updated: auto-logs `assigned` activity with assignee name

- ✅ TASK 5 — Deployed to EC2
  → Committed: `fe9d44a` on `eric-design`, pushed to GitHub
  → `git pull` + `python scripts/migrate.py` on EC2: all successful
  → `mezzofy-api.service`: active (running) with 4 workers

## Files Modified (commit fe9d44a)
- `server/app/api/hr.py` — list_leave_applications: self-service scoping fix
- `server/app/api/sales_leads.py` — activities endpoints + auto-log on status/assign
- `server/scripts/migrate.py` — lead_activities table + index

## Key Facts
- EC2: `ubuntu@3.1.255.48`, service: `mezzofy-api.service`
- Branch: `eric-design`
- Eric's employee: `MZ-EMP-002`, employee_id `7f2b48e1-0590-4ca3-bd22-3dea28af6484`
- lead_activities: UUID PK, CHECK on type, CASCADE delete, idx on (lead_id, created_at DESC)

## Previous Session (2026-03-28)
HR Module v1.52.0 — all backend tasks complete (see git history: cbba7bb, 0d8549e)

## Resume Instructions
All backend tasks for `leave-fix-and-leads-detail-plan.md` are COMPLETE.
Frontend tasks (6-8) are for the Frontend Agent.
If new backend tasks arrive: read plan at `.claude/coordination/plans/`, run /boot-backend.
