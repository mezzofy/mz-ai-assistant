# Quality Gate Review: Mobile v1.17.0 — Connected Accounts
**Reviewer:** Lead Agent
**Date:** 2026-03-11
**Commit:** `7f3f430`

## Files Reviewed

| File | Status |
|------|--------|
| `APP/src/api/msOAuth.ts` | ✅ PASS |
| `APP/src/stores/msStore.ts` | ✅ PASS |
| `APP/src/screens/ConnectedAccountsScreen.tsx` | ✅ PASS (1 warning) |
| `APP/src/screens/SettingsScreen.tsx` | ✅ PASS |
| `APP/App.tsx` | ✅ PASS |
| `APP/android/app/src/main/AndroidManifest.xml` | ✅ PASS |
| `APP/android/app/build.gradle` | ✅ PASS |
| `APP/package.json` | ✅ PASS |

---

## Findings

### Blockers: 0

### Warnings: 1

**W1 — `oauthLoading` has no cancel/timeout path** (`ConnectedAccountsScreen.tsx` ~line 92)

After `Linking.openURL(auth_url)` resolves, `oauthLoading` stays `true` until a `msalauth://` deep link
fires. If the user cancels Microsoft login and returns to the app without completing OAuth, the spinner
never clears — permanent spinner with no dismiss path short of navigating away and back.

Inherent limitation of plain `Linking.openURL` (vs `expo-web-browser.openAuthSessionAsync`).
**Acceptable for v1.17.0. Fix in v1.18.0:** add AppState `change` listener — when app returns to
foreground and `oauthLoading` still true with no pending deep link, clear spinner after short delay.

---

## Quality Checklist

- ✅ API layer follows exact `auth.ts` pattern (typed interfaces, `apiFetch` wrapper)
- ✅ Store follows `settingsStore.ts` Zustand pattern (silent error on loadStatus, re-throw on disconnect)
- ✅ Deep link listener properly attached/detached (addEventListener + sub.remove() cleanup)
- ✅ State JWT verified before token exchange (CSRF protection preserved)
- ✅ isLoading = loading || oauthLoading prevents double-tap correctly
- ✅ Disconnect shows confirmation Alert with destructive style
- ✅ Connected Accounts row in Group 2 (data/integrations group per spec)
- ✅ Row shows MS email as value prop when connected
- ✅ Navigation registered with slide_from_right (consistent with Profile, AIUsageStats)
- ✅ msalauth://callback intent-filter inside singleTask MainActivity
- ✅ Scope pills (Mail, Calendar, Notes, Teams) display when connected
- ✅ versionCode 28, versionName 1.17.0 consistent across build.gradle + package.json + SettingsScreen

---

## Verdict: PASS ✅

v1.17.0 ready to build. W1 tracked for v1.18.0.
