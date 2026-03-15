# Lead Review: Push Notifications v1.28.0
**Date:** 2026-03-16
**Reviewer:** Lead Agent
**Commit reviewed:** `cb9f58e` (FCM push notifications — 14 files)
**Verdict:** ✅ PASS (with one required action before APK build)

---

## Scope Reviewed

| File | Type | Verdict |
|------|------|---------|
| `server/scripts/migrate.py` | Backend | ✅ |
| `server/app/api/notifications.py` | Backend (NEW) | ✅ |
| `server/app/main.py` | Backend | ✅ |
| `server/app/tools/communication/push_ops.py` | Backend | ✅ |
| `server/app/tasks/tasks.py` | Backend | ✅ |
| `server/app/webhooks/scheduler.py` | Backend | ✅ |
| `server/app/tasks/beat_schedule.py` | Backend | ✅ |
| `APP/android/build.gradle` | Mobile | ✅ |
| `APP/android/app/build.gradle` | Mobile | ✅ |
| `APP/android/app/src/main/AndroidManifest.xml` | Mobile | ✅ |
| `APP/src/api/notificationsApi.ts` | Mobile (NEW) | ✅ |
| `APP/src/notifications/pushHandler.ts` | Mobile (NEW) | ✅ |
| `APP/src/stores/settingsStore.ts` | Mobile | ✅ |
| `APP/App.tsx` | Mobile | ✅ |
| `APP/src/stores/authStore.ts` | Mobile | ✅ |

---

## Findings

### 🔴 Blockers

**None.** (See Required Action below — not a code defect, a missing step.)

### 🟡 Warnings

**W1 — Version not bumped to v1.28.0**
- `APP/android/app/build.gradle` still has `versionCode 35 / versionName "1.26.0"`
- `APP/package.json` still on `1.26.0`
- `APP/src/screens/SettingsScreen.tsx` footer still on `v1.26.0`
- Firebase packages not yet in `node_modules` (`npm install` not yet run)
- **These must be done by Mobile agent before APK build.** Not a code defect — just the standard release step.

**W2 — No unit tests for `/notifications/*` endpoints**
- Three new REST endpoints have no corresponding test file
- All are simple CRUD — low risk, but consistent with project's >80% coverage goal
- Deferred to v1.29.0 or next Tester session. Non-blocking for this release.

### 🟢 Suggestions

**S1 — Minor summary duplication in `_run_chat_task`**
- `tasks.py` line ~538 computes `summary` for Redis, then line ~553 recomputes `_summary` for push — both truncate `task_data["message"]` to 60 chars
- Cosmetic duplication. Not worth a fix in this release.

**S2 — `setBackgroundMessageHandler` inside `initPushNotifications()`**
- RN Firebase docs recommend calling this at module top-level (outside any function)
- Current placement (inside `initPushNotifications`) means it only registers when the user is logged in AND notifications are enabled
- For this app's use case (user-authenticated push), this is acceptable — background notifications are only relevant to logged-in users anyway
- No action required.

---

## Detailed Findings (Passing Checks)

### Backend — notifications.py ✅
- All 3 endpoints authenticated via `Depends(get_current_user)` ✅
- All queries fully parameterized — no SQL injection risk ✅
- `ON CONFLICT (device_token) DO UPDATE` — correct upsert semantics; re-assigns token to new user on same device ✅
- `await db.commit()` present in all 3 handlers — no silent rollback ✅
- Input validation: `device_token` emptiness check + `platform` allowlist ✅
- `DELETE /unregister-device` with a body — technically non-standard HTTP but consistent with `apiFetch` mobile client and used elsewhere in this codebase ✅

### Backend — push_ops.py `get_user_push_targets()` ✅
- Opens own `AsyncSessionLocal` — no dependency on request-scoped session (correct for Celery context) ✅
- Checks `push_notifications_enabled` FIRST before fetching tokens — avoids unnecessary second query ✅
- Handles `pref_row is None` (unknown user) → returns `[]` ✅
- Full try/except — fails silently, never crashes Celery task ✅

### Backend — tasks.py `_run_agent_task` push block ✅
- `_uid_push != "system"` guard — static Beat jobs (weekly-kpi-report etc.) never trigger push ✅
- `_job_name` fallback chain: `workflow_name` → `_job_name` → `message[:40]` — graceful degradation ✅
- `_short_id` fallback: `job_id[:8].upper() or "TASK"` ✅
- `data` dict values are all strings — FCM requirement met ✅
- Wrapped in try/except — non-fatal ✅

### Backend — tasks.py `_run_chat_task` push block (success + failure) ✅
- DB-lookup replaces per-request `device_token` approach — correct architectural shift ✅
- Failure push: `for _t in await get_user_push_targets(user_id)` — correct awaiting before iteration ✅
- Failure handler has its own inner `try/except` — never masks the original exception ✅
- `raise` re-raises original exception correctly — Celery retry logic unaffected ✅

### Mobile — pushHandler.ts ✅
- `requestAndroidPermission()` API level guard (`Platform.Version < 33` → skip) ✅
- `messaging().getToken()` → `registerDevice()` → registers to backend ✅
- `onTokenRefresh` handler — handles FCM token rotation automatically ✅
- `unregisterPushDevice()` calls `getToken()` first — safe even if token was never obtained ✅
- Both functions non-fatal — Firebase failures never break login/logout flow ✅

### Mobile — authStore.ts logout ✅
- Dynamic `import('../notifications/pushHandler')` — avoids circular dep ✅
- Called BEFORE `clearTokens()` — access token still valid when unregister API call fires ✅
- Non-fatal catch — logout always completes regardless of push unregister result ✅

### Mobile — App.tsx useEffect ✅
- `[isLoggedIn, notifications]` deps — correctly re-fires if user enables notifications while logged in ✅
- `.catch(() => {})` — non-fatal ✅

### Mobile — Gradle + AndroidManifest ✅
- Google Services classpath `4.4.1` in root `build.gradle` ✅
- `apply plugin: 'com.google.gms.google-services'` in app `build.gradle` (after react plugin) ✅
- Firebase BoM `32.7.4` + `firebase-messaging` in app dependencies ✅
- `POST_NOTIFICATIONS` permission in manifest ✅
- `ReactNativeFirebaseMessagingService` service declared correctly ✅
- `google-services.json` placed at `APP/android/app/google-services.json` (commit `420d563`) ✅

---

## Required Action Before APK Build

Mobile agent must do **one session** to:

1. Run `npm install @react-native-firebase/app@^20.0.0 @react-native-firebase/messaging@^20.0.0` in `APP/`
2. Bump version to v1.28.0:
   - `APP/android/app/build.gradle`: `versionCode 36`, `versionName "1.28.0"`
   - `APP/package.json`: `"version": "1.28.0"`
   - `APP/src/screens/SettingsScreen.tsx`: footer → `v1.28.0`
3. Build release APK: `cd APP/android && ./gradlew assembleRelease`
4. Verify Logcat: `[Push] FCM token acquired` on app launch

---

## EC2 Deploy Steps (after APK verified)

```bash
cd /home/ubuntu/mz-ai-assistant && git pull
python server/scripts/migrate.py        # Creates user_devices + adds push_notifications_enabled column
sudo systemctl restart mezzofy-api.service
sudo systemctl restart mezzofy-celery.service
sudo systemctl restart mezzofy-beat.service
```

Verify:
```bash
sudo -u postgres psql -d mezzofy_ai -c "\d user_devices"
sudo -u postgres psql -d mezzofy_ai -c "SELECT push_notifications_enabled FROM users LIMIT 3;"
curl -X POST http://localhost:8000/notifications/register-device \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"device_token":"test-token","platform":"android"}'
# → {"registered": true}
```

---

## Summary

The v1.28.0 push notification implementation is **architecturally sound** and follows all established patterns:
- DB-lookup token approach (not per-request) is the right design
- `"system"` guard prevents Beat jobs from hitting push
- All push paths are non-fatal — no existing functionality can break
- Logout unregister is correctly ordered before token clearing

**The only action required is the version bump + npm install + APK build (Mobile agent, 1 session).**

**Backend is ready to deploy to EC2 immediately** (after git pull + migrate.py + service restarts).
