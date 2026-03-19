# Plan: Mission Control Portal v1.39.0 — Leads + Files UX
**Workflow:** change-request
**Date:** 2026-03-19
**Created by:** Lead Agent
**Branch:** eric-design

---

## Context

Follow-up to v1.38.0. Two items:
1. CRM page: rename to "Leads" + fix persistent 500 on leads listing
2. Files page: add search, proper table display, uppercase folder names

---

## Root Cause Analysis

### CRM 500 — Still Failing?
The SQL fix (`sl.created_at AS updated_at`, `NULL::text AS source_ref`) was applied to local code in the v1.38.0 session but **has not been committed or deployed to EC2 yet**. The local fix is correct. Deployment is required.

### CRM pipeline endpoint — Safe
`/crm/pipeline` only accesses `status` and `COUNT(*)` — no risk of 500 there.

---

## Task Breakdown

| # | Item | Type | File(s) | Status |
|---|------|------|---------|--------|
| 1a | Rename "CRM" → "Leads" in sidebar | Frontend | `Sidebar.tsx` | NOT STARTED |
| 1a | Update page title "CRM" → "Leads" | Frontend | `CRMPage.tsx` | NOT STARTED |
| 1b | Deploy backend SQL fix to EC2 | Deploy | `admin_portal.py` | READY (code done) |
| 2a | Add search bar to Files page | Frontend | `FilesPage.tsx` | NOT STARTED |
| 2b | Flat table display with thead/headers | Frontend | `FilesPage.tsx` | NOT STARTED |
| 2c | Uppercase folder names | Frontend | `FilesPage.tsx` | NOT STARTED |

---

## Implementation Details

### Item 1a — Rename CRM → Leads

**`portal/src/components/layout/Sidebar.tsx`**
- Change `label: 'CRM'` → `label: 'Leads'`

**`portal/src/pages/CRMPage.tsx`**
- Find all visible "CRM" text in JSX (page title, headings) and change to "Leads"
- Example: `<h1>CRM</h1>` → `<h1>Leads</h1>`

---

### Item 2 — Files Page Redesign

**Current state:** Accordion folders (click to expand) → embedded `<tbody>` rows, no `<thead>`. No search.

**Target state:**
1. **Search bar** at top — filters files across ALL folders by filename (case-insensitive substring match on `f.filename`)
2. **Flat table** with proper column headers: Name | Folder | Size | Date | Actions
3. **Uppercase folder label** — `group.scope` and `group.department` displayed as UPPERCASE in the Folder column

**Suggested implementation approach for Frontend Agent:**

```
State:
  - searchQuery: string (empty = show all)

Derived data:
  - allFiles = folders.flatMap(g => g.files.map(f => ({ ...f, folder: folderLabel(g) })))
  - displayed = searchQuery
      ? allFiles.filter(f => f.filename.toLowerCase().includes(searchQuery.toLowerCase()))
      : allFiles

Folder label for column (UPPERCASE):
  [scope, department].filter(Boolean).join(' / ').toUpperCase()
  e.g. "SHARED / MANAGEMENT", "COMPANY"

Table structure:
  <table>
    <thead>
      <tr>
        <th>Name</th>
        <th>Folder</th>
        <th>Size</th>
        <th>Date</th>
        <th>Actions</th>
      </tr>
    </thead>
    <tbody>
      {displayed.map(f => <tr>...columns...</tr>)}
    </tbody>
  </table>

Search bar:
  - Controlled input, no submit required (filter on every keystroke via useState)
  - Placeholder: "Search files..."
  - Place in the header row next to "+ Upload File" button
```

Keep the Upload and Delete modals — only change the folder tree accordion → flat table.

---

## Deployment Steps (After Frontend Code Done)

```bash
# 1. Commit all changes locally
git add portal/src/components/layout/Sidebar.tsx
git add portal/src/pages/CRMPage.tsx
git add portal/src/pages/FilesPage.tsx
# (admin_portal.py was already modified in v1.38.0 session — stage it too)
git add server/app/api/admin_portal.py
git add portal/src/api/portal.ts
git add portal/src/components/AgentOffice.tsx
git add portal/src/pages/LoginPage.tsx
git add portal/src/pages/OtpPage.tsx
git commit -m "feat(portal): v1.39.0 — Leads rename + Files table + search"

# 2. Deploy to EC2
# (git push → git pull on EC2 → restart service → rebuild portal)
```

---

## Files Modified (This Session)

### Frontend (Frontend Agent)
- `portal/src/components/layout/Sidebar.tsx` — label 'CRM' → 'Leads'
- `portal/src/pages/CRMPage.tsx` — title text 'CRM' → 'Leads'
- `portal/src/pages/FilesPage.tsx` — search + flat table + uppercase folder names

### Backend (Already Done — Just Deploy)
- `server/app/api/admin_portal.py` — CRM SQL fix already applied in v1.38.0

---

## Verification Checklist

1. **Sidebar** — Menu item reads "Leads" (not "CRM")
2. **Leads page title** — Page heading says "Leads"
3. **Leads 500** — After EC2 deploy, Leads table loads without error
4. **Files search** — Typing in search box filters file list instantly
5. **Files table** — All files shown in flat table with Name/Folder/Size/Date/Actions columns
6. **Files folder name** — Folder column shows "SHARED / MANAGEMENT", "COMPANY", etc. in UPPERCASE
7. **Files upload** — Upload modal still works (no regression)
8. **Files delete** — Delete modal still works (no regression)

---

## Delegation

**All 3 frontend file changes** → Frontend Agent (single session, ~20% context).

Backend fix is already in code. Lead needs to coordinate deployment after frontend is done.
