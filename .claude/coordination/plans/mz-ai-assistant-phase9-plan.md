# Plan: Phase 9 — E2E Tests
**Workflow:** change-request (adding E2E test coverage for mobile API flows)
**Date:** 2026-02-28
**Created by:** Lead Agent
**Agent:** Tester Agent (`/boot-tester`)

---

## Goal

Validate the complete mobile API flows end-to-end using the server's test infrastructure. Phase 7 covered unit + integration tests per endpoint. Phase 9 covers **multi-step E2E flows** that match what the mobile app does in real use: login → chat → check files → logout.

Also perform the pending **xfail cleanup** from Phase 7 (BUG-001 is fixed — the xfail is obsolete).

---

## Task Breakdown

| # | Task | File(s) | Priority |
|---|------|---------|----------|
| 1 | **xfail cleanup** | `server/tests/test_auth.py` | High |
| 2 | **Verify base suite** | Run `pytest tests/ -q` | High |
| 3 | **E2E: Auth flow** | `server/tests/test_e2e_mobile.py` (new) | High |
| 4 | **E2E: Chat flow** | `server/tests/test_e2e_mobile.py` | High |
| 5 | **E2E: Files flow** | `server/tests/test_e2e_mobile.py` | High |
| 6 | **Final suite run** | All tests | High |

---

## Task 1: xfail Cleanup

**File:** `server/tests/test_auth.py`
**Action:** Find and remove the `@pytest.mark.xfail(strict=True, reason="BUG in app/core/auth.py...")` decorator (and any blank lines following it) from `TestRefreshToken::test_refresh_valid_token`.

**Why:** BUG-001 was fixed in `app/core/auth.py` — `_build_payload()` now uses `user.get("id") or user.get("user_id")`. The xfail decorator was intentionally strict (`strict=True`) to catch when the fix lands. After removal, the test should PASS (not xpass, just pass).

**Expected result after fix:** The test that was xfail now passes normally. `pytest tests/test_auth.py::TestRefreshToken -v` should show 4 PASSED.

---

## Task 2: Verify Base Suite

Run: `cd server && pytest tests/ -q --no-header`

**Expected:** 236 passed, 0 failed, 0 xfail (was: 235 passed + 1 xfail before xfail removal)

If any test fails (other than newly-un-xfailed test), investigate and document in Tester status file. Do NOT fix bugs in production code — file an issue.

---

## Task 3–5: E2E Mobile Flow Tests

**New file:** `server/tests/test_e2e_mobile.py`

These tests use the existing FastAPI `TestClient` infrastructure. They simulate the exact sequence of API calls the mobile app makes.

### Test Classes to Write

**Class: `TestMobileAuthFlow`**
Tests the full auth lifecycle (matches `authStore.ts` + `LoginScreen.tsx` behavior):

```
test_login_and_get_me
  1. POST /auth/login with valid credentials
  2. Extract access_token + refresh_token from response
  3. GET /auth/me with access_token
  4. Assert user fields: id, email, name, role, department, permissions

test_token_refresh_flow
  1. POST /auth/login
  2. POST /auth/refresh with refresh_token
  3. Assert new access_token returned
  4. GET /auth/me with new access_token (confirm it works)

test_logout_requires_auth
  1. POST /auth/login → get tokens
  2. POST /auth/logout with Bearer token + refresh_token body
  3. Assert 200/204 response

test_expired_token_rejected
  1. GET /auth/me with invalid token → assert 401
```

**Class: `TestMobileChatFlow`**
Tests the chat workflow (matches `chatStore.ts` `sendToServer` + `loadSessions` + `loadHistory`):

```
test_send_text_and_get_session
  1. POST /auth/login → access_token
  2. POST /chat/send {message: "Hello"} → assert session_id returned
  3. GET /chat/sessions → assert session in list
  4. GET /chat/history/{session_id} → assert message in history

test_send_url_message
  1. POST /auth/login → access_token
  2. POST /chat/send-url {url: "https://example.com"} → assert response

test_chat_requires_auth
  1. POST /chat/send without Bearer token → assert 401/403
```

**Class: `TestMobileFilesFlow`**
Tests the files workflow (matches `files.ts` `listFilesApi` + `deleteFileApi`):

```
test_list_files_empty_for_new_user
  1. POST /auth/login → access_token
  2. GET /files/ → assert {artifacts: [], count: 0} or similar empty state

test_upload_and_list_file
  1. POST /auth/login → access_token
  2. POST /files/upload with a small test file (multipart)
  3. GET /files/ → assert file appears in artifacts list
  4. Assert artifact has: id, filename, file_type, download_url, created_at

test_delete_file
  1. POST /auth/login → access_token
  2. POST /files/upload → get artifact_id
  3. DELETE /files/{artifact_id} → assert {deleted: true}
  4. GET /files/ → assert file no longer in list

test_files_require_auth
  1. GET /files/ without Bearer token → assert 401/403
```

---

## API Contract Verification

While writing E2E tests, verify the mobile app's assumed response shapes match what the server actually returns:

| Mobile Assumption | Endpoint | Check |
|------------------|----------|-------|
| `user_info.id` in login response | POST /auth/login | Assert response has `user_info.id` (not `user_id`) |
| `session_id` in chat response | POST /chat/send | Assert `session_id` field exists |
| `artifacts` array in chat response | POST /chat/send | Assert `artifacts` is a list |
| `sessions` array in sessions response | GET /chat/sessions | Assert `sessions` field + `session_id` per item |
| `messages` array in history | GET /chat/history/{id} | Assert `messages` + `role`/`content`/`timestamp` per item |
| `artifacts` array in files | GET /files/ | Assert `artifacts` + `id`/`filename`/`file_type`/`download_url` |
| `artifact_id` in upload response | POST /files/upload | Assert `artifact_id` field |
| `deleted: true` in delete | DELETE /files/{id} | Assert `deleted` is true |

---

## Configuration Notes

- Use existing `conftest.py` test fixtures (auth headers, test client)
- If `TestClient` isn't sufficient for WS tests: document as out-of-scope, skip WS tests
- Write test results to `server/tests/results/e2e-report.md` — do NOT display full output in chat
- WS E2E tests (camera/speech) are **out of scope** for Phase 9 — complex to test without real media

---

## Expected Final Test Count

| Suite | Before Phase 9 | After Phase 9 |
|-------|---------------|---------------|
| test_auth.py | 235 pass + 1 xfail | 236 pass |
| test_e2e_mobile.py | 0 (new) | ~12–15 pass |
| All other test files | unchanged | unchanged |
| **Total** | **236 total** | **~248–251 pass, 0 fail** |

---

## After Completing Work

1. Write status to `.claude/coordination/status/tester.md`
2. Write test results summary to `server/tests/results/e2e-report.md`
3. Tell the human: "Tester tasks complete. Go back to Lead terminal for review."
