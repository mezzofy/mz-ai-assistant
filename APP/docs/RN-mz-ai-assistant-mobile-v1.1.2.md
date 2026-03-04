# Release Notes — Mezzofy AI Assistant Mobile v1.1.2
**Date:** 2026-03-04
**Type:** Patch
**Platform:** Android
**Build:** versionCode 5

---

## Changes

### Chat Header Layout — DeptBadge Relocation
- `DeptBadge` moved from the title row to the subtitle row in the chat screen header
- Title row now has full available width — long custom chat titles no longer truncated
- Subtitle row layout: `[DEPT BADGE]  Name · role`

### No Functional Changes
- No API changes, no backend changes, no behavior changes
- Edit pencil still appears correctly next to title when a session exists

---

## Files Changed

| File | Change |
|------|--------|
| `src/screens/ChatScreen.tsx` | Remove DeptBadge from `headerTop`; add to `headerSubRow`; add `headerSubRow` style; remove `marginTop` from `headerSub` |
| `android/app/build.gradle` | versionCode 4→5, versionName "1.1.1"→"1.1.2" |
| `package.json` | version "1.1.1"→"1.1.2" |
| `src/screens/SettingsScreen.tsx` | Version display: v1.1.1→v1.1.2 |

---

## Upgrade Notes
- Direct APK replacement — uninstall not required
- Visual-only change; no data migration needed
