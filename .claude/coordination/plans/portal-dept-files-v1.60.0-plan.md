# Plan: Portal Department Files Pages (v1.60.0)
**Workflow:** change-request
**Date:** 2026-04-02
**Created by:** Lead Agent

---

## Context

Following the RBAC access fix, department roles (finance, hr, sales) can now enter the portal but currently see the full Core nav (Dashboard, Tasks, Messages, Scheduler, Agents, Files). These roles should not have access to the AI assistant core tools — only their department's own section.

Additionally, each department needs its own "Files" menu item that shows:
- **Company files** (company scope — all authenticated users can read, only management can write)
- **Department files** (department scope — filtered to that dept)

This mirrors the Mobile app's non-management user file view: 2 sections (company + department), read-only for non-management.

---

## Access Rules (per existing backend `/files/` API)

| Scope | Who Can Read | Who Can Write/Delete |
|-------|-------------|---------------------|
| company | All authenticated users | Management only |
| department | Same department + Management | Same department + Management |
| personal | Owner only | Owner only |

Department files pages show only: **company** + **department** sections (no personal).

---

## Task Breakdown

| # | Task | Agent | Scope | Est. Sessions | Status |
|---|------|-------|-------|:---:|--------|
| 1 | Sidebar + API + DeptFilesPage + Routes | Frontend | `portal/src/` | 1 | NOT STARTED |

---

## Files to Modify / Create

### 1. `portal/src/components/layout/Sidebar.tsx`

**A — Restrict Core nav to admin + executive only**

Add `showCore` flag after existing flags:
```typescript
const CORE_ROLES = ['admin', 'executive']
const showCore = user?.role ? CORE_ROLES.includes(user.role) : false
```

Wrap the existing `NAV_ITEMS.map(...)` block in `{showCore && (...)}`.
Also wrap the `useEffect` badge-fetch + interval in `if (showCore)` guard to avoid unnecessary polling for dept users.

**B — Add Files to each department nav array**

Add `FolderOpen` to the lucide-react import if not already there (it is — check line 4 of current file).

```typescript
// FINANCE_NAV_ITEMS — append at end:
{ path: '/mission-control/finance/files', label: 'Files', icon: FolderOpen }

// HR_NAV_ITEMS — append at end:
{ path: '/mission-control/hr/files', label: 'Files', icon: FolderOpen }

// SALES_NAV_ITEMS — append at end:
{ path: '/mission-control/sales/files', label: 'Files', icon: FolderOpen }
```

---

### 2. `portal/src/api/portal.ts`

Add two new methods after the existing `downloadFile` method (or after Files section):

```typescript
// Dept-scoped file listing (uses public /files/ endpoint, not admin-portal)
getDeptFiles: (scope: 'company' | 'department', dept?: string) =>
  client.get('/files/', { params: { scope, ...(dept ? { dept } : {}) } }),

// Download via public endpoint
downloadDeptFile: (fileId: string, filename: string) =>
  client.get(`/files/${fileId}`, { responseType: 'blob' }).then((res) => {
    const url = window.URL.createObjectURL(new Blob([res.data]))
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.click()
    window.URL.revokeObjectURL(url)
  }),
```

---

### 3. `portal/src/pages/DeptFilesPage.tsx` *(NEW)*

Reusable component that accepts `department` and `sectionTitle` props.

**Props:**
```typescript
interface Props {
  department: string   // 'finance' | 'hr' | 'sales'
  sectionTitle: string // 'Finance' | 'HR' | 'Sales'
}
```

**Behavior:**
- On mount: fetch company files + dept files in parallel via two calls to `portalApi.getDeptFiles()`
  - Call 1: `getDeptFiles('company')` → company section
  - Call 2: `getDeptFiles('department', department)` → department section
- Use `useState` + `useEffect` (not react-query — consistent with other finance pages)
- Show two sections with section headers:
  - `🏢 Company Files` — files from company scope
  - `📁 {sectionTitle} Files` — files from dept scope
- Per file row: FileTypeAvatar + filename + size + date + Download button
- Loading state: spinner or "Loading files..."
- Empty state per section: "No files found"
- Error state: "Failed to load files"
- Download: calls `portalApi.downloadDeptFile(file.id, file.filename)`
- **Read-only** — no upload, delete, or rename actions
- Reuse `FileTypeAvatar` and `formatBytes` helpers (copy from FilesPage.tsx — single file, no import)

**Visual style:** Match existing portal dark theme (`#0A0E1A` bg, `#111827` card bg, `#f97316` orange accents, gray text). Table layout matching FilesPage.tsx.

---

### 4. `portal/src/App.tsx`

Add imports and 3 new routes:

```typescript
import DeptFilesPage from './pages/DeptFilesPage'
```

**Finance files route** (flat, same pattern as other finance routes):
```tsx
<Route path="finance/files" element={<FinanceRoute><DeptFilesPage department="finance" sectionTitle="Finance" /></FinanceRoute>} />
```

**HR files route** (nested under HRRoute Outlet — add as child of the hr route):
```tsx
// Inside <Route path="hr" element={<HRRoute><Outlet /></HRRoute>}>
<Route path="files" element={<DeptFilesPage department="hr" sectionTitle="HR" />} />
```

**Sales files route** (new path, not under crm):
```tsx
<Route path="sales/files" element={<SalesRoute><DeptFilesPage department="sales" sectionTitle="Sales" /></SalesRoute>} />
```

---

## Quality Gate (Lead Reviews After Task 1)

- [ ] `showCore` flag added — Core nav hidden for finance/hr/sales roles
- [ ] `admin` and `executive` still see full Core nav
- [ ] Finance nav array has Files item → `/mission-control/finance/files`
- [ ] HR nav array has Files item → `/mission-control/hr/files`
- [ ] Sales nav array has Files item → `/mission-control/sales/files`
- [ ] `getDeptFiles` API method added in portal.ts
- [ ] `downloadDeptFile` API method added in portal.ts
- [ ] `DeptFilesPage.tsx` created with company + dept two-section layout
- [ ] Company section and dept section both load correctly
- [ ] Download works
- [ ] Read-only (no upload/delete/rename in DeptFilesPage)
- [ ] 3 new routes registered in App.tsx (finance/files, hr/files, sales/files)
- [ ] TypeScript: `npx tsc --noEmit` — 0 errors
- [ ] Commit with message: `feat(portal): department files pages + hide core nav from dept roles (v1.60.0)`

---

## Acceptance Criteria

1. `finance_manager` logs in → sees Finance section only (no Core nav). Finance section has Files link.
2. Clicking Files → shows Company Files section + Finance Files section
3. `hr_manager` logs in → sees HR section only (no Core nav). HR section has Files link.
4. `sales_rep` logs in → sees Sales section only (no Core nav). Sales section has Files link.
5. `executive` logs in → sees Core nav + Finance + Sales + HR sections. Each dept section has Files link.
6. `admin` logs in → sees Core nav + all sections (no regression).
7. Files pages are read-only (no upload/delete/rename controls visible).
8. TypeScript 0 errors.

---

## Delegation Instructions

**Frontend Agent tasks:**
1. Read current Sidebar.tsx, portal.ts, App.tsx before editing
2. Execute changes in order: Sidebar → portal.ts → DeptFilesPage (new) → App.tsx
3. Run `npx tsc --noEmit`
4. Commit: `feat(portal): department files pages + hide core nav from dept roles (v1.60.0)`
5. Update `.claude/coordination/status/frontend.md`
