# Review: Backend Agent — MS Graph Personal Account (Delegated OAuth)
**Reviewer:** Lead Agent
**Date:** 2026-03-11
**Verdict:** ✅ PASS (with warnings — no blockers)

## Files Reviewed

| File | Type | Review |
|------|------|--------|
| `app/db/migrations/add_ms_oauth_tokens.sql` | Migration SQL | ✅ |
| `scripts/migrate.py` | Migration script | ✅ |
| `app/core/config.py` | Config constants | ✅ |
| `config/config.example.yaml` | Config template | ✅ |
| `app/services/ms_token_service.py` | Service layer | ✅ w/ warnings |
| `app/api/ms_oauth.py` | API controller | ✅ w/ warnings |
| `app/tools/communication/personal_ms_ops.py` | Tools (18) | ✅ w/ warnings |
| `app/tools/tool_executor.py` | Registration | ✅ |
| `app/main.py` | Router registration | ✅ |
| `docs/ms_oauth_mobile_integration.md` | Mobile guide | ✅ |

---

## Findings

### 🔴 Blockers
*None.*

---

### 🟡 Warnings

**W1 — Dead `db` dependency parameter in `oauth_callback`**
`app/api/ms_oauth.py:144`
```python
async def oauth_callback(
    body: CallbackRequest,
    current_user: dict = Depends(get_current_user),
    db: DBSession = None,   # ← never used; always None
):
```
`db` is declared as `DBSession = None` — not `Depends(get_db)` — so FastAPI never injects a session. The function body correctly creates its own sessions via `AsyncSessionLocal()`. The parameter is harmless but misleading to future readers. The `DBSession` import in `ms_oauth.py` is also unused as a result.
**Recommendation:** Remove `db: DBSession = None` parameter and the `DBSession` import from `ms_oauth.py`.

---

**W2 — Synchronous MSAL calls block the async event loop**
`app/api/ms_oauth.py:127–133` and `app/services/ms_token_service.py:230–239`

`msal.ConfidentialClientApplication.get_authorization_request_url()` and `acquire_token_by_refresh_token()` are **synchronous** network calls. When called from `async def` handlers, they block the uvicorn event loop for the duration of the MSAL call (typically 200–500ms per network round-trip).

For the current deployment profile (small team, EC2 single-instance), this is acceptable — the chance of concurrent MSAL calls is low. However, under any real load this will degrade all concurrent requests.
**Recommendation for v1.1:** Wrap MSAL calls in `await asyncio.get_event_loop().run_in_executor(None, msal_fn, *args)`. File a follow-up item.

---

**W3 — `filter` parameter name shadows Python builtin**
`app/tools/communication/personal_ms_ops.py:454`
```python
async def _read_emails(self, user_id: str, folder: str = "inbox", limit: int = 10, filter: str = None) -> dict:
```
`filter` is a Python builtin. While functionally harmless (the local param shadows the builtin only within this method), it's a style violation that can confuse linters and future readers.
**Recommendation:** Rename parameter to `odata_filter` (and update the tool definition `properties` key to `"odata_filter"` to match).

---

**W4 — Concurrent token refresh race condition (known v1.0 limitation)**
`app/services/ms_token_service.py:186–211`

If two requests for the same user arrive simultaneously when their token is expired, both will read the expired token, both will try to refresh it. Microsoft uses refresh token rotation — the second refresh attempt will use the rotated (now-invalid) refresh token and fail with `invalid_grant`. The user would need to reconnect.

This is low-risk for a mobile app (typically one active session), but worth documenting.
**Recommendation:** Add a Redis distributed lock around the refresh flow in v1.1. For now, document in `memory.md` as a known v1.0 limitation.

---

### 🟢 Suggestions

**S1 — Remove unused `List` import from typing**
`app/core/config.py:18`
```python
from typing import Optional, List
```
Python 3.9+ supports `list[str]` natively. The `List` alias from `typing` is legacy. Non-blocking, cosmetic.

**S2 — Add input validation to `CallbackRequest`**
`app/api/ms_oauth.py:44–46`
```python
class CallbackRequest(BaseModel):
    code: str
    state: str
```
Adding `min_length=1` to both fields would reject empty string payloads before they reach MSAL. Low priority since MSAL would reject them anyway.

---

## Backend Checklist Results

| Check | Result |
|-------|--------|
| CSR pattern: Controller → Service → Repository | ✅ Clean separation |
| Co-located models (no standalone `models/`) | ✅ |
| OAuth2 authentication on all endpoints | ✅ All 4 endpoints use `Depends(get_current_user)` |
| Input validation in controller layer | ✅ `CallbackRequest` Pydantic DTO |
| Business logic in service layer | ✅ Token refresh, encrypt/decrypt all in `ms_token_service.py` |
| Parameterized queries (SQL injection prevention) | ✅ All SQL uses `:param` style |
| Error handling with proper HTTP status codes | ✅ 503 (unconfigured), 400 (bad code/state), 403 (CSRF) |
| Types/interfaces for Mobile consumption | ✅ `ms_oauth_mobile_integration.md` covers all 4 endpoints |
| Security: tokens encrypted at rest | ✅ Fernet AES-128-CBC with HMAC |
| Security: CSRF protection on callback | ✅ State JWT with 10-min expiry + user_id verification |
| Security: `MS_TOKEN_FERNET_KEY` missing = hard fail | ✅ `RuntimeError` raised, not silent bypass |
| Tool count matches spec (18) | ✅ 4 email + 5 calendar + 4 notes + 5 teams = 18 |
| All tools audit-logged | ✅ Every handler calls `self._audit()` on success |
| Friendly no-account UX | ✅ `MSNotConnectedException` → "connect in Settings" message |
| Lazy inline imports (established pattern) | ✅ httpx, MSNotConnectedException imported inside handlers |
| `existing outlook_ops.py / teams_ops.py` unmodified | ✅ Confirmed |

---

## Deployment Prerequisites

These are **ops tasks**, not code issues. Must be done before mobile team can use the feature:

| # | Task | Command / Action |
|---|------|-----------------|
| 1 | Create `ms_oauth_tokens` table on EC2 | `cd /home/ubuntu/mz-ai-assistant/server && venv/bin/python scripts/migrate.py` |
| 2 | Generate Fernet key | `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| 3 | Add `MS_TOKEN_FERNET_KEY=<generated>` to EC2 `.env` | Edit `/home/ubuntu/mz-ai-assistant/server/config/.env` |
| 4 | Add `MS365_DELEGATED_REDIRECT_URI=msalauth://callback` to EC2 `.env` | Edit same `.env` file |
| 5 | Restart service | `sudo systemctl restart mezzofy-api.service` |
| 6 | Azure AD app registration | Add delegated permissions + `msalauth://callback` redirect URI (see `docs/ms_oauth_mobile_integration.md` §8) |

---

## Summary

The implementation is **functionally correct, secure, and follows all established project patterns**. The four warnings are non-blocking for v1.0:

- **W1** (dead `db` param) — cosmetic cleanup, backend agent can fix in next session
- **W2** (blocking MSAL calls) — acceptable for current load; schedule for v1.1
- **W3** (`filter` name) — cosmetic; rename to `odata_filter` in next session
- **W4** (refresh race) — document as known v1.0 limitation

## Next Steps

- [ ] **Backend Agent** (optional, low priority): Fix W1 (remove dead `db` param) and W3 (rename `filter`) — can be batched with next mobile-related backend work
- [ ] **Ops** (required before mobile can use feature): Execute the 6 deployment prerequisites above
- [ ] **Mobile Agent**: Build the "Connected Accounts" Settings UI using `docs/ms_oauth_mobile_integration.md` as the spec
- [ ] **Lead**: Update `memory.md` with W4 (refresh race) as documented v1.0 limitation
