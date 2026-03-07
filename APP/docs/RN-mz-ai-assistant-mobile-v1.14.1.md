# Release Notes — Mezzofy AI Assistant Mobile v1.14.1
**Date:** 2026-03-07
**Type:** Patch
**Platform:** Android
**Build:** versionCode 19

---

## Changes

### Bug Fix: History Tab Task Badges Restored
- Fixed: History tab showed zero task badges for all normal (sync) Q&A messages
- Root cause: v1.14.0 filter `t.queue_name === 'background'` excluded all sync tasks
  (sync tasks have `queue_name='default'`, not `'background'`)
- Fix: Removed `queue_name` filter from HistoryScreen — all tasks now show badges in History
- Chat banner behavior unchanged — still only shows lifecycle banner for background tasks ✅

---

## Files Changed

| File | Change |
|------|--------|
| `src/screens/HistoryScreen.tsx` | Remove `queue_name === 'background'` filter (2 occurrences) |
| `android/app/build.gradle` | versionCode 18→19, versionName "1.14.0"→"1.14.1" |
| `package.json` | version "1.14.0"→"1.14.1" |
| `src/screens/SettingsScreen.tsx` | Version display: v1.14.0→v1.14.1 |

---

## Upgrade Notes
- Direct APK replacement — uninstall not required
- No backend changes required
- No API changes
