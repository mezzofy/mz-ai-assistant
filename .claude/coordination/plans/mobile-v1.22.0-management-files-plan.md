# Plan: Mobile v1.22.0 — Management Cross-Department Files View

**Created:** 2026-03-14
**Lead:** Lead Agent
**Status:** READY FOR IMPLEMENTATION

---

## Goal

Management department users should see department folders and files for ALL departments in the mobile Files Tab. Other department users remain unchanged.

**Current behavior (all users):**
1. COMPANY PUBLIC
2. DEPARTMENT — [own dept only]
3. PERSONAL

**Target behavior (management only):**
1. COMPANY PUBLIC (write)
2. DEPARTMENT — FINANCE (read-only)
3. DEPARTMENT — MARKETING (read-only)
4. DEPARTMENT — SALES (read-only)
5. DEPARTMENT — SUPPORT (read-only)
6. DEPARTMENT — MANAGEMENT (full write — own dept)
7. PERSONAL (write)

**Non-management users:** Unchanged.

---

## Agent Tasks

### Backend Agent (Phase A) — 1 session

**Files to modify:**
- `server/app/api/files.py`
- `server/app/api/folders.py`

**Tasks:**

**A1** — Add `GET /files/departments` endpoint (management-only):
```python
# SELECT DISTINCT department FROM users WHERE department IS NOT NULL ORDER BY department
# Returns: {"departments": ["finance", "management", "marketing", ...]}
# 403 if user is not management
```

**A2** — Update `GET /files/?scope=department` to accept `?dept=` param:
- Add `dept: Optional[str] = Query(None)` to `list_files()`
- If management user AND dept provided → pass `dept` as department filter to `list_artifacts()`
- Non-management: `dept` param silently ignored
- Update `_check_read_access()`: if `_is_management(current_user)` → skip department equality check

**A3** — Update `GET /folders/?scope=department` to accept `?dept=` param:
- Add `dept: Optional[str] = Query(None)` to `list_folders()`
- If management AND dept provided → use dept in `_folder_visibility_clause()` instead of user's own dept
- Non-management: dept silently ignored

**A4** — Update `search_files()` for management cross-dept search:
```python
# Conditionally build WHERE clause based on _is_management(current_user)
# Management: OR (a.scope = 'department')  -- all dept files
# Others:     OR (a.scope = 'department' AND a.department = :dept)  -- own dept only
```

**Reuse:** `_is_management(user)` already exists at `files.py:61` and `folders.py:47`.

**After completing:** Write status to `.claude/coordination/status/backend.md`. Write handoff to `.claude/coordination/handoffs/backend-to-mobile-v1.22.0.md` confirming all endpoints are ready.

---

### Mobile Agent (Phase B + C) — 1–2 sessions

**Prerequisite:** Backend Phase A must be complete.

**Files to modify:**
- `APP/src/api/files.ts`
- `APP/src/api/folders.ts`
- `APP/src/screens/FilesScreen.tsx`
- `APP/package.json`
- `APP/android/app/build.gradle`

**Tasks:**

**B1** — Add `listDepartmentsApi()` to `APP/src/api/files.ts`:
```typescript
export async function listDepartmentsApi(): Promise<{departments: string[]}> {
  // GET /files/departments
}
```

**B2** — Update `listFilesApi()` in `APP/src/api/files.ts`:
```typescript
// Add optional dept?: string param → append ?dept=<name> to query string
```

**B3** — Update `listFoldersApi()` in `APP/src/api/folders.ts`:
```typescript
// Add optional dept?: string param → append ?dept=<name> to query string
```

**B4** — Refactor `APP/src/screens/FilesScreen.tsx`:

Detection:
```typescript
const isManagement = (user?.department ?? '').toLowerCase() === 'management';
```

State additions:
```typescript
const [departments, setDepartments] = useState<string[]>([]);
const [deptSectionsLoading, setDeptSectionsLoading] = useState(false);
// sections state key extended from FileScope to string:
// 'company', 'personal', 'dept_finance', 'dept_sales', etc.
```

Loading (management path):
```typescript
// 1. Fetch department list
// 2. Load company + personal (same as today)
// 3. Load per-dept sections in parallel
//    loadDeptSection(deptName) calls listFoldersApi('department', deptName)
//    and listFilesApi('department', null, deptName)
//    stores result in sections['dept_' + deptName]
```

Write access per section:
- Own dept (management): `canWrite('department', user)` → true
- Other depts: hardcoded false (read-only) — hide upload/folder create/delete/rename controls

Render order: Company → [depts alphabetically, management last] → Personal

Non-management: completely unchanged code path.

**C** — Version bump:
- `APP/package.json`: `"version": "1.22.0"`
- `APP/android/app/build.gradle`: `versionCode 34`, `versionName "1.22.0"`

**Reuse:**
- `deptColors` in `APP/src/utils/theme.ts:19` for per-dept section accent color (optional enhancement)
- `canWrite()` in `APP/src/utils/fileRights.ts` — unchanged, used for own-dept check

**After completing:** Update `.claude/coordination/status/mobile.md` with v1.22.0 changelog.

---

## Sequencing

```
[Backend Agent] A1 → A2 → A3 → A4 → handoff
                                        ↓
                              [Mobile Agent] B1 → B2 → B3 → B4 → C
```

Backend must complete first. Mobile reads the handoff before starting.

---

## Acceptance Criteria

- [ ] `GET /files/departments` returns all distinct depts (management user only; 403 for others)
- [ ] `GET /files/?scope=department&dept=sales` returns sales files for management user
- [ ] `GET /files/?scope=department&dept=sales` is ignored (own dept used) for non-management users
- [ ] Management user sees N department sections in Files Tab (one per dept returned by API)
- [ ] Management user sees read-only other-dept sections (no upload/folder-create visible)
- [ ] Management user sees write controls on their own (management) dept section
- [ ] Non-management users see identical behavior to v1.21.0
- [ ] Search results for management include files from all departments
- [ ] APK builds clean at v1.22.0 (versionCode 34)
