# Plan: Phase 8 — Mobile Integration
**Workflow:** change-request (wiring mock UI to real API)
**Date:** 2026-02-28
**Created by:** Lead Agent

---

## Goal

Replace all `DEMO_RESPONSES`, `setTimeout()` mock calls, and hardcoded data in `APP/` with real API calls to the `server/` FastAPI backend.

**Before Phase 8:** Mobile app is a fully functional UI prototype — all responses are fake
**After Phase 8:** Mobile app talks to the real server over HTTP/WebSocket

---

## Scope

**Files to wire up:**

| File | Current State | Phase 8 Change |
|------|--------------|----------------|
| `APP/src/stores/authStore.ts` | `login()` just sets boolean; uses `DEMO_USER` | Real `loginWithCredentials()`, token storage, refresh |
| `APP/src/stores/chatStore.ts` | No server calls | Add `sendToServer()`, `loadHistory()`, session tracking |
| `APP/src/screens/LoginScreen.tsx` | `setTimeout(() => login(), 1200)` | Real `POST /auth/login` call |
| `APP/src/screens/ChatScreen.tsx` | `setTimeout(() => DEMO_RESPONSES[dept], 2200)` | Real `POST /chat/send`, `POST /chat/send-media`, `POST /chat/send-url` |
| `APP/src/screens/FilesScreen.tsx` | Hardcoded `FILES` array | Real `GET /files/` |
| `APP/src/screens/HistoryScreen.tsx` | (likely hardcoded or empty) | Real `GET /chat/sessions` |
| `APP/src/screens/SettingsScreen.tsx` | Shows `DEMO_USER` data | Real `/auth/me`, real logout |
| `APP/src/screens/CameraScreen.tsx` | `setTimeout()` mock | Real WebSocket `/chat/ws` camera frames |

**New files to create:**

| File | Purpose |
|------|---------|
| `APP/src/api/api.ts` | Base fetch client with JWT auto-refresh interceptor |
| `APP/src/api/auth.ts` | login, logout, refresh, getMe |
| `APP/src/api/chat.ts` | sendText, sendMedia, sendUrl, getSessions, getHistory |
| `APP/src/api/files.ts` | listFiles, uploadFile, downloadFile, deleteFile |
| `APP/src/api/websocket.ts` | WebSocket manager for `/chat/ws` |
| `APP/src/storage/tokenStorage.ts` | Secure JWT storage (AsyncStorage with encryption) |

---

## Server API Contracts (from APP.md + actual implementation)

### Auth Endpoints
```
POST /auth/login       body: {email, password}        → {access_token, refresh_token, token_type, user_info}
POST /auth/refresh     body: {refresh_token}           → {access_token, token_type}
POST /auth/logout      body: {refresh_token}            → 204
GET  /auth/me          header: Bearer token            → {user_id, email, name, role, department, permissions}
```

### Chat Endpoints
```
POST /chat/send        body: {message, session_id?}    → {session_id, message_id, response, artifacts, tools_used}
POST /chat/send-media  multipart: file + message + session_id? → same
POST /chat/send-url    body: {url, message?, session_id?} → same
GET  /chat/sessions    header: Bearer                  → [{session_id, title, message_count, last_activity}]
GET  /chat/history/{id} header: Bearer                 → {session_id, messages: []}
WS   /chat/ws?token=JWT → WebSocket for streaming (status updates + camera + speech)
```

### Files Endpoints
```
POST /files/upload     multipart: media_file           → {artifact_id, filename, download_url}
GET  /files/           header: Bearer                  → {artifacts: [], count}
GET  /files/{id}       header: Bearer                  → file bytes (FileResponse)
DELETE /files/{id}     header: Bearer                  → {deleted: true}
```

---

## Task Breakdown

| Session | Tasks | Agent | Dependencies |
|---------|-------|-------|-------------|
| Pre-req | Remove xfail decorator from `test_auth.py` | Tester | BUG-001 fixed ✅ |
| **8A** | API layer + auth + token storage + LoginScreen + authStore | Mobile | Pre-req done |
| **8B** | Chat API + chatStore + ChatScreen (text/media/url/WebSocket) | Mobile | 8A |
| **8C** | FilesScreen + HistoryScreen + SettingsScreen + CameraScreen | Mobile | 8A |

---

## Session 8A Detailed Tasks

**Create `APP/src/api/api.ts`:**
- Base `apiFetch(path, options)` with:
  - Prepends `SERVER_BASE_URL` (read from config/env)
  - Attaches `Authorization: Bearer <access_token>` header
  - On 401 → auto-refresh token → retry once
  - On second 401 → call `authStore.logout()` (force re-login)

**Create `APP/src/api/auth.ts`:**
- `login(email, password)` → POST /auth/login
- `refreshToken(refresh_token)` → POST /auth/refresh
- `logout(refresh_token)` → POST /auth/logout
- `getMe()` → GET /auth/me

**Create `APP/src/storage/tokenStorage.ts`:**
- `saveTokens(access, refresh)` → AsyncStorage
- `getAccessToken()`, `getRefreshToken()`
- `clearTokens()`

**Update `APP/src/stores/authStore.ts`:**
- Add `loginWithCredentials(email: string, password: string): Promise<void>`
- Add `refreshAccessToken(): Promise<boolean>`
- Add `logout()` — calls real server + clears tokens
- Add `loadStoredUser()` — restore session on app restart
- Store: `accessToken`, `refreshToken`, `isLoggedIn`, `user`, `loading`, `error`

**Update `APP/src/screens/LoginScreen.tsx`:**
- Replace `setTimeout(() => login(), 1200)` with `await authStore.loginWithCredentials(email, password)`
- Show real error messages (invalid credentials, network error)

---

## Session 8B Detailed Tasks

**Create `APP/src/api/chat.ts`:**
- `sendText(message, sessionId?)` → POST /chat/send
- `sendMedia(file, message, sessionId?)` → POST /chat/send-media (multipart)
- `sendUrl(url, message, sessionId?)` → POST /chat/send-url
- `getSessions()` → GET /chat/sessions
- `getHistory(sessionId)` → GET /chat/history/{id}

**Create `APP/src/api/websocket.ts`:**
- `createWsConnection(token)` → WebSocket to `/chat/ws?token=JWT`
- Event handlers: `onStatusUpdate`, `onCameraResult`, `onComplete`
- `sendCameraFrame(base64Jpeg)` → WS message `{type: "camera_frame", data: ...}`
- Auto-reconnect on disconnect

**Update `APP/src/stores/chatStore.ts`:**
- Add `sessionId: string | null`
- Add `sendToServer(text, mode, mediaFile)` — calls appropriate chat API
- Add `loadHistory(sessionId)` — fetch and restore messages
- Add `loadSessions()` — for history screen
- On response: update messages + artifacts from real server data

**Update `APP/src/screens/ChatScreen.tsx`:**
- Replace `setTimeout(() => DEMO_RESPONSES[dept], ...)` with `chatStore.sendToServer()`
- Handle media uploads (image/video/audio/file) with real file picker
- Show real artifacts from API response
- Handle WS streaming status updates

---

## Session 8C Detailed Tasks

**Create `APP/src/api/files.ts`:**
- `listFiles()` → GET /files/
- `uploadFile(file)` → POST /files/upload
- `downloadFile(id)` → GET /files/{id}
- `deleteFile(id)` → DELETE /files/{id}

**Update `APP/src/screens/FilesScreen.tsx`:**
- Replace hardcoded `FILES` array with `GET /files/` on mount
- Show loading spinner
- Wire download button to real download

**Update `APP/src/screens/HistoryScreen.tsx`:**
- Load sessions from `chatStore.loadSessions()`
- Navigate to restored conversation on tap

**Update `APP/src/screens/SettingsScreen.tsx`:**
- User profile shows real data from `authStore.user` (loaded via `/auth/me`)
- Logout button calls real `authStore.logout()`

**Update `APP/src/screens/CameraScreen.tsx`:**
- Replace `setTimeout()` with real WebSocket camera frames
- Connect WS on camera open, disconnect on close
- Show real AI analysis results

---

## Configuration

The Mobile Agent must establish the `SERVER_BASE_URL` constant. Options:
- Development: `http://10.0.2.2:8000` (Android emulator → host machine)
- Production: `https://api.mezzofy.com` (actual EC2 server)
- Create `APP/src/config.ts` with the base URL + env detection

---

## Quality Gate (After Phase 8)

Lead Agent will review:
- [ ] No `DEMO_RESPONSES` or `DEMO_USER` remaining in active code paths
- [ ] No `setTimeout()` mocking API responses
- [ ] Login flow hits real `/auth/login` and stores JWT tokens
- [ ] Chat send hits real `/chat/send` (or media/url variants)
- [ ] Token refresh auto-happens on 401
- [ ] Files screen loads from real API
- [ ] Logout hits real endpoint and clears tokens
- [ ] Error states handled (network error, auth error, server error)
- [ ] TypeScript strict mode — no `any` types in API layer
- [ ] All API responses typed (match server response shapes)
