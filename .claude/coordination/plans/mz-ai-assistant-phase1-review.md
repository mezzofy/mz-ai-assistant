# Review: Backend Agent — Phase 1 (Auth + Security Layer)
**Reviewer:** Lead Agent
**Date:** 2026-02-27
**Verdict:** ✅ PASS (after fixes)

**Fix verification (2026-02-27):**
- ✅ `auth.py:100` — `_rl: None = Depends(rate_limit_auth)` present on login endpoint
- ✅ `auth.py:155` — `_rl: None = Depends(rate_limit_auth)` present on refresh endpoint
- ✅ `main.py:100-108` — ChatGatewayMiddleware registered first (innermost), CORSMiddleware registered second (outermost)
- ✅ `gateway.py` — `_BYPASS_PREFIXES` wired into dispatch logic
- ✅ `rate_limiter.py` — ZADD uses unique `uuid4().hex[:8]` suffix

**Original verdict:** REVISE

---

## Files Reviewed

| File | Role |
|------|------|
| `server/app/core/database.py` | SQLAlchemy async engine + session |
| `server/app/core/auth.py` | JWT creation, bcrypt, Redis blacklist |
| `server/app/core/rbac.py` | RBAC from roles.yaml |
| `server/app/core/dependencies.py` | FastAPI Depends factories |
| `server/app/core/rate_limiter.py` | Redis sliding window rate limit |
| `server/app/core/audit.py` | Async audit log |
| `server/app/api/auth.py` | /auth/* endpoints |
| `server/app/main.py` | FastAPI app entry point |
| `server/app/gateway.py` | /chat/* middleware |

---

## Findings

### 🔴 Blockers

**1. `server/app/api/auth.py:94-98` — Login endpoint missing brute-force protection**

The `rate_limit_auth` dependency (IP-based, 10 req/min) is defined in `rate_limiter.py` but never applied to the `/auth/login` endpoint. The login endpoint has zero rate limiting. An attacker can make unlimited password guessing attempts. This directly violates SECURITY.md brute-force protection requirements.

**Fix required (Backend Agent):**
Add `Depends(rate_limit_auth)` to the `login()` endpoint in `server/app/api/auth.py`.

The `/auth/refresh` endpoint should also get the same protection since repeated refresh attempts could be used to probe token validity.

---

### 🟡 Warnings

**1. `server/app/main.py:98-106` — Middleware registration order**

In Starlette/FastAPI, `app.add_middleware()` inserts at position 0 of the middleware stack. This means the **last-added middleware is outermost** (runs first on requests). Current order:
```
app.add_middleware(CORSMiddleware)       # added first → runs SECOND
app.add_middleware(ChatGatewayMiddleware) # added second → runs FIRST
```
Result: `ChatGatewayMiddleware → CORSMiddleware → routes`

For browser clients making cross-origin requests to `/chat/*`, HTTP OPTIONS preflight requests (which have no Authorization header) will be rejected with 401 before CORSMiddleware can respond. The mobile app (React Native) is unaffected since it doesn't trigger CORS preflight. However, Swagger UI at `/docs` and any future web dashboard would be impacted.

**Fix recommended (Backend Agent):** Swap the registration order so CORSMiddleware is outermost:
```python
app.add_middleware(ChatGatewayMiddleware)  # registered first → innermost
app.add_middleware(CORSMiddleware, ...)    # registered second → outermost
```

**2. `server/app/gateway.py:41-49` — `_BYPASS_PREFIXES` is dead code**

The `_BYPASS_PREFIXES` tuple is defined but never referenced inside `dispatch()`. The bypass logic is implemented inline as `if not path.startswith("/chat/") or path == "/chat/ws"`. The tuple definition is misleading — it implies a list-based check that doesn't exist. Remove the unused variable or wire it into the dispatch check.

**3. `server/app/core/rate_limiter.py:60` — ZADD member collision under concurrent load**

The sliding window uses `{str(now_ms): now_ms}` as the Redis ZADD mapping. If two requests arrive at the exact same millisecond, the second `zadd` overwrites the first (same key), causing the rate limiter to undercount. Under normal mobile app load, millisecond-level collisions are rare. Under stress testing or concurrent burst requests, the limiter may allow slightly more than the limit.

**Fix recommended:** Use a unique member per request, e.g., `{f"{now_ms}:{uuid4().hex[:8]}": now_ms}`.

---

### 🟢 Suggestions

**1. `server/app/core/rbac.py:16` — Document the lru_cache restart requirement**

`@lru_cache(maxsize=1)` loads `roles.yaml` once at first call and never re-reads it. If a role's permissions are changed in `roles.yaml`, the server must be restarted. This is acceptable for a production service but should be noted in the deployment runbook.

**2. `server/app/core/audit.py:30-31` — Consider a PII redaction helper**

The `details` parameter accepts any dict. The docstring says "redact PII before passing" but there's no enforcement. Sensitive data (email addresses, phone numbers, names) could end up in the 90-day audit log. Consider a `_redact(d: dict) -> dict` helper that strips known PII field names.

---

## Quality Gate Status

| Criterion | Status | Notes |
|-----------|--------|-------|
| POST /auth/login returns JWT pair | ✅ | Login flow complete with enrich_user_with_permissions |
| Protected endpoints reject 401 without token | ✅ | HTTPBearer + decode_access_token in get_current_user() |
| RBAC denies out-of-scope roles | ✅ | require_role() + require_permission() factories work correctly |
| 429 on rate limit (chat) | ✅ | ChatGatewayMiddleware applies 30/min per user |
| 429 on rate limit (auth) | ❌ | rate_limit_auth defined but NOT applied to login endpoint |
| /health returns DB + Redis status | ✅ | Returns degraded/ok with service status dict |

---

## Summary

Phase 1 is structurally solid. The database layer, JWT system, RBAC, and gateway middleware are all implemented correctly and follow the spec. The core authentication flow (login → tokens → protected endpoints → logout) works as designed.

**One security blocker must be fixed before Phase 2 can begin:** The login endpoint has no brute-force protection. An attacker can attempt unlimited password guesses. This is a trivial 3-line fix but is required before Phase 2.

The middleware ordering warning (🟡 #1) should also be fixed since it will break Swagger UI CORS — recommended to fix alongside the blocker.

---

## Next Steps

1. **Backend Agent** — Fix the 2 items before Phase 2:
   - 🔴 Add `Depends(rate_limit_auth)` to `/auth/login` (and `/auth/refresh`) in `server/app/api/auth.py`
   - 🟡 Swap middleware registration order in `server/app/main.py`
   - Optional: Fix `_BYPASS_PREFIXES` dead code and ZADD collision

2. After Backend Agent confirms fixes → Lead Agent updates quality gate → **PASS → Phase 2**

3. Phase 2 can then begin: `/boot-backend` → MS Graph tools (Outlook + Teams + Push) + Document tools (PDF/PPTX/DOCX/CSV)
