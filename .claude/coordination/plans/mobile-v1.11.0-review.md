# Quality Gate Review: v1.11.0 — Mobile Files Tab Search, Rename & Creator Display
**Date:** 2026-03-07
**Reviewer:** Lead Agent
**Plan:** (inline — no separate plan file; plan embedded in conversation)
**Version Target:** v1.11.0 (versionCode 14)

---

## Scope of Review

| File | Change |
|------|--------|
| `server/app/context/artifact_manager.py` | `list_artifacts()` LEFT JOIN users → adds `creator_name`, `created_by_id` |
| `server/app/api/files.py` | `GET /files/search`, `PATCH /{id}/rename`, `_check_rename_access()` helper |
| `APP/src/api/files.ts` | `ArtifactItem` fields, `SearchResponse`, `searchFilesApi`, `renameFileApi` |
| `APP/src/screens/FilesScreen.tsx` | Search bar, creator name in cards, rename modal, search results view |
| `APP/src/screens/FolderContentsScreen.tsx` | Creator name in cards, rename modal |

---

## Backend Review

### artifact_manager.py — `list_artifacts()`

- [x] LEFT JOIN `users u ON u.id = a.user_id` — correct FK relationship confirmed (`artifacts.user_id REFERENCES users(id)`)
- [x] `creator_name: row.creator_name or "Unknown"` — safe fallback for orphaned records
- [x] `created_by_id: str(row.created_by_id)` — UUID serialized to string correctly
- [x] f-string interpolation only uses function-internal values (`base_filter`, `folder_filter`) — not user input, no SQL injection risk
- [x] Existing function signature unchanged — backward compatible with `list_user_artifacts()` wrapper and all callers
- [x] No regression risk to existing tests (test_files.py patches `list_user_artifacts` or `list_artifacts` at API level)

### files.py — Route Ordering

- [x] `GET /files/search` registered at line 218, before `GET /{file_id}` at line 264 — FastAPI will not mis-route "search" as a file_id ✅ CRITICAL CHECK PASSED

### files.py — `GET /files/search`

- [x] Authentication: `Depends(get_current_user)` — all authenticated users only ✅
- [x] Input validation: `q: str = Query(..., min_length=1)` — empty search blocked ✅
- [x] Limit bounded: `Query(30, ge=1, le=100)` — abuse prevention ✅
- [x] ILIKE with parameterized `%q%` pattern — case-insensitive, no SQL injection ✅
- [x] RBAC enforced in WHERE clause — personal (uid match), department (dept match), company (all) ✅
- [x] `creator_name` and `created_by_id` included in response ✅
- [x] Results ordered `created_at DESC` ✅
- [x] Returns `{"results": [...], "count": N}` — matches `SearchResponse` interface ✅

### files.py — `PATCH /{file_id}/rename`

- [x] Filename validation: `strip()`, `len > 255`, `'/' in`, `'\\' in` — path traversal blocked ✅
- [x] `_check_read_access` called FIRST → 404 for inaccessible files (info leak prevention) ✅
- [x] `_check_rename_access` called SECOND → 403 for non-creator ✅
- [x] `_check_rename_access` compares `artifact["user_id"]` vs `current_user["user_id"]` — both are strings from JWT decode, no type mismatch ✅
- [x] DB update parameterized: `{"n": new_name, "id": file_id}` — no SQL injection ✅
- [x] `await db.commit()` present ✅
- [x] Response `{"renamed": True, "artifact_id": file_id, "filename": new_name}` matches `RenameFileResponse` interface ✅
- [x] Physical file on disk unchanged — only DB `filename` column updated (correct — download still works) ✅

### files.py — `_check_rename_access()`

- [x] Creator-only regardless of scope — consistent with plan spec ✅
- [x] 403 status code (not 404) — intentional, user has read access but not rename ✅

---

## Mobile Review

### files.ts

- [x] `ArtifactItem.creator_name?: string` — optional, backward compatible with existing artifact responses ✅
- [x] `ArtifactItem.created_by_id?: string` — optional, backward compatible ✅
- [x] `searchFilesApi()`: `encodeURIComponent(q)` prevents query string injection ✅
- [x] `renameFileApi()`: PATCH method, `Content-Type: application/json`, correct body shape ✅
- [x] `SearchResponse` matches backend `{"results": [...], "count": N}` exactly ✅
- [x] `RenameFileResponse` matches backend `{"renamed": true, "artifact_id": "...", "filename": "..."}` ✅

### FilesScreen.tsx

- [x] `useRef` added to React imports ✅
- [x] `renameFileApi`, `searchFilesApi` added to files import ✅
- [x] `RenameFileModal` type defined (separate from `FolderModalState` — correct, no merging) ✅
- [x] New state: `searchActive`, `searchQuery`, `searchResults`, `renameFileModal`, `searchDebounceRef` ✅
- [x] Search useEffect: 300ms debounce, cleanup on unmount/query change ✅
- [x] `canRename(f)`: `f.created_by_id === user.id` — correct string comparison, null-guarded ✅
- [x] `submitRenameFileModal` deps: `[renameFileModal, loadSection, searchResults, searchQuery]` — all defined before this callback, no TDZ issue ✅
- [x] After rename during active search: `loadSection` + re-run `searchFilesApi` — both views refreshed ✅
- [x] Search close button resets `searchActive`, `searchQuery`, `searchResults` — clean state ✅
- [x] `searchResults !== null` gates the results view (not `searchResults.length > 0`) — correct: `null` = no search, `[]` = search returned nothing ✅
- [x] Scope badge colors: company → `colors.info` (blue), dept → `colors.accent` (orange), personal → `colors.textMuted` (grey) — matches plan spec ✅
- [x] Creator name in `renderFileCard`: `date · name` format ✅
- [x] Creator name in `renderSearchResult`: `name · date` format (name-first for shared files where accountability matters) ✅
- [x] Rename button (`pencil-outline`) only rendered when `canRenameFile === true` ✅
- [x] Rename modal: same pattern as folder modal (reused styles), autofocus, Enter submits, maxLength=255 ✅
- [x] New styles: `searchBar`, `searchInput`, `scopeBadge`, `scopeBadgeText` added to StyleSheet ✅
- [x] Existing folder create/rename modal unchanged ✅
- [x] Existing download, delete, move, upload operations unchanged ✅

### FolderContentsScreen.tsx

- [x] `Modal`, `TextInput` added to RN imports ✅
- [x] `renameFileApi` imported (NOT `searchFilesApi` — correct, no search in folder view) ✅
- [x] `RenameFileModal` type defined before component ✅
- [x] `renameFileModal` state initialized ✅
- [x] `canRename(f)` defined before `loadFiles` — normal function, no TDZ issue ✅
- [x] `loadFiles` defined before `submitRenameFileModal` — TDZ issue proactively caught and fixed ✅
- [x] `submitRenameFileModal` deps: `[renameFileModal, loadFiles]` — correct ✅
- [x] Creator name in inline card render: `date · name` ✅
- [x] Rename button (`pencil-outline`) conditional on `canRenameFile` ✅
- [x] Rename modal + styles added (same visual pattern as FilesScreen) ✅
- [x] Existing delete, move, download, upload unchanged ✅

---

## Issues Found

### MINOR — Cosmetic (Not a Blocker)

**Dangling dot in `renderSearchResult` when `creator_name` is falsy:**
```tsx
{f.creator_name ? <Text>{f.creator_name}</Text> : null}
<Text>·</Text>   {/* ALWAYS rendered */}
<Text>{date}</Text>
```
If `creator_name` is null/undefined, display shows `· Mar 7` instead of `Mar 7`.

**Assessment:** NOT a blocker. The backend guarantees `creator_name` is always populated via `or "Unknown"` fallback. All users have a `users.name` value (NOT NULL constraint in schema). The conditional branch on mobile can only fire if the API contract is violated — which it won't be. Flag for v1.12.0 polish if desired.

---

## Quality Gate Checklist

### Documents
- [x] Plan specified in conversation (no separate file needed for this change request)
- [x] API contract defined and matched by both backend and mobile

### Code — Backend
- [x] Input validation on all new endpoints ✅
- [x] Authentication enforced: `Depends(get_current_user)` on all 3 new routes ✅
- [x] Parameterized queries throughout — no SQL injection ✅
- [x] RBAC correct: search (WHERE clause), rename (`_check_read_access` + `_check_rename_access`) ✅
- [x] Route ordering correct: `/search` before `/{file_id}` ✅
- [x] No breaking changes to existing endpoints ✅

### Code — Mobile
- [x] API contract matched exactly ✅
- [x] Optional fields are backward compatible ✅
- [x] Hook dependency arrays correct ✅
- [x] TDZ ordering issue caught and fixed ✅
- [x] Existing functionality (delete, move, download, upload, folders) unchanged ✅
- [x] State transitions correct (searchResults null/array gating) ✅

### Integration
- [x] `created_by_id` UUID from backend matches `user.id` UUID in mobile auth store (`UserInfo.id: string`) ✅
- [x] `creator_name` from `users.name` column (NOT NULL in DB schema) → safe ✅

### No Regressions Expected
- [x] Existing test suite: `test_files.py` tests mock `list_user_artifacts` / `list_artifacts` at API boundary — new SQL JOIN doesn't affect mock return values ✅
- [x] `list_user_artifacts` wrapper unchanged ✅
- [x] `get_artifact`, `delete_file`, `move_file` endpoints unchanged ✅

---

## Decision

**✅ PASS — Proceed to Task 3: Tests + APK Build**

No blocking issues found. The 1 minor cosmetic issue (dangling dot) is a non-blocker due to backend guarantee.

---

## Next Steps

### Task 3A — Run Test Suite (Manual or Tester Agent)
```bash
# On dev machine or EC2
cd server && python -m pytest tests/ --no-cov -v
```
Expected: **302+ tests passing, 0 failing** (255 existing + existing files tests + any new ones)

### Task 3B — Backend Deploy to EC2
```bash
# On dev machine — ensure all changes committed and pushed to GitHub first
ssh -i mz-ai-key.pem ubuntu@3.1.255.48
cd /home/ubuntu/mz-ai-assistant/server
git pull
sudo systemctl restart mezzofy-api.service
sudo journalctl -u mezzofy-api.service -n 30 --no-pager
```

**Verify these new endpoints work:**
- `GET /files/search?q=test` → `{"results": [...], "count": N}`
- `PATCH /files/{uuid}/rename` → `{"renamed": true, ...}`
- `GET /files/?scope=personal` response now includes `creator_name` and `created_by_id`

### Task 3C — Mobile Version Bump + APK Build (Mobile Agent)

| Field | Old | New |
|-------|-----|-----|
| `versionCode` in `build.gradle` | 13 | 14 |
| `versionName` in `build.gradle` | "1.10.0" | "1.11.0" |
| Version string in `SettingsScreen.tsx` | `v1.10.0` | `v1.11.0` |

```bash
cd APP/android && ./gradlew.bat assembleRelease
```
Expected: `app-release.apk` ~61 MB, versionCode 14, versionName 1.11.0

---
**Review complete. Quality gate: PASS.**
