# Plan: BUG — Leave Summary Dashboard Empty
**Workflow:** bug-fix
**Date:** 2026-03-30
**Created by:** Lead Agent

## Root Cause

`hr_ops.py _get_leave_summary_dashboard()` returns field names that don't match
the TypeScript `HRLeaveDashboard` interface in `portal/src/types/index.ts`.

**Data flow:**
```
Backend returns: {"summary": [...], "year": ..., "count": N}
Frontend looks for: dashboard.employee_summaries   ← undefined → "No data"
```

## Required Fixes (backend only — server/app/tools/database/hr_ops.py)

### Fix 1 — Top-level key rename
Change return value key `"summary"` → `"employee_summaries"`

### Fix 2 — Leave balance sub-field renames
Inside each employee's `leave_balances` list, rename:
- `"leave_type"` → `"leave_type_name"`
- `"code"` → `"leave_type_code"`
- `"entitled"` → `"entitled_days"`
- `"taken"` → `"taken_days"`
- `"pending"` → `"pending_days"`
- `"remaining"` → `"remaining_days"`

### Fix 3 — Add pending_applications per employee
Frontend expects `emp.pending_applications` (integer).
Add a subquery or second query to count `hr_leave_applications WHERE status='pending'`
grouped by employee_id. Join it into the employee grouping loop.

### Fix 4 — Add stat card aggregates
Frontend expects 4 top-level fields on the dashboard object:
- `total_active_employees` — COUNT hr_employees WHERE status='active' (+ same dept/country filters)
- `on_leave_today` — COUNT employees on approved leave where today BETWEEN start_date AND end_date
- `pending_approvals` — COUNT hr_leave_applications WHERE status='pending'
- `leaves_this_month` — COUNT approved leaves in current month (by start_date)

## Scope

| File | Change |
|------|--------|
| `server/app/tools/database/hr_ops.py` | Fix `_get_leave_summary_dashboard` method (lines 1225–1287) |

**No frontend changes needed.** TypeScript types and UI code are correct.

## Task

| # | Task | Agent | Scope | Status |
|---|------|-------|-------|--------|
| 1 | Fix `_get_leave_summary_dashboard` in hr_ops.py | Backend | server/app/tools/database/hr_ops.py | NOT STARTED |
| 2 | Deploy to EC2 | Backend | EC2 | NOT STARTED |

## Acceptance Criteria
- [ ] Leave Summary table shows rows for all active employees with leave balances
- [ ] Stat cards show real numbers (total employees, on leave today, pending, this month)
- [ ] Annual and Sick columns show `taken / remaining` values
- [ ] Pending column shows correct count per employee
- [ ] No regression on Pending Approvals tab
