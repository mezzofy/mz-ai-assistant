# Context Checkpoint: Tester Agent
**Date:** 2026-03-13
**Project:** mz-ai-assistant
**Session:** Auth Security OTP — test regression fixes
**Context:** ~20% at checkpoint
**Reason:** Task complete

---

## Assigned Task

Fix test failures caused by the breaking change to `POST /auth/login` (now returns `otp_required` instead of JWT tokens).

**Failing tests from regression run:**
- `test_auth.py::TestLogin` — 3 tests (expected JWT, got `otp_required`)
- `test_e2e_mobile.py::TestMobileAuthFlow` — 3 tests (login helper returned wrong shape)
- `test_e2e_mobile.py::TestMobileChatFlow` — 2 tests (auth setup broken)
- `test_e2e_mobile.py::TestMobileFilesFlow` — 3 tests (auth setup broken)

---

## Completed This Session

| # | File | Change | Status |
|---|------|--------|--------|
| 1 | `server/tests/test_auth.py` | `TestLogin` 3 tests updated to assert `otp_required` + `otp_token` | ✅ Done locally |
| 2 | `server/tests/test_e2e_mobile.py` | `_login()` helper rewritten to 2-step OTP flow via Redis db=15 | ✅ Done locally |

---

## Changes Detail

### `test_auth.py` — TestLogin (3 tests)

All 3 tests updated to match new `/auth/login` → `otp_required` response:

- `test_login_valid_credentials` — now has `mock_otp_store, mock_email_sender` fixtures; asserts `data["status"] == "otp_required"` and `"otp_token" in data`
- `test_login_returns_permissions_in_user_info` — now has `mock_otp_store, mock_email_sender` fixtures; asserts `otp_required` (permissions come from `/auth/verify-otp` after OTP, not login)
- `test_login_access_token_is_valid_jwt` — renamed in spirit: now verifies `otp_token` is a UUID (no `.` separators), not a JWT

### `test_e2e_mobile.py` — `_login()` helper

New 2-step flow:
```python
async def _login(client, email, password) -> dict:
    # Step 1: POST /auth/login → otp_token
    step1 = await client.post("/auth/login", json={"email": email, "password": password})
    otp_token = step1.json()["otp_token"]

    # Step 2: Read OTP from Redis test DB (db=15, set by conftest REDIS_URL)
    async with aioredis.from_url("redis://localhost:6379/15", decode_responses=True) as r:
        raw = await r.get(f"login_otp:{otp_token}")
    code = json.loads(raw)["code"]

    # Step 3: POST /auth/verify-otp → JWT tokens
    step3 = await client.post("/auth/verify-otp", json={"otp_token": otp_token, "code": code})
    return step3.json()
```

**Why this works in tests:**
- `mock_rate_limiter` covers `/auth/login` and `/auth/verify-otp` (both have `Depends(rate_limit_auth)`)
- `mock_db_get_user` patches `_get_user_by_email` in both `/auth/login` and `/auth/verify-otp`
- OTP is stored in REAL Redis db=15 (env var `REDIS_URL=redis://localhost:6379/15`)
- `otp.py` reads `REDIS_URL` env var → stores in db=15 → `_login()` reads from db=15 ✅
- Email send fails silently (`try/except` in auth.py) — no MS Graph config in test env ✅
- `mock_otp_store` is NOT used in E2E tests — OTP uses real Redis

---

## Pre-existing Failures (NOT our responsibility)

| Test | Root Cause | Action |
|------|-----------|--------|
| `test_integration_research_task.py` | BUG-014: Anthropic key exhausted until 2026-04-01 | None (pre-existing) |
| `test_security.py::TestPathTraversal::test_windows_path_traversal_stripped` | Windows-only path test on Linux EC2 | None (pre-existing) |
| `test_sales_lead_automation.py` (5 tests) | Pre-existing failures unrelated to auth change | None (pre-existing) |

---

## Action Required (by user)

The local files are already correct. They just need to be pushed to GitHub and pulled on EC2:

**Step 1 — Commit locally:**
```bash
git add server/tests/test_auth.py server/tests/test_e2e_mobile.py
git commit -m "test(auth): update TestLogin + E2E login helper for OTP 2-step flow"
```

**Step 2 — Push via GitHub Desktop to `eric-design` branch**

**Step 3 — Pull on EC2 and re-run:**
```bash
ssh -i mz-ai-key.pem ubuntu@3.1.255.48
cd /home/ubuntu/mz-ai-assistant && git pull origin eric-design
cd server
venv/bin/pytest tests/test_auth.py tests/test_e2e_mobile.py -v 2>&1 | tail -30
```

**Expected result:** The 11 previously-failing tests should now pass.

---

## Resume Instructions (if more work)

After /clear, load in order:
1. `CLAUDE.md`
2. `.claude/agents/tester.md`
3. `.claude/skills/test-automation-engineer.md`
4. `.claude/coordination/memory.md`
5. `.claude/coordination/status/tester.md` (this file)
