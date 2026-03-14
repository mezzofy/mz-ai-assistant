# Quality Gate Review: Multi-Agent Orchestration v1.23.0
**Reviewer:** Lead Agent
**Date:** 2026-03-14
**Workflow:** change-request
**Scope:** Backend only (B1 + B2)

---

## Files Reviewed

| File | Action | Reviewed |
|------|--------|---------|
| `server/app/agents/research_agent.py` | CREATED | ✅ |
| `server/app/agents/developer_agent.py` | CREATED | ✅ |
| `server/app/llm/anthropic_client.py` | MODIFIED `_format_tools()` | ✅ |
| `server/app/llm/kimi_client.py` | MODIFIED `_format_tools()` | ✅ |
| `server/app/agents/agent_registry.py` | MODIFIED | ✅ |
| `server/app/api/chat.py` | MODIFIED | ✅ |
| `server/config/config.example.yaml` | MODIFIED | ✅ |

---

## Checklist

### Architecture & Patterns
- [x] Extends `BaseAgent` correctly (both agents)
- [x] `can_handle()` uses `task.get("agent") == "research"/"developer"` — correct for Celery path
- [x] `can_handle()` returns `False` safely during cross-dept keyword fallback (no `"agent"` key in sync path)
- [x] Lazy inline imports (`AnthropicClient`, `KimiClient`, `_update_agent_task_step`) — follows established pattern
- [x] `_broadcast_step` is non-fatal (wrapped in try/except) — correct
- [x] `_err()` / `_ok()` from BaseAgent NOT used for success return in research_agent — returns raw dict instead, but shape matches BaseAgent contract ✅
- [x] No cross-module imports — agents import from llm/ and tasks/ only

### Routing Logic (chat.py)
- [x] `_detect_agent_type()` called BEFORE `_is_long_running()` check — correct ordering
- [x] `"research:"` prefix detected via `startswith()` — case-sensitive (acceptable: user must type lowercase)
- [x] `"developer:"` prefix detected via `startswith()` — same note
- [x] `task_payload["agent"]` correctly set to `_detected_agent or user.get("department", "")` — clean fallback
- [x] `queue_name` in DB INSERT is now dynamic (`:qname` param) — SQL injection safe ✅
- [x] Existing department routing unchanged — non-matching messages flow through as before
- [x] `"research"` keyword already in original `_LONG_RUNNING_KEYWORDS` — "research:" prefix triggers both detect + long-running ✅

### AGENT_MAP Side Effect (agent_registry.py)
- [x] `_ALL_AGENTS` now includes ResearchAgent + DeveloperAgent — SAFE because both `can_handle()` return False when `task.get("agent")` is unset (sync path)
- [x] No docstring update on AgentRegistry — acceptable (not required for this change)

### LLM Client Fixes
- [x] `anthropic_client._format_tools()`: pass-through guard `if "type" in t and t.get("type") != "function"` — correctly identifies native built-in tools
- [x] `kimi_client._format_tools()`: pass-through guard `if "function" in t and isinstance(t.get("function"), dict)` — correctly identifies pre-formatted tools
- [x] Both guards preserve backward compatibility — existing ToolExecutor calls unaffected

### ResearchAgent — Claude Loop
- [x] `_sanitize_messages()` in AnthropicClient only strips top-level message dict keys, not `content` list internals — reconstructed assistant content blocks (tool_use) are preserved ✅
- [x] Tool result messages sent as `{"role": "user", "content": [...tool_result...]}` — correct Anthropic format
- [x] Loop termination: `stop_reason == "end_turn" or not tool_calls` — correct; handles both clean finish and edge case where model returns no tool calls with non-end_turn reason
- [x] `tc["arguments"]` guarded with `isinstance(..., dict)` — safe

### ResearchAgent — Kimi Loop
- [x] Assistant message constructed in OpenAI format with `tool_calls` key — correct for Kimi
- [x] `role: "tool"` result messages — correct OpenAI tool result format
- [x] Loop termination: `stop_reason == "stop" or not tool_calls` — correct; Kimi returns `finish_reason="tool_calls"` when calling tools, `"stop"` when done

### DeveloperAgent
- [x] `FileNotFoundError` caught separately — user gets a helpful message if Claude CLI not installed
- [x] `asyncio.create_subprocess_exec` (not `shell=True`) — no shell injection risk ✅
- [x] `env={**os.environ, "ANTHROPIC_API_KEY": ...}` — inherits full env, overrides key
- [x] All 5 stream-JSON event types handled: `assistant`, `tool_use`, `tool_result`, `result`, `error`
- [x] `errors="replace"` on decode — safe for unexpected binary output

---

## Issues Found

### 🔴 P1 — MUST FIX: Zombie process leak on timeout

**File:** `server/app/agents/developer_agent.py` lines 134–137

```python
except asyncio.TimeoutError:
    process.kill()
    logger.warning(...)
    return self._err(...)      # ← returns WITHOUT awaiting process.wait()
```

After `process.kill()` the child process is sent SIGKILL and terminates immediately, but the OS keeps a zombie entry until the parent calls `wait()`. The Celery worker is long-running — every developer agent timeout accumulates a zombie. Fix: add `await process.wait()` before `return`.

**Fix (one line):**
```python
except asyncio.TimeoutError:
    process.kill()
    await process.wait()       # ← add this line
    logger.warning(...)
    return self._err(...)
```

---

### 🟡 P2 — CONFIRM: `asyncio.timeout()` requires Python 3.11+

**File:** `server/app/agents/developer_agent.py` line 97

`async with asyncio.timeout(timeout):` was added in Python 3.11 (PEP 647). If EC2 runs Python 3.10, this raises `AttributeError` at runtime.

**Action required:** Confirm `python3 --version` on EC2. If 3.10, replace with:
```python
async with asyncio.wait_for(..., timeout=timeout):
```
or restructure using `asyncio.wait_for()` on the inner coroutine.

*Note: `str | None` union type syntax (used in both agents) also requires 3.10+, so EC2 is at minimum 3.10.*

---

### 🟢 P3 — MINOR: `success: True` returned even when subprocess exits non-zero

**File:** `server/app/agents/developer_agent.py` lines 141–152

The code logs a warning on non-zero exit but still returns `{"success": True}`. If Claude Code exits with an error code but produced some output before crashing, `final_result` may be non-empty — returning success is debatable but defensible. If `final_result` is empty on non-zero exit, the response is `{"success": True, "content": "Task complete."}` which is misleading.

**Recommendation:** Acceptable for v1.23.0 since `final_result or "Task complete."` is a safe fallback. Revisit in v1.24.0.

---

### 🟢 P3 — MINOR: Static `progress=50` for all step broadcasts

Both agents hardcode `progress=50` throughout the loop. The mobile banner progress bar will jump to 50% on the first step event and stay pinned there. This is a UX regression vs. the existing department agents which report incremental progress (5% → 80%).

**Recommendation:** Acceptable for v1.23.0 since the feature is new. Plan progressive progress calculation in v1.24.0.

---

## Routing Verification

End-to-end trace for "search the web: X":

```
POST /chat/send {"message": "search the web: X"}
  → _detect_agent_type("search the web: X") → "research"
  → _is_long_running("search the web: X") → True (hits "search the web")
  → queue_name_value = "research"
  → agent_tasks INSERT: queue_name="research"
  → task_payload["agent"] = "research"
  → process_chat_task.delay(task_payload)
  → _run_chat_task():
      agent_name = "research"
      "research" in AGENT_MAP → True
      agent = ResearchAgent(config)
      agent.execute(task_data) → Claude web_search_20250305 loop
      process_result() → saves to DB, marks agent_task completed
      Redis publish → mobile WS task_complete event
```
✅ Correct end-to-end.

End-to-end trace for regular "write a monthly sales report":

```
POST /chat/send {"message": "write a monthly sales report"}
  → _detect_agent_type(...) → None (no research/developer keyword)
  → _is_long_running(...) → True (hits "monthly")
  → queue_name_value = "background"
  → task_payload["agent"] = user.get("department", "")  ← department routing unchanged
  → AGENT_MAP["sales"] or get_agent_for_task() → SalesAgent
```
✅ Existing flow unchanged.

---

## Decision

**⚠️ REVISE — Fix P1 before deploy**

The P2 confirmation and P3 items can be handled post-merge but P1 (zombie process leak) is a one-line fix that must go in before the commit.

**Required fix (Backend Agent):**
- Add `await process.wait()` after `process.kill()` in the `asyncio.TimeoutError` handler in `developer_agent.py`

**Required confirmation (human):**
- Run `python3 --version` on EC2 to confirm Python 3.11+ before deploying

After the P1 fix is applied → **PASS — ready to commit and deploy.**

---

## Post-Fix Deploy Checklist

```
1. git add server/app/agents/research_agent.py
               server/app/agents/developer_agent.py
               server/app/llm/anthropic_client.py
               server/app/llm/kimi_client.py
               server/app/agents/agent_registry.py
               server/app/api/chat.py
               server/config/config.example.yaml
               server/app/context/artifact_manager.py   ← BUG-015 fix (pre-existing)
               server/app/context/session_manager.py    ← BUG-015 fix (pre-existing)
2. git commit -m "feat: add ResearchAgent + DeveloperAgent (v1.23.0)"
3. EC2: git pull --no-rebase
4. EC2: npm install -g @anthropic-ai/claude-code  (if not already installed)
5. EC2: Add to server/config/.env:
         AGENT_WORK_DIR=/home/ubuntu/mezzofy-workspace
6. EC2: sudo systemctl restart mezzofy-api.service
7. EC2: sudo systemctl restart mezzofy-worker.service
```

No migrate.py run needed — no DB schema changes.
