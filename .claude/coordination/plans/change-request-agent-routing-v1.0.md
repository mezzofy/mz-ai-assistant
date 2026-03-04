# Plan: Agent Routing Redesign — Department-First + Permission-Gated Cross-Department
**Workflow:** change-request
**Date:** 2026-03-04
**Created by:** Lead Agent

---

## Problem Statement

The current agent routing system has four interrelated problems:

1. **Cross-department routing is ungated** — Any user from any department can trigger any other
   department's agent if their message contains the right keyword. A support user asking about
   "invoices" routes to FinanceAgent; a management user asking "create a file" (with the word
   "content") routed to MarketingAgent. This is both a UX bug and a security gap.

2. **Permissions are ignored at routing** — `task["permissions"]` is carried in the JWT but the
   routing layer never reads it. `_require_permission()` is called in only ONE agent (SalesAgent).

3. **No general fallback in Finance, Marketing, Support agents** — These agents have no fallback
   handler. FinanceAgent always runs financial queries; MarketingAgent always runs content
   generation; SupportAgent always runs ticket analysis — even for completely unrelated messages.

4. **ManagementAgent can_handle() inconsistency** — Was the only agent requiring BOTH department
   AND keyword. Management users sending general requests (e.g., "create notes.txt") bypassed
   ManagementAgent and landed in SalesAgent as the default.

---

## Design Decisions

### Rule 1: Department → Agent is always 1:1 (primary routing)
`task["department"]` determines which agent handles the request. No exceptions for known departments.
A sales user always gets SalesAgent. A finance user always gets FinanceAgent.

### Rule 2: Cross-department routing requires explicit permission
Users without `"cross_department_access"` permission (or admin/executive role) stay in their
department's agent. Cross-department routing is opt-in, not opt-out.

### Rule 3: Management role has inherent cross-department access
Management users need to see all departments' data — that's their job.
`ManagementAgent.can_handle()` returns True for ALL management users (no keyword requirement).
Internal execute() routing (KPI vs general) stays based on message keywords.

### Rule 4: Every agent must have a general fallback
FinanceAgent, MarketingAgent, and SupportAgent currently have no true general fallback.
The `_general_response()` method belongs in `BaseAgent` — all agents inherit it and call it
as the last resort. This replaces ad-hoc fallbacks like `_general_sales_workflow()`.

### Rule 5: Conversation history key fixed at routing layer
`chat.py` stores history as `task["conversation_history"]` but `execute_with_tools()` reads
`task["messages"]`. Fix once in `router.py._execute_with_instance()` — add `"messages"` key
before dispatch. This means ALL agents and tools benefit without needing per-agent fixes.

---

## Files to Change

| # | File | Type | Change |
|---|------|------|--------|
| 1 | `server/app/agents/agent_registry.py` | EDIT | Redesign `get_agent_for_task()` — dept-first, permission-gated cross-dept |
| 2 | `server/app/agents/base_agent.py` | EDIT | Add shared `_general_response()` method |
| 3 | `server/app/agents/finance_agent.py` | EDIT | Simplify `can_handle()` + add `_general_response()` fallback in `execute()` |
| 4 | `server/app/agents/marketing_agent.py` | EDIT | Simplify `can_handle()` + add `_general_response()` fallback in `execute()` |
| 5 | `server/app/agents/support_agent.py` | EDIT | Simplify `can_handle()` + add `_general_response()` fallback in `execute()` |
| 6 | `server/app/agents/sales_agent.py` | EDIT | Simplify `can_handle()` — `_general_sales_workflow()` already uses execute_with_tools |
| 7 | `server/app/agents/management_agent.py` | EDIT | Simplify `can_handle()` — remove keyword requirement (execute() already routes internally) |
| 8 | `server/app/router.py` | EDIT | Add `task["messages"] = task.get("conversation_history", [])` in `_execute_with_instance()` |

---

## Detailed Change Specifications

---

### File 1: `server/app/agents/agent_registry.py`

**Replace `get_agent_for_task()` entirely:**

```python
# Permission string for cross-department access
_CROSS_DEPT_PERMISSION = "cross_department_access"
# Roles that always have cross-department access
_CROSS_DEPT_ROLES = {"admin", "executive", "management"}


def get_agent_for_task(task: dict, config: dict):
    """
    Select and instantiate the correct agent for the given task.

    Selection logic:
    1. User's department → always use that department's agent (primary routing)
    2. Unknown department + cross_department_access permission → keyword fallback
    3. Unknown department, no cross-dept permission → SalesAgent default

    Cross-department routing (step 2) is only activated for:
      - Users with "cross_department_access" in permissions
      - Users with role: admin, executive, or management

    Args:
        task: Task dict with "department", "role", "permissions", and "message" keys.
        config: Full app config dict.

    Returns:
        Instantiated agent (never None — always has a fallback).
    """
    department = task.get("department", "").lower()
    role = task.get("role", "").lower()
    permissions = task.get("permissions", [])

    # 1. Direct department → agent routing (primary path for all known departments)
    if department in AGENT_MAP:
        agent_cls = AGENT_MAP[department]
        logger.debug(f"AgentRegistry: department routing → {agent_cls.__name__} (dept={department!r})")
        return agent_cls(config)

    # 2. Unknown department: check if user has cross-department access
    can_cross_dept = (
        _CROSS_DEPT_PERMISSION in permissions
        or role in _CROSS_DEPT_ROLES
    )

    if can_cross_dept:
        for agent_cls in _ALL_AGENTS:
            agent = agent_cls(config)
            if agent.can_handle(task):
                logger.debug(
                    f"AgentRegistry: cross-dept keyword routing → {agent_cls.__name__} "
                    f"(role={role!r}, perm=cross_department_access)"
                )
                return agent

    # 3. Default fallback for unknown departments
    logger.debug(
        f"AgentRegistry: default fallback → SalesAgent "
        f"(dept={department!r} unknown, cross_dept={'yes' if can_cross_dept else 'no'})"
    )
    return SalesAgent(config)
```

---

### File 2: `server/app/agents/base_agent.py`

**Add `_general_response()` as a shared method (after `_send_email`):**

```python
async def _general_response(self, task: dict) -> dict:
    """
    General fallback — answer via LLM with full tool access.

    Used when the request doesn't match any department-specific workflow.
    Enables tools like create_txt, create_csv, create_pdf, send_email, etc.
    Conversation history is available for multi-turn tool use
    (e.g., LLM asks 'personal or shared?' → user replies → LLM calls tool).
    """
    from app.llm import llm_manager as llm_mod
    # task["messages"] key already set by router._execute_with_instance()
    llm_result = await llm_mod.get().execute_with_tools(task)
    content = llm_result.get("content", "I'm here to help. What would you like to do?")
    tools_called = llm_result.get("tools_called", [])
    return self._ok(content=content, tools_called=tools_called)
```

---

### File 3: `server/app/agents/finance_agent.py`

**Change 3a — Simplify `can_handle()`:**

Current:
```python
def can_handle(self, task: dict) -> bool:
    department = task.get("department", "").lower()
    if department == "finance":
        return True
    message = task.get("message", "").lower()
    return any(kw in message for kw in _TRIGGER_KEYWORDS)
```

Replace with:
```python
def can_handle(self, task: dict) -> bool:
    return task.get("department", "").lower() == "finance"
```

**Change 3b — Add general fallback in `execute()`:**

FinanceAgent's `execute()` currently runs financial queries unconditionally.
Add an intent check at the top so non-finance messages use `_general_response()`:

After:
```python
async def execute(self, task: dict) -> dict:
    source = task.get("source", "mobile")
    message = task.get("message", "")
```

Add:
```python
    # Scheduler/webhook: always run financial workflow
    # Mobile: only run financial workflow if message contains financial intent
    if source == "mobile" and not any(kw in message.lower() for kw in _TRIGGER_KEYWORDS):
        return await self._general_response(task)
```

---

### File 4: `server/app/agents/marketing_agent.py`

**Change 4a — Simplify `can_handle()`:**

Current:
```python
def can_handle(self, task: dict) -> bool:
    department = task.get("department", "").lower()
    if department == "marketing":
        return True
    message = task.get("message", "").lower()
    return any(kw in message for kw in _TRIGGER_KEYWORDS)
```

Replace with:
```python
def can_handle(self, task: dict) -> bool:
    return task.get("department", "").lower() == "marketing"
```

**Change 4b — Add general fallback in `execute()`:**

After:
```python
async def execute(self, task: dict) -> dict:
    message = task.get("message", "")
```

Add:
```python
    # Only run content generation workflow if message has marketing intent
    if not any(kw in message.lower() for kw in _TRIGGER_KEYWORDS):
        return await self._general_response(task)
```

---

### File 5: `server/app/agents/support_agent.py`

**Change 5a — Simplify `can_handle()`:**

Current:
```python
def can_handle(self, task: dict) -> bool:
    department = task.get("department", "").lower()
    if department == "support":
        return True
    message = task.get("message", "").lower()
    return any(kw in message for kw in _TRIGGER_KEYWORDS)
```

Replace with:
```python
def can_handle(self, task: dict) -> bool:
    return task.get("department", "").lower() == "support"
```

**Change 5b — Replace `_ticket_analysis_workflow()` default with `_general_response()`:**

SupportAgent's `execute()` ends with:
```python
return await self._ticket_analysis_workflow(task)
```

This always runs ticket analysis, even for "create a notes.txt". Replace the final default:
```python
# Only run ticket workflow if message has support/ticket intent
if any(kw in message.lower() for kw in _TRIGGER_KEYWORDS):
    return await self._ticket_analysis_workflow(task)
return await self._general_response(task)
```

(Keep the existing scheduler and ticket_triage conditions above this.)

---

### File 6: `server/app/agents/sales_agent.py`

**Change 6a — Simplify `can_handle()`:**

Current:
```python
def can_handle(self, task: dict) -> bool:
    department = task.get("department", "").lower()
    if department == "sales":
        return True
    message = task.get("message", "").lower()
    return any(kw in message for kw in _TRIGGER_KEYWORDS)
```

Replace with:
```python
def can_handle(self, task: dict) -> bool:
    return task.get("department", "").lower() == "sales"
```

No change to `execute()` — `_general_sales_workflow()` already calls `execute_with_tools`.
(The `conversation_history` → `messages` key fix is handled in router.py, File 8.)

---

### File 7: `server/app/agents/management_agent.py`

**Change 7 — Simplify `can_handle()` (remove keyword requirement):**

Current:
```python
def can_handle(self, task: dict) -> bool:
    message = task.get("message", "").lower()
    is_management_user = task.get("department", "").lower() == "management"
    has_keyword = any(kw in message for kw in _TRIGGER_KEYWORDS)
    return is_management_user and has_keyword
```

Replace with:
```python
def can_handle(self, task: dict) -> bool:
    return task.get("department", "").lower() == "management"
```

The keyword-based routing is already handled INSIDE `execute()`:
- Message has KPI keywords → `_kpi_dashboard_workflow()`
- Everything else → `_general_response()` (with tools — already fixed)

---

### File 8: `server/app/router.py`

**Change 8 — Add `conversation_history` → `messages` mapping in `_execute_with_instance()`:**

Current:
```python
async def _execute_with_instance(agent, task: dict) -> dict:
    agent_label = agent.__class__.__name__.replace("Agent", "").lower()
    logger.info(...)
    set_user_context(
        dept=task.get("department", "general"),
        email=task.get("email", ""),
    )
    result = await agent.execute(task)
    result.setdefault("agent_used", agent_label)
    return result
```

Add the key mapping before `agent.execute(task)`:
```python
    # Map conversation_history → messages for execute_with_tools compatibility.
    # chat.py stores session history under "conversation_history";
    # LLMManager.execute_with_tools() reads it as "messages".
    task["messages"] = task.get("conversation_history", [])
    result = await agent.execute(task)
```

---

## Routing Behaviour After Changes

| User Department | Message | Routing | Notes |
|----------------|---------|---------|-------|
| `sales` | "find leads in Singapore" | SalesAgent → prospecting workflow | dept match |
| `sales` | "create notes.txt" | SalesAgent → _general_response() → tools | no keyword match, fallback |
| `finance` | "show P&L Q4" | FinanceAgent → financial workflow | keyword match |
| `finance` | "create notes.txt" | FinanceAgent → _general_response() → tools | no keyword match, fallback |
| `marketing` | "write landing page" | MarketingAgent → content workflow | keyword match |
| `marketing` | "create notes.txt" | MarketingAgent → _general_response() → tools | no keyword match, fallback |
| `support` | "show open tickets" | SupportAgent → ticket workflow | keyword match |
| `support` | "create notes.txt" | SupportAgent → _general_response() → tools | no keyword match, fallback |
| `management` | "weekly KPI dashboard" | ManagementAgent → KPI workflow | keyword match |
| `management` | "create notes.txt" | ManagementAgent → _general_response() → tools | no keyword match, fallback |
| `support` | "what's our revenue?" | SupportAgent → _general_response() → LLM answers | no cross-dept DB access |
| `support` (+ cross_dept perm) | "what's our revenue?" | SalesAgent or FinanceAgent via keyword scan | explicit cross-dept permission |

---

## What Does NOT Change

- `execute()` internal workflow routing in each agent (keyword-based sub-workflow selection stays)
- Permission checks within `execute()` for specific actions (e.g., `email_send` in SalesAgent)
- The `_kpi_dashboard_workflow()` and `_weekly_kpi_workflow()` in ManagementAgent
- All tool ops, LLM manager, session management, artifact routing
- JWT payload structure — `permissions` array is already there

---

## Task Assignment

**Agent:** Backend Agent
**Sessions:** 1 (8 files, all small surgical changes — no new files needed)
**Dependencies:** None — self-contained routing refactor

---

## Acceptance Criteria

- [ ] Sales user: "create notes.txt" → SalesAgent handles it, file created via tools
- [ ] Finance user: "create notes.txt" → FinanceAgent handles it, file created via tools
- [ ] Marketing user: "create notes.txt" → MarketingAgent handles it, file created via tools
- [ ] Support user: "create notes.txt" → SupportAgent handles it, file created via tools
- [ ] Management user: "create notes.txt" → ManagementAgent handles it, file created via tools
- [ ] Management user: "weekly KPI" → ManagementAgent KPI workflow (unchanged)
- [ ] Support user: "show quarterly revenue" → SupportAgent general response (no cross-dept data leak)
- [ ] Support user with cross_department_access: "show quarterly revenue" → FinanceAgent
- [ ] Marketing keywords ("write landing page") still route to MarketingAgent for marketing users
