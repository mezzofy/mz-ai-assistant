# Review: SchedulerAgent v1.25.0
**Date:** 2026-03-15
**Reviewer:** Lead Agent
**Workflow:** change-request
**Decision:** ✅ PASS (after Backend Agent fixes)

---

## Files Reviewed

| File | Type | Verdict |
|------|------|---------|
| `server/app/tools/scheduler/__init__.py` | New — empty package | ✅ |
| `server/app/tools/scheduler/scheduler_ops.py` | New — 4 tool methods | ✅ |
| `server/app/agents/scheduler_agent.py` | New — agent | ✅ (after fix) |
| `server/app/api/chat.py` | Modified — keyword detection | ✅ (after fix) |
| `server/app/agents/agent_registry.py` | Modified — AGENT_MAP entry | ✅ |
| `server/app/router.py` | Modified — explicit agent override | ✅ |
| `server/app/tools/tool_executor.py` | Modified — SchedulerOps registered | ✅ |
| `server/app/llm/llm_manager.py` | Modified — system_prompt override | ✅ (fix) |

---

## Issues Found & Resolved

### ❌ → ✅ CRITICAL Bug A — Scheduler detection order
- **Problem:** `_is_scheduler_request()` fired AFTER `_is_long_running()`.
  Phrases like "schedule a weekly report" matched `_LONG_RUNNING_KEYWORDS`
  ("weekly", "report") and went to Celery — SchedulerAgent never reached.
- **Fix (commit 6d9f634):** Scheduler detection moved FIRST. Long-running check
  guarded with `if not task.get("agent") and _is_long_running(...)`.

### ❌ → ✅ CRITICAL Bug B — Custom system prompt silently ignored
- **Problem:** `LLMManager._build_system_prompt()` always built from
  `_SYSTEM_PROMPT_TEMPLATE`. The SchedulerAgent's `task["system_prompt"]`
  injection was silently dropped — LLM saw all 40+ tools, not 4 scheduler tools.
- **Fix (commit 6d9f634):** Added early-return at top of `_build_system_prompt()`:
  `if task and task.get("system_prompt"): return task["system_prompt"]`

### ⚠️ → ✅ Medium — LLMManager fresh instantiation
- **Problem:** `LLMManager(config)` per request; memory.md mandates singleton.
- **Fix (commit 6d9f634):** Changed to `llm_mod.get().execute_with_tools(...)`.

### ⚠️ Accepted — Cron minimum interval gap
- Chat path doesn't enforce 15-min minimum (REST API does).
- LLM system prompt guidance mitigates. Deferred to v1.26.0.

---

## Quality Checklist

### Architecture
- [x] Follows BaseTool + BasAgent patterns
- [x] Lazy inline imports inside method bodies
- [x] All queries parameterized — no SQL injection risk
- [x] Ownership enforced: all write tools check `str(row.user_id) != user_id`
- [x] Job limit enforced before INSERT (not after)
- [x] `can_handle()` checks `task["agent"]` — safe in cross-dept fallback

### Routing
- [x] Scheduler detection before long-running check
- [x] `_route_mobile()` explicit agent override doesn't break dept routing
- [x] No regression: normal dept messages unaffected (`task["agent"]` unset → explicit check fails → dept routing)
- [x] No regression: research/developer Celery path unaffected

### LLM
- [x] Custom system prompt delivered to LLM via `task["system_prompt"]`
- [x] System prompt instructs: 4 tools only, UTC timezone math, list-before-delete
- [x] Singleton pattern followed

### Security
- [x] No user-supplied values in SQL SET clauses
- [x] Ownership check on delete and run_now
- [x] `user_id` from `user_context.get_user_id()` (server-side ContextVar, not user input)

---

## Known Gaps (Non-Blocking)
- Cron 15-min minimum not validated in chat path (v1.26.0 candidate)
- No unit tests for `_is_scheduler_request()` or `SchedulerOps` (v1.26.0 candidate)
- `SchedulerAgent` appears in `_ALL_AGENTS` cross-dept fallback scan (harmless — `can_handle()` returns False when `task["agent"]` is not "scheduler")

---

## Deploy Checklist
- [ ] `git push` to remote
- [ ] `git pull` on EC2
- [ ] `sudo systemctl restart mezzofy-api.service`
- [ ] No DB migration required (uses existing `scheduled_jobs` table)
- [ ] No mobile changes required (Schedule Stats screen already polls REST API)

## Verification (Manual — EC2)
```bash
# Test 1: List jobs (no scheduler keywords → dept routing, not scheduler)
POST /chat/send {"message": "find new leads in fintech"}
→ agent_used: "sales" (not "scheduler")

# Test 2: List scheduler jobs
POST /chat/send {"message": "show my scheduled tasks"}
→ agent_used: "scheduler", content lists jobs

# Test 3: Create — phrase with long-running words
POST /chat/send {"message": "Schedule a weekly sales report every Monday at 9am"}
→ agent_used: "scheduler", new row in scheduled_jobs (NOT routed to Celery)

# Test 4: Delete by name (LLM must call list first, then delete)
POST /chat/send {"message": "Delete my weekly sales report schedule"}
→ agent_used: "scheduler", is_active = FALSE for that job
```
