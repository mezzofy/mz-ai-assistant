# Plan: Leave Records Fix + Leads Detail Page
**Workflow:** bug-fix + change-request
**Date:** 2026-03-29
**Created by:** Lead Agent

---

## Summary

Two tasks:
1. **BUG — Leave records not visible** after successful submission (mobile + portal)
2. **FEATURE — Leads Detail Page** with communication log timeline (portal only)

---

## Task 1: Leave Records Bug Fix

### Root Cause Diagnosis

After tracing the full code path:

**A. `GET /leave/applications` has no self-service scoping**
- `list_leave_applications` endpoint uses `Depends(get_current_user)` (no permission guard)
- Calls `_get_leave_applications(requesting_user_id=user_id, filters={})` with empty filters
- `_get_leave_applications` IGNORES `requesting_user_id` — returns ALL 200 applications from all employees
- Fix: when `employee_id` filter not explicitly provided AND user lacks `hr_read`/`hr_leave_manage`, auto-resolve current user → employee and scope to that employee only

**B. Portal has no self-service leave view**
- Portal `HRLeaveManagementPage.tsx` has two tabs:
  - "Leave Summary" — requires `hr_reports`/`management_read` permission — ALL employees dashboard
  - "Pending Approvals" — only shows leaves for DIRECT REPORTS of the logged-in manager
- There is NO tab/view where an employee can see THEIR OWN leave applications
- `APPROVER_ROLES = ['hr_staff', 'hr_manager', 'executive', 'admin']` — `management` role is EXCLUDED, so the Pending Approvals tab is hidden entirely for Eric

**C. Mobile v1.54.0 APK newly built — may not be installed yet**
- The LEAVE HISTORY card was added in the current session (v1.54.0)
- Once Eric installs v1.54.0 + the backend fix is deployed, the mobile will show correctly

**D. EC2 deployment of `_apply_leave` date fix**
- The `_apply_leave` date conversion fix (`_to_date()`) was committed but EC2 deployment was listed as pending
- Since user reports SUCCESS on submission: EC2 may already have this fix
- Backend Agent must verify and deploy if not already done

### Backend Fixes (hr.py + EC2)

**Fix 1 — Self-service scoping in `GET /leave/applications`**

In `hr.py list_leave_applications()`:
```python
# After resolving filters, if no employee_id filter AND user is self-service only:
user_permissions = current_user.get("permissions", [])
is_hr_manager = any(p in user_permissions for p in ("hr_read", "hr_leave_manage", "hr_reports", "management_read"))
if not employee_id and not is_hr_manager:
    # Auto-scope: resolve this user's own employee record
    emp_result = await hr._resolve_employee_by_user(user_id)
    if emp_result.get("success"):
        filters["employee_id"] = emp_result["output"]["id"]
    else:
        return _ok({"applications": [], "count": 0})  # No employee linked = no records
```

**Fix 2 — Investigate Eric's DB records**

On EC2, run:
```sql
SELECT u.id, u.email, e.id AS employee_id, e.staff_id, e.full_name, e.user_id AS emp_user_id
FROM users u
LEFT JOIN hr_employees e ON e.user_id = u.id
WHERE u.email = 'eric@mezzofy.com';
```

Then check leave applications:
```sql
SELECT la.id, la.status, la.start_date, la.end_date, la.total_days, la.created_at
FROM hr_leave_applications la
WHERE la.employee_id = '<eric_employee_id>';
```

This confirms whether records exist. If none exist → EC2 date fix not deployed; deploy now.

**Fix 3 — Deploy EC2 if not already done**
```bash
ssh ubuntu@3.1.255.48
cd /home/ubuntu/mz-ai-assistant/server
git pull origin eric-design
sudo systemctl restart mezzofy-api.service
```

### Portal Fix (HRLeaveManagementPage.tsx)

**Add "My Leaves" tab** — visible to ALL authenticated users with `hr_self_service` permission.
- Calls `GET /api/admin-portal/hr/leave/applications` (no filters — backend now auto-scopes)
- Shows current user's own leave applications in a table: type, dates, days, status, reason, applied date
- Include "Apply Leave" button (links to or embeds the apply form)
- Add `management` to `APPROVER_ROLES` so management role can also see the Pending Approvals tab

---

## Task 2: Leads Detail Page + Communication Log

### What Exists
- `sales_leads` table: id, company_name, contact_name, contact_email, contact_phone, industry, location, source, status, assigned_to, notes, created_at, last_contacted, follow_up_date, source_ref, updated_at
- `CRMPage.tsx`: list view with pipeline summary, create/edit modal (inline)
- No detail page, no activity/communication log table

### What Needs to Be Built

**Backend:**

1. New DB table `lead_activities` (add to migrate.py + run on EC2):
```sql
CREATE TABLE IF NOT EXISTS lead_activities (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id     UUID NOT NULL REFERENCES sales_leads(id) ON DELETE CASCADE,
    actor_id    UUID REFERENCES users(id),
    actor_name  TEXT,
    type        TEXT NOT NULL,  -- 'created', 'status_changed', 'assigned', 'note', 'email_sent', 'call', 'meeting', 'follow_up_set'
    title       TEXT NOT NULL,
    body        TEXT,
    meta        JSONB,          -- flexible: {old_status, new_status, assignee_name, etc.}
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_lead_activities_lead ON lead_activities(lead_id, created_at DESC);
```

2. Auto-log activities on lead state changes (in existing `update_lead` handler):
   - Status changes → log `status_changed` activity
   - Assignment changes → log `assigned` activity

3. New API endpoints in `server/app/api/crm.py` (or wherever CRM routes live):
   - `GET /api/admin-portal/crm/leads/{id}` — full lead detail
   - `GET /api/admin-portal/crm/leads/{id}/activities` — activity log (DESC order)
   - `POST /api/admin-portal/crm/leads/{id}/activities` — add manual activity (note, call log, etc.)

**Portal:**

4. New file: `portal/src/pages/CRMLeadDetailPage.tsx`
   - Layout similar to `HREmployeeProfilePage.tsx` (header + back nav + sections)
   - Left/top: Lead info card (all fields, inline editable status + assignee)
   - Bottom/right: Communication Log timeline — newest first, icon per activity type
   - Activity types + icons:
     - `created` → sparkles (orange)
     - `status_changed` → arrow-right-circle
     - `assigned` → person-circle
     - `email_sent` → mail
     - `call` → phone-portrait
     - `meeting` → calendar
     - `follow_up_set` → alarm
     - `note` → document-text
   - "Add Activity" quick actions: Note / Call / Meeting / Email
   - Auto-refresh activities after adding

5. Wire `CRMPage.tsx` — clicking a lead row navigates to `CRMLeadDetailPage`

6. Add to `portal/src/api/portal.ts`:
   - `getCrmLeadDetail: (id: string)`
   - `getCrmLeadActivities: (id: string)`
   - `addLeadActivity: (id: string, data: {...})`

7. Add route in portal router for `/mission-control/crm/leads/:id`

---

## Task Breakdown

| # | Task | Agent | Scope | Depends On | Sessions |
|---|------|-------|-------|-----------|----------|
| 1 | Fix GET /leave/applications scoping | Backend | server/app/api/hr.py | none | 1 |
| 2 | Investigate + deploy EC2 (verify Eric's records) | Backend | EC2 | none | 1 (same as #1) |
| 3 | Add lead_activities table to migrate.py + run on EC2 | Backend | server/scripts/migrate.py | none | 1 (same as #1) |
| 4 | Add lead detail + activities API endpoints | Backend | server/app/api/crm.py | #3 | 1 (same as #1) |
| 5 | Auto-log activities on lead status/assignment changes | Backend | server/app/api/crm.py or crm_ops.py | #3 | 1 (same as #1) |
| 6 | Portal: "My Leaves" tab in HRLeaveManagementPage | Frontend | portal/src/pages/hr/ | #1,#2 | 1 |
| 7 | Portal: CRMLeadDetailPage with comm log | Frontend | portal/src/pages/ | #3,#4,#5 | 1 |
| 8 | Portal: Wire CRMPage rows to detail page + add route | Frontend | portal/src/pages/ | #7 | 1 (same as #7) |

## Parallel Opportunities
- Tasks 1–5 (Backend) can run in a single Backend session
- Tasks 6–8 (Frontend) can run after Backend is done

## Files to Modify

| File | Change |
|------|--------|
| `server/app/api/hr.py` | Fix GET /leave/applications self-service scoping + add management to APPROVER hint |
| `server/scripts/migrate.py` | Add lead_activities table definition |
| `server/app/api/crm.py` | Add /leads/{id}, /leads/{id}/activities endpoints + auto-log on update |
| `portal/src/pages/hr/HRLeaveManagementPage.tsx` | Add "My Leaves" tab + add management to APPROVER_ROLES |
| `portal/src/pages/CRMLeadDetailPage.tsx` | NEW — Lead detail + comm log UI |
| `portal/src/pages/CRMPage.tsx` | Add click-to-detail navigation on rows |
| `portal/src/api/portal.ts` | Add 3 new CRM API methods |
| `portal/src/App.tsx` or router file | Add /mission-control/crm/leads/:id route |

## Acceptance Criteria

**Leave fix:**
- [ ] Eric's employee record confirmed linked in DB
- [ ] Eric's leave applications visible in mobile Profile LEAVE HISTORY (after installing v1.54.0)
- [ ] Portal "My Leaves" tab shows current user's own applications
- [ ] `management` role can see portal "Pending Approvals" tab
- [ ] Self-service users cannot see other employees' applications

**Leads detail:**
- [ ] Clicking a lead row in CRMPage opens CRMLeadDetailPage
- [ ] Detail page shows all lead fields with inline-editable status and assignee
- [ ] Communication log shows: created, all status changes, all assignment changes
- [ ] "Add Activity" lets user log a note, call, meeting, or email manually
- [ ] All activity types shown with distinct icons on the timeline
