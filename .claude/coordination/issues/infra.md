# Infra Agent Issues

## ISSUE-001 (2026-03-12) — BUG-014: Anthropic API Key Monthly Limit Exhausted

**Priority:** P1 — Chat is completely broken for all users
**Raised by:** Lead Agent (investigation)
**Status:** OPEN — awaiting user action (key replacement or limit increase needed)

### Root Cause

The `ANTHROPIC_API_KEY` in EC2 `.env` has exhausted its monthly Anthropic usage limit.
Confirmed from `mezzofy-api.service` logs starting 2026-03-11 16:32:

```
Error code: 400 - You have reached your specified API usage limits.
You will regain access on 2026-04-01 at 00:00 UTC.
```

**This is NOT a v1.18.0 code bug** — coincidental timing only. The ChatScreen, chatStore.ts, and api/chat.ts are identical to v1.17.1.

### Fix (User Action Required)

Option A — Replace API key (fastest):
1. Get a new Anthropic API key from console.anthropic.com
2. SSH: `nano /home/ubuntu/mz-ai-assistant/server/config/.env`
3. Replace `ANTHROPIC_API_KEY=sk-ant-api03-KIC5...` with the new key
4. `sudo systemctl restart mezzofy-api.service`

Option B — Increase spending limit on current Anthropic account:
1. Go to console.anthropic.com → Billing → raise usage limit
2. `sudo systemctl restart mezzofy-api.service`

Option C — Wait until 2026-04-01 00:00 UTC (limit resets automatically)

---

## ISSUE-002 (2026-03-12) — BUG-015: agent_task UUID Type Mismatch in context.processor

**Priority:** P3 — Non-fatal logging failure (secondary bug)
**Raised by:** Lead Agent (investigation)
**Status:** ✅ RESOLVED — commit `2f777cd`

### Root Cause

`context/processor.py` passes a Python `UUID` object where asyncpg expects a `str`.
Recurring log error:
```
Failed to create/update agent_task record (session=...):
invalid input for query argument $4: UUID('...') (expected str, got UUID)
```

### Fix

In `context/processor.py`, cast the UUID to string when building the SQL parameter dict:
```python
# Before
{"session_id": session_id, ...}
# After
{"session_id": str(session_id), ...}
```
