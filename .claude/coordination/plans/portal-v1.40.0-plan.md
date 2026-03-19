# Plan: Mission Control Portal v1.40.0 — Leads Fix + Files Download + UI Standards
**Workflow:** bug-fix + change-request
**Date:** 2026-03-19
**Created by:** Lead Agent
**Branch:** eric-design

---

## Context

Three items from this session:
1. **CRM/Leads 500** — `GET /api/admin-portal/crm/leads` returns 500. Backend SQL fix already in committed code locally but NOT deployed to EC2 yet. EC2 has old code that selects `updated_at`/`source_ref` columns that don't exist in `sales_leads` table.
2. **Files Download Broken** — `download_url = /files/{id}` is the mobile API endpoint requiring JWT Bearer auth. Browser `<a href>` navigation doesn't send Authorization headers → 401. No download endpoint exists under `/api/admin-portal/`.
3. **UI Standardisation** — Leads, Files, Tasks action buttons are inconsistent (text labels, emoji). Standardise to match Users table structure but with SVG icon buttons (better than emoji).

---

## Root Cause Analysis

### Issue 1: Leads 500
- EC2 runs old `admin_portal.py` that did `SELECT ... updated_at, source_ref FROM sales_leads`
- `sales_leads` table does NOT have those columns
- Fix is already in committed local code: `sl.created_at AS updated_at`, `NULL::text AS source_ref`
- **Only action required: deploy to EC2**

### Issue 2: Files Download
- `download_url = /files/{r.id}` routes to mobile file API (`files.py`)
- Mobile API uses `Depends(get_current_user)` — requires JWT in Authorization header
- Browser `<a href="/files/xxx" target="_blank">` makes unauthenticated GET → 401
- Fix: Add `GET /api/admin-portal/files/{id}/download` under admin_portal router (uses `AdminUser`)
- Frontend: Replace `<a href>` with programmatic blob download via axios

### Issue 3: UI Standardisation
- **Reference Standard (UsersPage.tsx):**
  - Container: `rounded-xl border`, bg `#111827`, borderColor `#1E2A3A`
  - Table: `w-full text-xs`
  - THead: `border-b text-left`, color `#6B7280`, borderColor `#1E2A3A`
  - TH: first col `px-4 py-3`, rest `py-3`, last `py-3 pr-4`
  - Row: `border-t`, borderColor `#1E2A3A`
  - TD: first col `px-4 py-2.5`, rest `py-2.5`, last `py-2.5 pr-4`
  - Current actions: emoji `✏` (orange `#f97316`) and `🗑` (red `#EF4444`) — to be upgraded
- **Target improved icons:** Inline SVG (14×14), consistent hover states
- Pages to update: **Users, Leads, Files, Tasks**

---

## Task Breakdown

| # | Task | Agent | File(s) | Depends On | Status |
|---|------|-------|---------|-----------|--------|
| 1 | Add `/files/{id}/download` endpoint | Backend | `admin_portal.py` | — | NOT STARTED |
| 2 | Add `downloadFile(id)` to portal API | Frontend | `portal.ts` | Task 1 | NOT STARTED |
| 3 | Fix download in FilesPage + SVG icons | Frontend | `FilesPage.tsx` | Task 2 | NOT STARTED |
| 4 | SVG icons in UsersPage | Frontend | `UsersPage.tsx` | — | NOT STARTED |
| 5 | SVG icon for Kill in TasksPage | Frontend | `TasksPage.tsx` | — | NOT STARTED |
| 6 | Verify Leads table (CRMPage) | Frontend | `CRMPage.tsx` | — | NOT STARTED |
| 7 | Deploy to EC2 | Deploy | — | 1–6 | NOT STARTED |

**Parallel:** Tasks 1 + 4 + 5 + 6 can start immediately. Task 2 depends on Task 1 completing. Task 3 depends on Task 2.

---

## Backend Implementation Details (Task 1)

**File:** `server/app/api/admin_portal.py`

Add this endpoint **after** the `folder-tree` endpoint (around line 896):

```python
@router.get("/files/{file_id}/download")
async def download_file(
    file_id: str,
    current_user: dict = AdminUser,
    db: AsyncSession = Depends(get_db),
):
    """Download a file by artifact ID — admin portal auth."""
    from sqlalchemy import text as sql_text
    from fastapi.responses import FileResponse
    from pathlib import Path as FsPath
    import os

    row = await db.execute(
        sql_text("SELECT filename, file_path, file_type FROM artifacts WHERE id = :id"),
        {"id": file_id},
    )
    artifact = row.fetchone()
    if artifact is None or not artifact.file_path:
        from fastapi import HTTPException, status as http_status
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="File not found")

    file_path = artifact.file_path
    if not os.path.exists(file_path):
        from fastapi import HTTPException, status as http_status
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="File removed from storage")

    # Basic path traversal guard
    from app.context.artifact_manager import get_artifacts_dir
    resolved = FsPath(file_path).resolve()
    artifact_root = get_artifacts_dir().resolve()
    if not str(resolved).startswith(str(artifact_root)):
        from fastapi import HTTPException, status as http_status
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="File not found")

    # Map file_type to MIME (reuse same logic as files.py)
    mime_map = {
        "pdf": "application/pdf",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "xls": "application/vnd.ms-excel",
        "csv": "text/csv",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "txt": "text/plain",
        "md": "text/markdown",
        "json": "application/json",
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "mp4": "video/mp4",
        "mp3": "audio/mpeg",
    }
    mime = mime_map.get((artifact.file_type or "").lower(), "application/octet-stream")

    return FileResponse(
        path=file_path,
        filename=artifact.filename,
        media_type=mime,
    )
```

**Note:** Route `"/files/{file_id}/download"` must be placed BEFORE `"/files/{file_id}"` (if any catch-all routes exist). Since the folder-tree GET is `/files/folder-tree` and currently there's no `/files/{id}` in admin_portal.py, placing it after the folder-tree endpoint is safe.

---

## Frontend Implementation Details (Tasks 2–6)

### Task 2: portal.ts — Add `downloadFile`

```typescript
downloadFile: async (id: string, filename: string): Promise<void> => {
  const response = await client.get(`/api/admin-portal/files/${id}/download`, {
    responseType: 'blob',
  })
  const url = URL.createObjectURL(response.data)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
},
```

### Task 3: FilesPage.tsx — Programmatic Download + SVG Icons

Replace the `<a href={f.download_url}>Download</a>` with:
```tsx
<button
  onClick={() => portalApi.downloadFile(f.id, f.filename)}
  title="Download"
  className="p-1.5 rounded transition-colors hover:bg-orange-500/10"
  style={{ color: '#f97316' }}
>
  {/* Download SVG icon */}
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
    <polyline points="7 10 12 15 17 10"/>
    <line x1="12" y1="15" x2="12" y2="3"/>
  </svg>
</button>
```

Replace Rename text button with pencil SVG icon:
```tsx
<button
  onClick={() => handleRename(f)}
  title="Rename"
  className="p-1.5 rounded transition-colors hover:bg-blue-500/10"
  style={{ color: '#4DA6FF' }}
>
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
    <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
  </svg>
</button>
```

Replace Delete text button with trash SVG icon:
```tsx
<button
  onClick={() => setConfirmDelete(f)}
  title="Delete"
  className="p-1.5 rounded transition-colors hover:bg-red-500/10"
  style={{ color: '#EF4444' }}
>
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="3 6 5 6 21 6"/>
    <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>
    <path d="M10 11v6M14 11v6"/>
    <path d="M9 6V4h6v2"/>
  </svg>
</button>
```

The `justify-end` div container stays. Remove `px-2 py-1 text-xs` and replace with `p-1.5 rounded` for icon buttons.

### Task 4: UsersPage.tsx — Upgrade Action Icons

Replace `✏` emoji button:
```tsx
<button
  onClick={() => setEditUser(user)}
  title="Edit"
  className="p-1.5 rounded transition-colors hover:bg-orange-500/10"
  style={{ color: '#f97316' }}
>
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
    <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
  </svg>
</button>
```

Replace `🗑` emoji button:
```tsx
<button
  onClick={() => setDeleteUser(user)}
  title="Deactivate"
  className="p-1.5 rounded transition-colors hover:bg-red-500/10"
  style={{ color: '#EF4444' }}
>
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="3 6 5 6 21 6"/>
    <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>
    <path d="M10 11v6M14 11v6"/>
    <path d="M9 6V4h6v2"/>
  </svg>
</button>
```

### Task 5: TasksPage.tsx — SVG Kill Icon

Replace the "Kill" text button with a stop icon:
```tsx
<button
  onClick={() => killMutation.mutate(t.id)}
  disabled={killMutation.isPending}
  title="Kill task"
  className="p-1.5 rounded transition-colors hover:bg-red-500/20 disabled:opacity-40"
  style={{ color: '#EF4444', border: '1px solid rgba(239,68,68,0.3)' }}
>
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
  </svg>
</button>
```

### Task 6: CRMPage.tsx — Verify Table

The Leads table already follows the Users standard structure. It lacks an Actions column which is correct (leads are read-only in the portal — no edit/delete). Add `hover:bg-white/5 transition-colors` to rows for consistency with Files/Tasks (Users doesn't have hover but Files/Tasks do — user wants "standardise" so let's keep the hover since it's present in most pages).

No structural changes required to CRMPage.tsx.

---

## Deployment Steps (Task 7)

```bash
# On EC2 (via SSH):
cd /home/ubuntu/mz-ai-assistant
git pull
sudo systemctl restart mezzofy-api.service
cd portal
npm install
npm run build
# Portal dist is served from /mission-control/ via nginx
```

**Critical:** The Leads 500 fix is already committed locally. After `git pull` on EC2 and service restart, the 500 will be resolved.

---

## Files Modified

### Backend
- `server/app/api/admin_portal.py` — Add `/files/{id}/download` endpoint

### Frontend
- `portal/src/api/portal.ts` — Add `downloadFile(id, filename)` function
- `portal/src/pages/FilesPage.tsx` — Programmatic download + SVG icons
- `portal/src/pages/UsersPage.tsx` — SVG icons (emoji → SVG)
- `portal/src/pages/TasksPage.tsx` — SVG stop icon for Kill button
- `portal/src/pages/CRMPage.tsx` — No changes needed (already standard)

---

## Verification Checklist

1. **Leads table loads** — No 500 error after EC2 deploy; leads list appears
2. **Files download works** — Clicking download button saves file locally
3. **Files rename works** — Rename inline edit still functions
4. **Files delete works** — Delete modal still works
5. **Users icons** — Edit shows pencil SVG, delete shows trash SVG
6. **Files icons** — Download shows download SVG, Rename shows pencil SVG, Delete shows trash SVG
7. **Tasks Kill icon** — Stop square SVG shown for running tasks
8. **All icons consistent** — Same 14×14 size, same hover states pattern

---

## Delegation

**Backend Agent (Session 1):** Task 1 — add download endpoint to `admin_portal.py`

**Frontend Agent (Session 1):** Tasks 2–6 — all portal frontend changes (portal.ts + 3 page files)

**Both can run in parallel.** Frontend does NOT need to wait for Backend — both agents work independently.

After both complete → commit → deploy to EC2 (Task 7).
