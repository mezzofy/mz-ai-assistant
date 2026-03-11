# Plan: Mobile v1.17.1 — Patch Release (503 UX Fix)
**Workflow:** bug-fix
**Date:** 2026-03-11
**Created by:** Lead Agent

## Summary

Patch release for the "Connect Microsoft Account → Error popup" bug (HTTP 503).

Two fixes were already applied before this plan was written:
- ✅ Fix 1 (server): EC2 `.env` updated with `MS365_CLIENT_ID`, `MS365_CLIENT_SECRET`,
  `MS365_DELEGATED_REDIRECT_URI`, `MS_TOKEN_FERNET_KEY`. Service restarted.
- ✅ Fix 2 (mobile code): `ConnectedAccountsScreen.tsx` — `ApiError` import + 503-friendly
  message in `handleConnect` catch block.

This plan covers the version bump, build, and commit only.

---

## Task Breakdown

| # | Task | Agent | Scope | Depends On | Est. Sessions | Status |
|---|------|-------|-------|-----------|:-------------:|--------|
| 1 | Bump version to v1.17.1 | Mobile | `APP/` | None | 1 | NOT STARTED |
| 2 | Build debug APK | Mobile | `APP/android/` | Task 1 | 1 (same) | NOT STARTED |
| 3 | Commit + update memory | Mobile | git + memory | Task 2 | 1 (same) | NOT STARTED |

All 3 tasks run in the same session.

---

## Task 1: Version Bump

### File: `APP/android/app/build.gradle`
```
versionCode 28  →  29
versionName "1.17.0"  →  "1.17.1"
```

### File: `APP/package.json`
```
"version": "1.17.0"  →  "1.17.1"
```

---

## Task 2: Build APK

```bash
cd APP/android && ./gradlew assembleDebug
```

Expected output:
- `BUILD SUCCESSFUL`
- APK at `APP/android/app/build/outputs/apk/debug/app-debug.apk`

---

## Task 3: Commit

Stage and commit:
```
git add APP/android/app/build.gradle APP/package.json APP/src/screens/ConnectedAccountsScreen.tsx
git commit -m "chore(mobile): bump version to v1.17.1 (versionCode 29)

Fix 503 UX: friendly error message when MS OAuth not configured on server.
Server fix: EC2 .env now includes MS365_CLIENT_ID + MS365_CLIENT_SECRET.
"
```

Then update `.claude/coordination/memory.md` with the v1.17.1 entry.

---

## Acceptance Criteria

- [ ] `versionCode 29` in `build.gradle`
- [ ] `versionName "1.17.1"` in `build.gradle`
- [ ] `"version": "1.17.1"` in `package.json`
- [ ] `BUILD SUCCESSFUL` from Gradle
- [ ] APK exists at expected path
- [ ] Git commit created
- [ ] Memory updated

---

## Quality Gate (Lead Review)

Lead checks:
- Version numbers consistent across both files
- ConnectedAccountsScreen.tsx change is committed (not just staged)
- Build was successful (no Gradle errors)
