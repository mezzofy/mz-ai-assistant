# Plan: Mobile v1.8.0 — Folder Bug Fix + Move-to-Folder Feature
**Workflow:** Change Request (post-implementation — code complete)
**Date:** 2026-03-07
**Created by:** Lead Agent

---

## Context

All source code changes are already implemented (same session). This plan covers
the remaining deployment and build steps only.

### Changes Included in v1.8.0

| # | Type | Change |
|---|------|--------|
| 1 | Bug fix | Folder contents "Failed to load files" → now shows files correctly (UUID type fix in `artifact_manager.py`) |
| 2 | Feature | `PATCH /files/{id}/move` endpoint — move file to different folder or root |
| 3 | Feature | Move icon on file cards in `FilesScreen` (folder picker Alert) |
| 4 | Feature | Move icon on file cards in `FolderContentsScreen` (move-to-root) |
| 5 | UX | Retry button on error state in `FolderContentsScreen` |

---

## Task Breakdown

| # | Task | Agent | Scope | Depends On | Est. Sessions | Status |
|---|------|-------|-------|-----------|:-------------:|--------|
| 1 | Deploy backend to EC2 | (manual — see commands below) | EC2 server | None | — | NOT STARTED |
| 2 | Version bump + APK build | Mobile | `APP/` | Task 1 | 1 | NOT STARTED |

---

## Task 1 — Backend Deployment (Manual — No Agent Needed)

These are shell commands for the human to run directly:

```bash
# On dev machine — push code to GitHub first
# (ensure all changes are committed and pushed)

# Then SSH to EC2
ssh -i mz-ai-key.pem ubuntu@3.1.255.48

# Pull and restart
cd /home/ubuntu/mz-ai-assistant/server
git pull
sudo systemctl restart mezzofy-api.service

# Verify
sudo journalctl -u mezzofy-api.service -n 30 --no-pager
```

**Expected:** Service restarts cleanly, no import errors, port 8000 listening.
**Key fix activated:** `uuid.UUID()` cast in `list_artifacts()` + `PATCH /files/{id}/move` endpoint available.

---

## Task 2 — Mobile Agent: Version Bump + APK Build

**File to update:** `APP/android/app/build.gradle`

| Field | Old | New |
|-------|-----|-----|
| `versionCode` | 11 | 12 |
| `versionName` | "1.7.0" | "1.8.0" |

**File to update:** `APP/src/screens/SettingsScreen.tsx`
- Update version display string to `v1.8.0`

**Build command:**
```bash
cd APP/android && ./gradlew.bat assembleRelease
```

**Expected output:**
- `APP/android/app/build/outputs/apk/release/app-release.apk`
- ~61 MB, versionCode 12, versionName 1.8.0
- Signed with `mezzofy-release.keystore`

---

## Parallel Opportunities

- Task 1 (backend deploy) and Task 2 (mobile build) can run in parallel — they are independent.

---

## Quality Gates

### After Task 1 (Backend Deploy)
- [ ] `sudo journalctl` shows clean startup (no Python import errors)
- [ ] `GET /files/?scope=personal&folder_id=<uuid>` returns `{"artifacts": [], "count": 0}` (not 500)
- [ ] `PATCH /files/{id}/move` returns 200 with `{"moved": true, ...}`

### After Task 2 (Mobile Build)
- [ ] BUILD SUCCESSFUL in gradlew output
- [ ] APK versionCode = 12, versionName = 1.8.0
- [ ] SettingsScreen shows `v1.8.0`
- [ ] Mobile Agent updates `status/mobile.md` checkpoint

---

## Acceptance Criteria

1. Tapping a folder in the Files tab → shows files (or "No files in this folder") — never "Failed to load files"
2. Move icon visible on personal/department file cards where `write=true`
3. Tapping move in FilesScreen → Alert shows root + folder list → pick destination → file moves
4. Tapping move in FolderContentsScreen → "Move to Root" option → file moves to root
5. Error state in FolderContentsScreen has a Retry button
6. APK installable on Android device, version shows 1.8.0 in Settings

---

## Version History Entry

| Version | versionCode | Key Change |
|---------|:-----------:|-----------|
| 1.7.0 | 11 | SettingsScreen version string fix |
| **1.8.0** | **12** | **Folder contents bug fix + move-to-folder feature + retry UX** |
