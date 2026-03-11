# Context Checkpoint: Mobile Agent
**Date:** 2026-03-12
**Session:** v1.18.0 — Fix: SettingsScreen version label (was stuck at v1.17.1)
**Context:** ~10% at checkpoint
**Reason:** v1.18.0 APK complete and verified

---

## v1.18.0 Build Result

| Field | Value |
|-------|-------|
| Result | BUILD SUCCESSFUL |
| APK path | `APP/android/app/build/outputs/apk/release/app-release.apk` |
| APK size | ~60 MB |
| versionCode | 30 |
| versionName | 1.18.0 |
| Build time | 1m 2s |
| Branch | eric-design |
| Commits | `6f2bc2c` — fix(mobile): update SettingsScreen version label to v1.18.0 |

**Changes in v1.18.0:**
- `APP/android/app/build.gradle`: versionCode 30, versionName 1.18.0 (was stuck at 29/1.17.1)
- `APP/src/screens/SettingsScreen.tsx`: version label → v1.18.0 (hardcoded string was v1.17.1)
- `APP/package.json`: version 1.18.0 (already bumped before this session)

**Root cause documented:** React Native does NOT auto-sync versionName from package.json.
Three places must always be updated together: `build.gradle`, `package.json`, `SettingsScreen.tsx`.

---

## v1.17.1 Build Result

| Field | Value |
|-------|-------|
| Result | BUILD SUCCESSFUL |
| APK path | `APP/android/app/build/outputs/apk/debug/app-debug.apk` |
| APK size | ~61 MB |
| versionCode | 29 |
| versionName | 1.17.1 |
| Build time | 22s |
| Branch | eric-design |
| Commit | `fa0b851` — chore(mobile): bump version to v1.17.1 (versionCode 29) |

**Changes in v1.17.1:**
- `APP/src/screens/ConnectedAccountsScreen.tsx`: `ApiError` import + 503-specific friendly message in `handleConnect` catch block (commit b54c487)
- `APP/android/app/build.gradle`: versionCode 29, versionName 1.17.1
- `APP/package.json`: version 1.17.1
- `APP/src/screens/SettingsScreen.tsx`: version label → v1.17.1
- EC2 `.env`: MS365_CLIENT_ID + MS365_CLIENT_SECRET added (user action)

---

## v1.17.0 Build Result

| Field | Value |
|-------|-------|
| Result | BUILD SUCCESSFUL |
| APK path | `APP/android/app/build/outputs/apk/release/app-release.apk` |
| APK size | 61 MB |
| versionCode | 28 |
| versionName | 1.17.0 |
| Build time | 51s |
| Branch | eric-design |
| Commit | `7f3f430` — feat(mobile): add Connected Accounts screen for MS OAuth (v1.17.0) |

**Changes in v1.17.0:**
- `APP/src/api/msOAuth.ts` (NEW): 4 API functions for MS OAuth endpoints
- `APP/src/stores/msStore.ts` (NEW): Zustand store for MS connection state
- `APP/src/screens/ConnectedAccountsScreen.tsx` (NEW): Connect/disconnect UI with deep link handler
- `APP/src/screens/SettingsScreen.tsx`: Added "Connected Accounts" row; version → v1.17.0
- `APP/App.tsx`: Registered ConnectedAccounts stack screen
- `APP/android/app/src/main/AndroidManifest.xml`: msalauth://callback intent-filter
- `APP/android/app/build.gradle`: versionCode 28, versionName 1.17.0
- `APP/package.json`: version 1.17.0

---

## v1.16.0 Build Result

| Field | Value |
|-------|-------|
| Result | BUILD SUCCESSFUL |
| APK path | `APP/android/app/build/outputs/apk/release/app-release.apk` |
| APK size | 61 MB |
| versionCode | 27 |
| versionName | 1.16.0 |
| Build time | 18s |
| Branch | eric-design |
| Commit | `bbbc8d5` — chore(mobile): bump version to v1.16.0 (versionCode 27) |

**Changes in v1.16.0:**
- `APP/src/screens/ChatScreen.tsx`: `handleStopRecording()` → `setInput(transcript)` + `setInputMode('text')`; button label "Stop & Send" → "Stop & Edit"
- `APP/src/utils/theme.ts`: `INPUT_MODES` — `myfiles` moved to index 5 (before `url` at index 6)

---

## v1.15.0 Build Result

| Field | Value |
|-------|-------|
| Result | BUILD SUCCESSFUL |
| APK path | `APP/android/app/build/outputs/apk/release/app-release.apk` |
| APK size | 61 MB |
| versionCode | 26 |
| versionName | 1.15.0 |
| Build time | 1m 7s |
| Branch | eric-design |
| Commit | `03121ce` — chore(mobile): bump version to v1.15.0 (versionCode 26) |

**Changes in v1.15.0:**
- `server/app/api/files.py`: image OCR+vision inline analysis on upload; `image_analysis` in response
- `server/app/api/chat.py`: `_IMAGE_EXTENSIONS` set; `send_artifact()` routes images through `image_handler`
- `server/tests/test_files.py`: 5 new tests (all passing)
- `APP/src/utils/theme.ts`: `INPUT_MODES` 9→7 (video, audio removed)
- `APP/src/screens/ChatScreen.tsx`: `handleModeAction()` simplified; `MediaType` import removed

---

## v1.14.7 Changes (BUG-007)

**Files modified:**
- `APP/src/api/chat.ts`: added `progress?`, `current_step?`, `started_at?` to `TaskSummary` interface
- `APP/src/stores/chatStore.ts`: `pollActiveTask` — session guard `if (get().sessionId !== sessionId) return;` (Fix B); `sendToServer` — `response.response || 'Task completed.'` fallback (Fix C)
- `APP/src/screens/ChatScreen.tsx`: banner condition `activeTask && activeTask.session_id === sessionId` (Fix D); added progress % + step description sub-line to banner body
- `APP/android/app/build.gradle`: versionCode 24→25, versionName "1.14.6"→"1.14.7"
- `APP/package.json`: "1.14.6"→"1.14.7"
- `APP/src/screens/SettingsScreen.tsx`: version label v1.14.6→v1.14.7

**Bugs fixed:**
- A: `progress` + `current_step` now mapped into TypeScript and displayed in banner
- B: Stale poll response discarded when session changed (race condition on "+" new chat)
- C: Empty assistant bubble prevented by `|| 'Task completed.'` fallback
- D: Banner is session-scoped — only shows when `activeTask.session_id === sessionId`

---

## v1.14.6 Build Result

| Field | Value |
|-------|-------|
| Result | BUILD SUCCESSFUL |
| APK path | `APP/android/app/build/outputs/apk/release/app-release.apk` |
| APK size | ~61 MB |
| versionCode | 24 |
| versionName | 1.14.6 |
| Build time | 1m 2s |
| Branch | eric-design |
| Commits | `ec3a071` (all 7 files — BUG-006 fixes + version bump) |

**Changes in v1.14.6 (BUG-006):**
- `server/app/api/chat.py`: add `append_message` import; pre-save user message immediately after `agent_tasks` INSERT — chat history never blank if worker crashes
- `server/app/context/processor.py`: wrap user-message append with `if not agent_task_id:` — prevents duplicate user message when task completes
- `server/app/tasks/tasks.py`: `@worker_ready.connect` stale recovery — marks `running` tasks >15 min as failed on worker start; `SoftTimeLimitExceeded` handler — marks failed immediately, no retry
- `APP/src/stores/chatStore.ts`: `loadHistory()` now sets `activeTask` from tasks array — restores task banner when opening session from History

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
| 1.14.5 | 23 | BUG-005: session_id always set; History badges fixed for all task states |
| 1.14.6 | 24 | BUG-006: stale task recovery; user msg pre-save; SoftTimeLimitExceeded handler; activeTask in loadHistory |
| 1.14.7 | 25 | BUG-007: progress visibility in banner; new-chat race fix; empty bubble guard; session-scoped banner |
| **1.15.0** | **26** | **Image OCR+vision analysis on upload; remove video/audio input modes** |
| **1.16.0** | **27** | **Speech populates input (not auto-send); My Files before URL in input grid** |
| **1.17.0** | **28** | **Connected Accounts — MS OAuth mobile UI (Settings → Connect Microsoft Account)** |
| **1.17.1** | **29** | **Patch: 503 UX — friendly error when MS OAuth unconfigured on server** |
| **1.18.0** | **30** | **MS Contacts backend (FEAT-013); fix: SettingsScreen version label sync** |

---

## Resume Instructions (if more work)

After /clear, load in order:
1. `CLAUDE.md`
2. `.claude/agents/mobile.md`
3. `.claude/skills/mobile-developer.md`
4. `.claude/coordination/memory.md`
5. `.claude/coordination/status/mobile.md` (this file)
