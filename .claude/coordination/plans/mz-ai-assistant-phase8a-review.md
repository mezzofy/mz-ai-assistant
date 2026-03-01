# Quality Gate Review: Phase 8A
**Reviewer:** Lead Agent
**Date:** 2026-02-28
**Phase:** 8A (Mobile API Layer + Auth Integration)
**Files Reviewed:** 10 (4 created, 4 replaced/rewritten, 2 patched)

---

## Gate Criteria vs Results

| Criterion | Required | Actual | Status |
|-----------|----------|--------|--------|
| Login hits real `/auth/login` | Yes | `loginApi()` → `POST /auth/login` | ✅ PASS |
| JWT tokens stored persistently | AsyncStorage | `saveTokens()` via `multiSet` | ✅ PASS |
| Token refresh auto-happens on 401 | Yes | `apiFetch` retries once after refresh | ✅ PASS |
| Session restore on app launch | Yes | `App.tsx useEffect → loadStoredUser()` | ✅ PASS |
| Logout hits real server | Yes | `logoutApi(refreshToken)` → `POST /auth/logout` | ✅ PASS |
| Token cleared on logout | Yes | `clearTokens()` called, state reset | ✅ PASS |
| Error states handled | Yes | Red error banner in LoginScreen; session expiry message | ✅ PASS |
| No `DEMO_USER` in auth code paths | None | Removed — `user` is `UserInfo \| null` | ✅ PASS |
| No `setTimeout()` mocking auth | None | Removed — real async `loginWithCredentials` | ✅ PASS |
| TypeScript — no `any` in API layer | Zero `any` | Zero — all generics typed | ✅ PASS |
| API responses typed to server shapes | Yes | `LoginResponse`, `UserInfo`, `RefreshResponse` | ✅ PASS |

---

## File-by-File Assessment

### `APP/src/config.ts` ✅ PASS
- Platform-aware URL selection: Android `10.0.2.2`, iOS `localhost` — correct
- `__DEV__` global used correctly (no import needed in RN)
- WS URL derived correctly from HTTP URL
- PROD URL placeholder is appropriate for dev phase

### `APP/src/storage/tokenStorage.ts` ✅ PASS
- `multiSet` / `multiRemove` for atomic batch operations — correct pattern
- Namespaced keys (`@mz_access_token`) avoid collision with other AsyncStorage users
- All four functions return correct Promise types
- No unnecessary complexity

### `APP/src/api/api.ts` ✅ PASS (with one observation — see below)
- Circular dep solution (callback registration) is clean and correct
- FormData guard for Content-Type is correctly placed
- `Object.setPrototypeOf` for `ApiError instanceof` — necessary for TS transpile, correct
- 204 early-return before `response.json()` — correct; prevents parse error on logout
- Retry-once pattern is safe — no infinite loop risk
- `_parseErrorMessage` handles both `detail` (FastAPI standard) and `message` fallback — matches server RFC 7807 format

### `APP/src/api/auth.ts` ✅ PASS
- `UserInfo.id: string` — matches server `"id"` field (confirmed from plan: both `/auth/login` and `/auth/me` return `id`)
- `loginApi` uses `skipAuth: true` — correct, no token exists at login time
- `logoutApi` does NOT use `skipAuth` — correct, server requires `Depends(get_current_user)`
- `refreshTokenApi` uses `skipAuth: true` — correct, calling with potentially expired token
- Comment on `user_info` redundancy (no extra `/auth/me` round trip needed) — good

### `APP/src/stores/authStore.ts` ✅ PASS (with one minor correctness issue — see below)
- `registerUnauthorizedHandler` called at module init time — correct, runs before any API call
- `loginWithCredentials` sets `loading: true` before async, `loading: false` on both success and catch — correct
- `logout` is best-effort for server call (swallowed catch) — correct design; local logout always proceeds
- `login: () => set({isLoggedIn: true})` legacy alias retained — safe backward compat
- `clearError` action present — used correctly by LoginScreen before each attempt

### `APP/src/screens/LoginScreen.tsx` ✅ PASS
- Hardcoded credentials (`sarah@mezzofy.com` / `password123`) removed — correct
- Local `loading` state removed — driven by `authStore.loading` — correct
- `clearError()` called before each login attempt — correct (prevents stale error on retry)
- Guard `!email.trim() || !password` prevents empty submits — correct
- Error banner renders below form fields, above button — sensible UX placement
- `autoCorrect={false}` on email field — good addition vs original

### `APP/App.tsx` ✅ PASS
- `useEffect(() => { loadStoredUser(); }, [loadStoredUser])` — correct React pattern
- `loadStoredUser` in effect dependency array — correct (stable reference from Zustand)
- No flash of login screen before session restore check: `isLoggedIn` starts `false`, then `loadStoredUser` sets it — **small UX concern** (see observation below; not a blocker)

### `APP/src/screens/SettingsScreen.tsx` ✅ PASS
- `if (!user) return null` — correct null guard before user data access
- `onPress={() => { logout(); }}` — void wrapper satisfies `RowProps.onPress: () => void` — correct
- Pre-existing `BRAND.accentSoft` reference (line 93) noted in plan, intentionally not fixed — acceptable per plan scope

### `APP/src/screens/ChatScreen.tsx` ✅ PASS
- `if (!user) return null` at line 14 — correct placement after user selector, before destructuring
- No further changes in this session — DEMO_RESPONSES left for 8B intentionally

---

## Issues Found

### ISSUE-1 (Minor, non-blocking): Stale `accessToken` in Zustand state after silent refresh

**Location:** `authStore.ts:loadStoredUser()` lines 77–91

**Problem:** If `getMeApi()` triggers an auto-refresh in `api.ts` (because the stored access token is expired but refresh token is still valid), `api.ts` correctly persists the new access token to AsyncStorage via `saveTokens(newAccess, oldRefresh)`. However, `loadStoredUser()` then reads `storedRefresh = await getRefreshToken()` (correct) but sets `accessToken: storedAccess` — the OLD expired token — in Zustand state.

**Impact:** Low in practice. `apiFetch` always reads from AsyncStorage directly (not from `authStore.accessToken`), so all subsequent API calls use the correct new token. No current screen reads `authStore.accessToken` directly. The stale value in state is never acted upon.

**Fix (for 8B):** After `getMeApi()` returns, re-read the access token from storage:
```typescript
const freshAccess = await getAccessToken(); // re-read after possible refresh
set({
  isLoggedIn: true,
  user: userInfo,
  accessToken: freshAccess,         // not storedAccess
  refreshToken: storedRefresh,
});
```

**Severity:** Low — cosmetic incorrectness in state. No functional breakage. Fix is 1-line. Mobile Agent should fix at start of Session 8B.

---

### OBSERVATION-1 (Not a bug): Login screen flash on cold start

**Detail:** On cold start, `isLoggedIn` is `false` so Login screen renders briefly before `loadStoredUser()` completes the AsyncStorage read (~50–100ms). User sees a brief flash of the Login screen before being navigated to MainTabs.

**Standard solution:** A loading/splash state (`isInitializing: boolean`) in authStore. Not required for Phase 8 — acceptable for v1.0. Flag for Phase 10 (UX polish).

---

### OBSERVATION-2 (Known, accepted): `BRAND.accentSoft` undefined in SettingsScreen

Noted in plan as a pre-existing bug. Not introduced by Session 8A. Does not affect auth flow. Leave for dedicated UX polish pass.

---

## Summary

| Category | Count | Verdict |
|----------|:-----:|---------|
| ✅ Pass | 10/10 files | All deliverables correct |
| ⚠️ Minor issues | 1 | Stale `accessToken` in Zustand after silent refresh (low severity, easy 1-line fix) |
| 🔵 Observations | 2 | Login flash (UX), accentSoft undefined (pre-existing) |
| ❌ Blockers | 0 | None |

---

## Decision: ✅ PASS — Proceed to Phase 8B

Phase 8A quality gate is **PASSED**. The API foundation is solid:
- Auth client layer is cleanly separated and correctly typed
- Circular dependency handled elegantly without hacks
- Token persistence and refresh are correct
- Session restore works on app launch
- Error flow is correct (banners, cleared on retry, session expiry)

**Required before 8B:**
1. Fix ISSUE-1 (stale `accessToken`) at start of 8B — 1-line change in `loadStoredUser()`

**Not required before 8B:**
- Tester xfail cleanup (doesn't affect mobile work)
- Login screen flash (UX polish, not blocking)
- `BRAND.accentSoft` (pre-existing, unrelated)

---

## Next: Phase 8B Instructions for Mobile Agent

Session 8B scope (from `mz-ai-assistant-phase8-plan.md`):
1. Fix ISSUE-1 first (1-line in `authStore.ts:loadStoredUser`)
2. Create `APP/src/api/chat.ts` — `sendText`, `sendMedia`, `sendUrl`, `getSessions`, `getHistory`
3. Create `APP/src/api/websocket.ts` — WS manager for `/chat/ws?token=JWT`
4. Update `APP/src/stores/chatStore.ts` — add `sessionId`, `sendToServer()`, `loadHistory()`, `loadSessions()`
5. Update `APP/src/screens/ChatScreen.tsx` — replace `DEMO_RESPONSES` + `setTimeout` with real `chatStore.sendToServer()`

**Server contracts for 8B:**
```
POST /chat/send        {message, session_id?}               → {session_id, message_id, response, artifacts, tools_used}
POST /chat/send-media  multipart: file + message + session_id? → same shape
POST /chat/send-url    {url, message?, session_id?}         → same shape
GET  /chat/sessions    Bearer                               → [{session_id, title, message_count, last_activity}]
GET  /chat/history/{id} Bearer                              → {session_id, messages: []}
WS   /chat/ws?token=JWT → streaming: {type, status, data}
```
