# Context Checkpoint: Mobile Agent
**Date:** 2026-03-08
**Session:** v1.14.5 — BUG-005 session_id fix + History badge fix + release APK build
**Context:** ~12% at checkpoint
**Reason:** v1.14.5 release APK built successfully

---

## v1.14.5 Build Result

| Field | Value |
|-------|-------|
| Result | BUILD SUCCESSFUL |
| APK path | `APP/android/app/build/outputs/apk/release/app-release.apk` |
| APK size | ~61 MB |
| versionCode | 23 |
| versionName | 1.14.5 |
| Build time | 43s |
| Branch | eric-design |
| Commits | `9b6d8fb` (versionCode 23, package.json, SettingsScreen) |

**Changes in v1.14.5 (BUG-005):**
- `server/app/api/chat.py`: call `get_or_create_session()` synchronously before `agent_tasks` INSERT — `session_id` is never NULL on task creation
- `APP/src/stores/chatStore.ts`: capture `session_id` from 202 response for correct task polling
- `APP/src/screens/HistoryScreen.tsx`: show Task ID badges for failed and in-progress tasks (not just completed)
- `SettingsScreen.tsx`: version label → v1.14.5

---

## v1.14.4 Build Result

| Field | Value |
|-------|-------|
| Result | BUILD SUCCESSFUL |
| APK path | `APP/android/app/build/outputs/apk/release/app-release.apk` |
| APK size | ~61 MB |
| versionCode | 22 |
| versionName | 1.14.4 |
| Build time | 42s |
| Branch | eric-design |
| Commits | `820ba6a` (backend fixes + SettingsScreen), `8f3cd43` (versionCode 22, package.json) |

**Changes in v1.14.4:**
- `tasks.py`: fix AGENT_MAP — stores classes not instances; call `AGENT_MAP[name](config)` to instantiate
- `celery_app.py`: `@worker_process_init` signal disposes SQLAlchemy engine pool on worker startup (prevents asyncpg connections bound to parent-process event loop)
- `tasks.py`: catch `MaxRetriesExceededError` in `process_chat_task()` → update `agent_tasks.status` to `'failed'` (prevents stuck 'running' tasks)
- `SettingsScreen.tsx`: version label → v1.14.4

---

## v1.14.3 Build Result

| Field | Value |
|-------|-------|
| Result | BUILD SUCCESSFUL |
| APK path | `APP/android/app/build/outputs/apk/release/app-release.apk` |
| APK size | ~61 MB |
| versionCode | 21 |
| versionName | 1.14.3 |
| Build time | 47s |
| Branch | eric-design |
| Commits | `ff9a141` (backend P0 fix + version bump), `0026f12` (SettingsScreen label) |

**Changes in v1.14.3:**
- `server/app/tasks/tasks.py`: register `process_chat_task`; `_update_agent_task_session()` writes real session UUID back to `agent_tasks.session_id` after first-message session creation
- `server/app/api/chat.py`: default `notify_on_done=true` in `agent_tasks` INSERT
- `SettingsScreen.tsx`: version label → v1.14.3

---

## v1.14.2 Build Result

| Field | Value |
|-------|-------|
| Result | BUILD SUCCESSFUL |
| APK path | `APP/android/app/build/outputs/apk/release/app-release.apk` |
| APK size | ~61 MB |
| versionCode | 20 |
| versionName | 1.14.2 |
| Build time | 43s |
| Branch | eric-design |
| Commit | `41d50d2` — chatStore queued-task UX fix + version bump |

**Changes in v1.14.2:**
- `chatStore.ts`: skip adding assistant message for queued tasks — task banner handles UX; only synchronous responses add a message bubble
- `chatStore.ts`: safe optional chaining on `artifacts?.length` and `tools_used?.length` (prevents crash when fields absent)
- `SettingsScreen.tsx`: version label → v1.14.2

---

## v1.14.1 Build Result

| Field | Value |
|-------|-------|
| Result | BUILD SUCCESSFUL |
| APK path | `APP/android/app/build/outputs/apk/release/app-release.apk` |
| APK size | ~61 MB |
| versionCode | 19 |
| versionName | 1.14.1 |
| Build time | 42s |
| Branch | eric-design |
| Commits | `e480445` (versionCode 19, HistoryScreen fix), `60a0431` (release notes, package.json, SettingsScreen label) |

---

## v1.14.0 Build Result (previous session)

| Field | Value |
|-------|-------|
| Result | BUILD SUCCESSFUL |
| APK path | `APP/android/app/build/outputs/apk/release/app-release.apk` |
| APK size | ~61 MB |
| versionCode | 18 |
| versionName | 1.14.0 |
| Build time | 1m |
| Branch | eric-design |
| Commit | 1314ad2 — chore(mobile): bump version to v1.14.0 (versionCode 18) |

---

## v1.13.0 Changes (previous session)

| # | File | Change |
|---|------|--------|
| 1 | `server/app/api/files.py` | Added `GET /files/storage-stats` endpoint (returns `{total_bytes, count}` for personal files) |
| 2 | `APP/src/screens/HistoryScreen.tsx` | Header: row layout with refresh button (top-right); `ActivityIndicator` while refreshing, `refresh-outline` icon otherwise; `disabled={refreshing}` prevents double-tap |
| 3 | `APP/src/api/files.ts` | Added `StorageStatsResponse` interface + `getStorageStatsApi()` calling `/files/storage-stats` |
| 4 | `APP/src/stores/settingsStore.ts` | Replaced `fileCount`/`loadFileCount`/`listFilesApi` with `storageDisplay`/`loadStorageInfo`/`getStorageStatsApi` + `formatBytes` helper (B/KB/MB/GB) |
| 5 | `APP/src/screens/SettingsScreen.tsx` | Destructures `storageDisplay`/`loadStorageInfo`; Storage & Data row shows formatted size; version string → `v1.13.0` |
| 6 | `APP/android/app/build.gradle` | `versionCode 16 → 17`, `versionName "1.12.0" → "1.13.0"` |
| 7 | `APP/package.json` | `"version": "1.12.0"` → `"1.13.0"` |

---

## Features in v1.13.0 (eric-design branch)

1. **History tab refresh button** — tappable header button (top-right), consistent with FilesScreen pattern. Spinner while loading, disabled on double-tap. Pull-to-refresh still works unchanged.
2. **Settings → Storage & Data** — now shows formatted total file size (`X.X MB`) instead of file count (`N files`). Backed by new `GET /files/storage-stats` endpoint that sums `os.path.getsize()` for the user's personal artifacts on disk.

---

## Version History (this branch)

| Version | versionCode | Key Change |
|---------|:-----------:|-----------|
| 1.2.0 | 6 | AI Usage Stats screen (model status + system health) |
| 1.3.0 | 7 | AI Usage Stats real data (LLM usage stats wired) |
| 1.4.0 | 8 | Auth header for downloads; success color for status pills |
| 1.5.0 | 9 | Logout clears chat state + AsyncStorage titles |
| 1.6.0 | 10 | Share sheet download flow; react-native-share added |
| 1.7.0 | 11 | SettingsScreen version string fix |
| 1.8.0 | 12 | Folder contents bug fix + move-to-folder + retry UX |
| 1.9.0 | 13 | FolderContentsScreen fix |
| 1.10.0 | 14 | Task ID & status bar (chat + history) + package.json sync |
| 1.11.0 | 15 | File search, file rename, creator display in file metadata UI |
| 1.12.0 | 16 | History tab: pull-to-refresh + Task ID label on task badges |
| 1.13.0 | 17 | History refresh button + Settings storage size display |
| 1.14.0 | 18 | Long-running chat task support + background task tracking + WS notifications |
| 1.14.1 | 19 | HistoryScreen: show all session tasks; release notes |
| 1.14.2 | 20 | chatStore: skip assistant msg for queued tasks; safe optional chaining |
| 1.14.3 | 21 | Backend P0: register Celery task, session_id writeback, notify_on_done default |
| 1.14.4 | 22 | Backend: fix AGENT_MAP instantiation, event loop, stuck task status |
| **1.14.5** | **23** | **BUG-005: session_id always set; History badges fixed for all task states** |

---

## Resume Instructions (if more work)

After /clear, load in order:
1. `CLAUDE.md`
2. `.claude/agents/mobile.md`
3. `.claude/skills/mobile-developer.md`
4. `.claude/coordination/memory.md`
5. `.claude/coordination/status/mobile.md` (this file)
