# Plan: HR Module v1.52.0 — Full HR Sub-Module

**Workflow:** new-module (additive extension)
**Date:** 2026-03-28
**Created by:** Lead Agent
**Source:** `docs/HR_MODULE_CLAUDE_CODE_PROMPT.md`

---

## Context

Extends the existing system with a full HR sub-module:
- Employee records + leave management (DB + tools + API)
- Portal frontend section (sidebar + 5 pages)
- New HR Agent workflows for leave operations via chat

**Additive-only. Do not restart services. Do not rewrite existing code.**

---

## Task Breakdown

| # | Phase | Task | Agent | Depends On | Status |
|---|-------|------|-------|-----------|--------|
| 1 | 1–3, 10 | DB migration + seed + RBAC + config | Backend | — | DONE |
| 2 | 4 | `hr_ops.py` tools (15 tools) | Backend | Task 1 | DONE |
| 3 | 5–6 | `/hr` API router + user-employee linking | Backend | Task 2 | DONE |
| 4 | 7 | Extend HR Agent with leave workflows | Backend | Task 3 | DONE |
| 5 | 11 | Tests (`tests/test_hr_module.py`) | Backend | Task 3+4 | NOT STARTED |
| 6 | 8–9 | Portal: sidebar + 5 pages | Frontend | Task 3 | NOT STARTED |
| 7 | 12 | Docs update | Docs | Task 5+6 | NOT STARTED |

**Parallel after Tasks 3+4:** Backend runs tests (Task 5) while Frontend builds portal (Task 6).

---

## Backend Agent Tasks (Sessions 1–5)

### Session 1 — DB Migration + Seed + RBAC + Config

Files to modify:
- `server/scripts/migrate.py` → append 5 HR tables + indexes
- `server/scripts/seed_hr.py` → NEW: 8 default leave types
- `server/config/roles.yaml` → add `hr_staff`; extend `hr_manager`; add `hr_self_service` to all non-HR roles
- `server/app/core/rbac.py` → add new HR roles/permissions to VALID_ROLES/permissions
- `server/config/config.example.yaml` → add `hr:` section

### Session 2 — hr_ops.py

File to create: `server/app/tools/database/hr_ops.py`
Pattern: follow `crm_ops.py` exactly (class HROps(BaseTool), get_tools(), async handlers, lazy imports)
15 tools: get_employee, list_employees, create_employee, update_employee, set_employee_status,
          get_employee_profile, apply_leave, get_leave_applications, get_leave_balance,
          update_leave_status, get_leave_summary_dashboard, get_pending_approvals, list_leave_types

### Session 3 — /hr API Router + User Linking

Files to create/modify:
- `server/app/api/hr.py` → NEW: 17 endpoints (follow sales_leads.py pattern)
- `server/app/main.py` → add `app.include_router(hr_api.router, prefix="/hr")`
- `server/app/api/admin.py` → additive: optional `create_employee` flag on POST /admin/users
- auth/me endpoint → additive: add `employee_id`, `staff_id`, `manager_employee_id`

### Session 4 — Extend HR Agent

File: `server/app/agents/hr_agent.py` — READ FULLY FIRST, then extend only
Add 5 workflows + expand can_handle() keywords
Use lazy inline imports for HROps

### Session 5 — Tests

File to create: `server/tests/test_hr_module.py`
24 tests (14 tools + 5 API + 5 agent routing)
Run: `pytest tests/test_hr_module.py -v`

---

## Frontend Agent Tasks (Sessions 1–2)

### Session 1 — Sidebar + Guard + Routes + API

- `portal/src/components/layout/Sidebar.tsx` → add HR section (Users2 + CalendarRange icons)
- `portal/src/components/HRRoute.tsx` → NEW: permission guard for hr roles
- `portal/src/App.tsx` → add /hr/* routes wrapped in HRRoute
- `portal/src/api/portal.ts` → add 13 hrApi methods
- `portal/src/types/index.ts` → add HR TypeScript interfaces

### Session 2 — 5 Page Components

- `portal/src/pages/hr/HREmployeesPage.tsx`
- `portal/src/pages/hr/HREmployeeProfilePage.tsx` (3 tabs)
- `portal/src/pages/hr/HREmployeeFormPage.tsx`
- `portal/src/pages/hr/HRLeaveApplicationModal.tsx`
- `portal/src/pages/hr/HRLeaveManagementPage.tsx`

Dark theme: bg #0A0E1A, cards #111827, borders #1E2A3A, accent #f97316

---

## Docs Agent Tasks

Append only to:
- `server/docs/MEMORY.md` → add 5 HR tables
- `server/docs/AGENTS.md` → add 5 HR agent workflows
- `server/docs/TOOLS.md` → add hr_ops.py
- `server/docs/SECURITY.md` → add HR permissions

---

## Quality Gates

| Gate | Condition |
|------|-----------|
| 1 | `psql -c "\dt hr_*"` shows 5 tables |
| 2 | hr_ops.py imports without error |
| 3 | `/hr/employees` returns `{"success": true, "data": [...]}` |
| 4 | `pytest tests/test_hr_module.py -v` → 24 passed |
| 5 | Portal sidebar shows HR section; all 5 pages render |

---

## Hard Rules

- ❌ DO NOT restart FastAPI, Celery, or Celery Beat
- ❌ DO NOT drop or alter existing tables
- ❌ DO NOT rewrite hr_agent.py — extend only
- ❌ DO NOT remove any existing role or permission
- ✅ All new tables use IF NOT EXISTS
- ✅ All mutations logged to hr_audit_log
- ✅ All tools enforce user_id scoping
