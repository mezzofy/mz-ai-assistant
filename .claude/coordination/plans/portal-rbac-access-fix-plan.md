# Plan: Portal RBAC Access Fix
**Workflow:** change-request
**Date:** 2026-04-02
**Created by:** Lead Agent
**Version:** v1.0

---

## Context

The entire portal (`/mission-control/*`) is wrapped in `AdminRoute`, which currently only allows `role === 'admin'`. This blocks all non-admin roles (finance_manager, hr_manager, sales_manager, etc.) from accessing the portal entirely, even though `HRRoute` and `FinanceRoute` guards exist and are ready.

**Required access rules (per user request):**
| Role | Can Access Sections |
|------|-------------------|
| `admin` | Everything (unchanged) |
| `executive` | Finance + Sales + HR sections |
| `finance_manager` | Finance section only |
| `hr_manager` | HR section only |
| `sales_manager` | Sales section only |
| `sales_rep` | Sales section only |

**Assumption:** Core nav items (Dashboard, Tasks, Messages, Scheduler, Agents, Files) remain accessible to all authenticated portal users — these are the AI assistant's core features.

**Users page** (`/mission-control/users`): admin-only, sidebar entry hidden for all other roles.

---

## Task Breakdown

| # | Task | Agent | Scope | Depends On | Est. Sessions | Status |
|---|------|-------|-------|-----------|:---:|--------|
| 1 | Update AdminRoute + Create SalesRoute + Update Sidebar + Update App.tsx | Frontend | `portal/src/` | None | 1 | NOT STARTED |

Single-agent, single-session task (4 file edits, 1 new file).

---

## Files to Modify

### 1. `portal/src/components/AdminRoute.tsx`
**Change:** Replace hard `role !== 'admin'` check with a list of all allowed portal roles.

```
PORTAL_ROLES = [
  'admin', 'executive',
  'finance_manager', 'finance_viewer',
  'hr_manager', 'hr_staff', 'hr_viewer',
  'sales_manager', 'sales_rep',
  'cfo', 'ceo'
]

if (!user?.role || !PORTAL_ROLES.includes(user.role)) → show Access Denied
```

Error message: "You do not have permission to access this portal."

### 2. `portal/src/components/SalesRoute.tsx` *(NEW)*
**Pattern:** Identical to `HRRoute.tsx` and `FinanceRoute.tsx`.

```
SALES_ROLES = ['sales_manager', 'sales_rep', 'executive', 'admin']

Checks: isAuthenticated + role in SALES_ROLES
Error message: "Sales role required to access this section"
```

### 3. `portal/src/components/layout/Sidebar.tsx`
**Current:** Sales section always shown (no role check). Users bottom nav always shown.

**Changes:**
- Add `SALES_ROLES = ['sales_manager', 'sales_rep', 'executive', 'admin']` constant
- Add `showSales` flag: `user?.role ? SALES_ROLES.includes(user.role) : false`
- Wrap Sales section in `{showSales && (...)}` (same pattern as Finance/HR)
- Add `showUsers` flag: `user?.role === 'admin'`
- Wrap BOTTOM_NAV_ITEMS (Users) in `{showUsers && (...)}` to hide from non-admin roles

### 4. `portal/src/App.tsx`
**Change:** Wrap CRM routes with SalesRoute (same pattern as FinanceRoute/HRRoute).

```tsx
import SalesRoute from './components/SalesRoute'

// Wrap:
<Route path="crm" element={<SalesRoute><CRMPage /></SalesRoute>} />
<Route path="crm/leads/:id" element={<SalesRoute><CRMLeadDetailPage /></SalesRoute>} />
```

---

## Parallel Opportunities
None — single agent, sequential file edits.

---

## Quality Gate (Lead Reviews After Task 1)

- [ ] `AdminRoute` allows all 11 PORTAL_ROLES, blocks unknown roles
- [ ] `SalesRoute` created matching HRRoute/FinanceRoute pattern
- [ ] Sidebar `showSales` flag correctly gates Sales section
- [ ] Sidebar `showUsers` flag hides Users nav from non-admin
- [ ] CRM routes wrapped in SalesRoute in App.tsx
- [ ] `finance_manager` → sees Finance section only (not Sales, HR, Users)
- [ ] `hr_manager` → sees HR section only (not Finance, Sales, Users)
- [ ] `sales_manager`/`sales_rep` → sees Sales section only (not Finance, HR, Users)
- [ ] `executive` → sees Finance + Sales + HR sections (not Users)
- [ ] `admin` → sees everything (unchanged)
- [ ] TypeScript: `npx tsc --noEmit` — 0 errors
- [ ] No cross-module imports introduced

---

## Acceptance Criteria

1. A user with `finance_manager` role can log in and access Finance pages
2. A user with `finance_manager` role cannot navigate to `/mission-control/hr/*` or `/mission-control/crm`
3. A user with `hr_manager` role can log in and access HR pages
4. A user with `sales_manager` or `sales_rep` role can log in and access CRM pages
5. A user with `executive` role can access Finance, Sales, and HR sections
6. A user with `admin` role has full access (no regression)
7. The Users page (`/mission-control/users`) is hidden from all non-admin roles
8. TypeScript compiles with 0 errors

---

## Delegation Instructions

**Open a new terminal and run:**
```
/boot-frontend
```

Frontend Agent tasks:
- Read this plan at `.claude/coordination/plans/portal-rbac-access-fix-plan.md`
- Read current file state for all 4 files before editing
- Execute Tasks in order: AdminRoute → SalesRoute (new) → Sidebar → App.tsx
- Run `npx tsc --noEmit` after all changes
- Commit: `feat(portal): RBAC role-based access fix — finance/hr/sales/executive roles`
- Update `.claude/coordination/status/frontend.md` when done

**Do NOT run a dev server or deploy to EC2 — human handles deployment.**
