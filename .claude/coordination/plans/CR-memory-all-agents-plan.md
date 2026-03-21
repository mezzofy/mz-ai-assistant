# Plan: CR — Persistent Memory for All Agents (v1.46.x)
**Workflow:** change-request
**Date:** 2026-03-21
**Created by:** Lead Agent
**Version target:** v1.46.x (next available patch)

---

## Context

`chat_with_memory()` (Anthropic server-side memory tool) is only wired to `ManagementAgent._general_response()`.
All other agents use `execute_with_tools()` in their fallback path — no persistent memory.

**Goal:** Every agent's general/fallback response path gets the same memory capability ManagementAgent has today.

---

## Analysis: Who calls what today

### Uses `_general_response()` → all get memory after base fix
| Agent | Path |
|-------|------|
| ManagementAgent | overrides `_general_response()` with `chat_with_memory()` → already has memory |
| FinanceAgent | calls `self._general_response(task)` → falls through to **base** (no memory) |
| HRAgent | calls `self._general_response(task)` → falls through to **base** (no memory) |
| MarketingAgent | calls `self._general_response(task)` → falls through to **base** (no memory) |
| SupportAgent | calls `self._general_response(task)` → falls through to **base** (no memory) |

### Uses `execute_with_tools()` directly (intentional specialized calls — do NOT add memory)
| Agent | Why NOT |
|-------|---------|
| LegalAgent | Custom system prompts injected per workflow — memory namespace would conflict |
| SchedulerAgent | Custom system prompt via `task["system_prompt"]`; scheduler context, not user-facing chat |
| SalesAgent | Has its own fallback (`_general_response_fallback`) calling `execute_with_tools()` directly |

### Special agents (own loops — not applicable)
| Agent | Why NOT |
|-------|---------|
| ResearchAgent | Native server-side web_search tools — own agentic loop, incompatible with memory tool |
| DeveloperAgent | Claude Code subprocess — no LLM call in Python |

---

## Approach

**Single-file core change:** Update `BaseAgent._general_response()` in `base_agent.py` to use `chat_with_memory()` with fallback to `execute_with_tools()` — exactly the pattern ManagementAgent already has.

**Remove duplication:** Delete `ManagementAgent._general_response()` override — it becomes redundant once base has memory.

**SalesAgent:** Update `SalesAgent._general_response_fallback()` to call `self._general_response(task)` instead of `execute_with_tools()` directly, so it inherits memory from base.

---

## Task Breakdown

| # | Task | Agent | Scope | Depends On | Est. Sessions | Status |
|---|------|-------|-------|-----------|:-------------:|--------|
| 1 | Backend: update BaseAgent + remove ManagementAgent override + fix SalesAgent | Backend | `server/app/agents/base_agent.py`, `management_agent.py`, `sales_agent.py` | None | 1 | NOT STARTED |
| 2 | Tester: update/add tests for all 5 affected agents | Tester | `server/tests/` | Task 1 | 1 | NOT STARTED |
| 3 | Lead review: quality gate | Lead | plans/ | Task 2 | — | NOT STARTED |

## Parallel Opportunities
- Tasks 1 and 2 are sequential (tests depend on implementation)

---

## Detailed Spec for Backend Agent

### File 1: `server/app/agents/base_agent.py`

Replace `_general_response()` (lines ~182–199) with:

```python
async def _general_response(self, task: dict) -> dict:
    """
    General fallback — answer via LLM with persistent memory and full tool access.

    Uses chat_with_memory() so all agents build user-level memory across sessions.
    Falls back to execute_with_tools() if memory tool fails.

    Memory scope: "user:{user_id}" — per-user across all departments.
    """
    from app.llm import llm_manager as llm_mod

    task_for_llm = {**task, "messages": task.get("conversation_history", [])}
    messages = task_for_llm.get("messages", [])
    if not messages or messages[-1].get("content") != task.get("message", ""):
        messages = messages + [{"role": "user", "content": task.get("message", "")}]

    memory_scope = f"user:{task.get('user_id', 'unknown')}"
    system_prompt = llm_mod.get()._build_system_prompt(task_for_llm)

    try:
        llm_result = await llm_mod.get().chat_with_memory(
            messages=messages,
            memory_scope=memory_scope,
            client_tools=None,
            system=system_prompt,
        )
        content = llm_result.get("text") or llm_result.get("content", "")
        if not content:
            content = "I'm here to help. What would you like to do?"
        return self._ok(content=content, tools_called=["memory"], artifacts=[])
    except Exception as e:
        logger.warning(
            f"{self.__class__.__name__}._general_response: "
            f"chat_with_memory failed, falling back to execute_with_tools: {e}"
        )
        llm_result = await llm_mod.get().execute_with_tools(task_for_llm)
        content = llm_result.get("content", "I'm here to help. What would you like to do?")
        tools_called = llm_result.get("tools_called", [])
        artifacts = llm_result.get("artifacts", [])
        return self._ok(content=content, tools_called=tools_called, artifacts=artifacts)
```

### File 2: `server/app/agents/management_agent.py`

Remove the entire `_general_response()` override method (lines ~84–112).
The base implementation now covers ManagementAgent identically.
Keep `_kpi_dashboard_workflow()` and all other methods unchanged.

### File 3: `server/app/agents/sales_agent.py`

`_general_sales_workflow()` (line ~347) calls `execute_with_tools()` directly.
Replace its body with `return await self._general_response(task)`.
This way SalesAgent inherits the base memory path (same pattern, no duplication).

---

## Detailed Spec for Tester Agent

### Test changes required

1. **`test_base_agent.py` or `test_management_agent.py`** (wherever `_general_response` is tested):
   - Update mocks: `_general_response` now calls `chat_with_memory` first, then falls back
   - Add test: fallback path fires when `chat_with_memory` raises exception
   - Verify: `tools_called=["memory"]` on success path

2. **`test_management_agent.py`**:
   - ManagementAgent no longer overrides `_general_response` — remove tests for the override
   - ManagementAgent should still pass existing behavioral tests (it now uses base)

3. **`test_sales_agent.py`**:
   - `_general_sales_workflow` previously called `execute_with_tools` directly
   - Update: now calls `_general_response` (which calls `chat_with_memory`); update mock expectations accordingly

4. **`test_finance_agent.py`, `test_hr_agent.py`, `test_marketing_agent.py`, `test_support_agent.py`**:
   - Any test for the fallback path should now expect `chat_with_memory` call (or test behaviorally)

**Minimum coverage:** All 5 department agents' fallback path must have at least one test.

---

## Quality Gate

Lead reviews after Task 2 completes:
- [ ] `BaseAgent._general_response()` uses `chat_with_memory()` with fallback
- [ ] `ManagementAgent._general_response()` override removed (no duplication)
- [ ] `SalesAgent` fallback calls `self._general_response()` (not `execute_with_tools()` directly)
- [ ] All existing tests still pass (no regressions)
- [ ] New/updated tests cover: success path (memory used), failure path (fallback to execute_with_tools)
- [ ] `LegalAgent`, `SchedulerAgent`, `ResearchAgent`, `DeveloperAgent` unchanged

---

## Acceptance Criteria

1. Finance, HR, Marketing, Support, Management agents all use persistent memory in their fallback path
2. Sales agent fallback also uses persistent memory
3. Legal, Scheduler, Research, Developer agents are unchanged (they have specialized execution paths)
4. Zero test regressions
5. Deploy as a patch release (v1.46.x)

---

## Version & Release Notes

- **Version:** v1.46.x (patch after current v1.46.y)
- **RN required:** Yes — add entry: "Persistent memory now active for all department agents (Finance, HR, Marketing, Sales, Support) — agents remember user preferences and context across sessions"
- **Deploy:** Restart `mezzofy-api.service` + `mezzofy-celery.service` (code change only, no migration needed)
