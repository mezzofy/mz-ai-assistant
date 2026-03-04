# Mobile Build Plan — v1.2.0
**Date:** 2026-03-05
**Agent:** Mobile
**Lead:** Review after build completes

---

## What's in v1.2.0

| Change | File | Type |
|--------|------|------|
| Friendlier error messages in chat | `APP/src/screens/ChatScreen.tsx` | Bug fix |
| AI Usage Stats screen (new) | `APP/src/screens/AIUsageStatsScreen.tsx` | Feature |
| Admin API helper | `APP/src/api/admin.ts` | Feature |
| AIUsageStats navigation registered | `APP/App.tsx` | Feature |
| SettingsRow AI Usage Stats tappable | `APP/src/screens/SettingsScreen.tsx` | Feature |
| Artifact registration fix (server) | Server-side (already deployed) | Bug fix |

---

## Mobile Agent Tasks (in order)

### Step 1 — Bump version
- `APP/package.json` line 3: `"version": "1.1.2"` → `"version": "1.2.0"`
- `APP/src/screens/SettingsScreen.tsx` line 182: `v1.1.2` → `v1.2.0`

### Step 2 — TypeScript check
```bash
cd C:\Mezzofy\workspace\mz-ai-assistant\APP
npx tsc --noEmit
```
Must complete with 0 errors (pre-existing jest type warnings are acceptable).

### Step 3 — Build Android APK
```bash
cd C:\Mezzofy\workspace\mz-ai-assistant\APP\android
gradlew.bat assembleDebug
```
Expected: BUILD SUCCESSFUL, APK at `APP/android/app/build/outputs/apk/debug/app-debug.apk`

### Step 4 — Report to Lead
Write output to `.claude/coordination/status/mobile.md`:
- TypeScript result (pass/fail, error count)
- Build result (success/fail, task count, APK path + size)
- Any warnings or issues

---

## Lead Review Checklist

- [ ] `package.json` version = `1.2.0`
- [ ] `SettingsScreen.tsx` version string = `v1.2.0`
- [ ] TypeScript: 0 new errors
- [ ] Android: BUILD SUCCESSFUL
- [ ] APK produced at expected path
- [ ] No new lint warnings from new files
