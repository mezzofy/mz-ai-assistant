# Plan: CR — Agent Team Roster Awareness + Persona-Name Routing (v1.47.0)
**Workflow:** change-request
**Date:** 2026-03-21
**Created by:** Lead Agent

---

## Problem Statement

Users want to say things like "Ask Leo to review this contract" or "Can Sam help me with this lead?"
but today nothing works:

1. **Agents don't know the team** — `_SYSTEM_PROMPT_TEMPLATE` has zero roster info. Every agent
   just knows it's "the Mezzofy AI Assistant helping the {department} team." When a user mentions
   Leo, Sam, Rex, etc., the active agent has no idea who they are.

2. **Routing ignores persona names** — `_detect_agent_type()` in `chat.py` only detects
   keyword/prefix routing (legal keywords, research keywords, etc.) and predefined prefixes
   ("research:", "legal:", "developer:"). Saying "ask Leo to review this" → no routing happens.

---

## Solution: Two Changes, Two Files

### Change 1: System Prompt — Inject Team Roster + Self-Identity (`llm_manager.py`)

Add a `_AGENT_TEAM_ROSTER` constant (compact table of all 10 agents) and a `_AGENT_PERSONA_MAP`
dict (dept → persona name). Update `_build_system_prompt()` to prepend self-identity + roster
to every agent's system prompt.

**Result:** Every agent call to the LLM now includes:
- "You are **Fiona**, Mezzofy's Finance Agent."
- A compact team table: who each agent is, their persona name, specialty, and how to invoke them

### Change 2: Persona-Name Routing (`chat.py`)

Extend `_detect_agent_type()` to recognise:
- Name prefixes: `"leo:"`, `"rex:"`, `"max:"`, `"fiona:"`, `"sam:"`, `"maya:"`, `"suki:"`, `"hana:"`, `"dev:"`, `"sched:"`
- Directed phrases: `"ask leo"`, `"talk to leo"`, `"route to leo"`, `"send to leo"`, `"let leo"`, `"have leo"` (same pattern for each persona)

Returns the correct agent routing key for each persona:
- leo → "legal"
- rex → "research"
- dev → "developer"
- sched → "scheduler"
- max → "management"
- fiona → "finance"
- sam → "sales"
- maya → "marketing"
- suki → "support"
- hana → "hr"

---

## Detailed Spec for Backend Agent

### FILE 1: `server/app/llm/llm_manager.py`

#### Step A — Add `_AGENT_PERSONA_MAP` constant (after the existing `_SYSTEM_PROMPT_TEMPLATE`)

```python
# Maps department name → agent persona name
_AGENT_PERSONA_MAP: dict[str, str] = {
    "management": "Max",
    "finance": "Fiona",
    "sales": "Sam",
    "marketing": "Maya",
    "support": "Suki",
    "hr": "Hana",
    "legal": "Leo",
    "research": "Rex",
    "developer": "Dev",
    "scheduler": "Sched",
}
```

#### Step B — Add `_AGENT_TEAM_ROSTER` constant (after `_AGENT_PERSONA_MAP`)

```python
_AGENT_TEAM_ROSTER = """
## Mezzofy AI Team — All 10 Agents

You are part of a 10-agent AI team. Each agent has a persona name, a department specialty,
and can be invoked by typing their name followed by ":" (e.g. "leo: review this contract")
or by using natural-language routing phrases like "ask Leo to...", "route to Sam", etc.

| Persona | Agent | Department | Specialty |
|---------|-------|-----------|-----------|
| Max | Management (Orchestrator) | management | Cross-dept KPI dashboards, executive reports, multi-agent orchestration. Delegates to all other agents. |
| Fiona | Finance | finance | Financial reports, revenue analytics, P&L summaries, CSV/PDF exports |
| Sam | Sales | sales | LinkedIn prospecting, CRM lead management, email campaigns, pitch deck generation |
| Maya | Marketing | marketing | Marketing content, campaign emails, competitive web research, brand materials |
| Suki | Support | support | Support ticket analysis, SLA reports, customer communications, Teams updates |
| Hana | HR | hr | HR analytics, leave/headcount reports, employee communications, org charts |
| Leo | Legal | legal | Contract review/drafting, legal advisory, risk assessment — 7 jurisdictions (SG/HK/MY/UAE/SA/QA/Cayman) |
| Rex | Research | research | Agentic web research (up to 8 search iterations), cited market research reports |
| Dev | Developer | developer | Code generation, code review, Claude Code CLI execution, API integration |
| Sched | Scheduler | scheduler | Schedule recurring jobs (Celery Beat), manage automated reports |

**How users invoke a specific agent:**
- Name prefix: "leo: review this contract" / "rex: research competitors" / "sam: find prospects"
- Directed phrase: "ask Leo to...", "have Sam...", "route to Rex", "let Fiona run the report"
- Keywords: Legal/contract/NDA keywords → Leo | Research/web search → Rex | Code/script keywords → Dev

When the user asks about another agent or wants to route to them, explain who they are and
their invoke syntax. If the user asks you to do something outside your specialty, suggest
the right agent.
"""
```

#### Step C — Update `_build_system_prompt()` to inject self-identity + roster

At the start of `_build_system_prompt()`, after resolving `dept`, `role`, `source`, `user_id`:

1. Look up `persona_name = _AGENT_PERSONA_MAP.get(dept.lower(), "AI Assistant")`
2. Build `self_identity = f"You are **{persona_name}**, Mezzofy's {dept.title()} Agent.\n\n"`
3. Prepend `self_identity + _AGENT_TEAM_ROSTER + "\n\n"` to the system prompt

The final prompt structure becomes:
```
You are **Fiona**, Mezzofy's Finance Agent.

## Mezzofy AI Team — All 10 Agents
[roster table]

You are the Mezzofy AI Assistant helping the finance team.
[rest of existing template...]
```

The `_SYSTEM_PROMPT_TEMPLATE` itself does NOT need to change — just prepend to the result of `format()`.

---

### FILE 2: `server/app/api/chat.py`

#### Step A — Add `_PERSONA_ROUTING` dict (near the top, after `_LEGAL_TRIGGERS` or `_SCHEDULER_KEYWORDS`)

```python
# Maps persona name → agent routing key
# Used to route messages like "ask Leo...", "leo: ...", "route to Sam"
_PERSONA_ROUTING: dict[str, str] = {
    "leo": "legal",
    "rex": "research",
    "dev": "developer",
    "sched": "scheduler",
    "max": "management",
    "fiona": "finance",
    "sam": "sales",
    "maya": "marketing",
    "suki": "support",
    "hana": "hr",
}

# Phrases that signal intent to route to a named agent
_PERSONA_ROUTE_VERBS = [
    "ask ", "talk to ", "route to ", "send to ", "let ", "have ",
    "get ", "use ", "ping ", "tell ", "forward to ", "hand to ",
    "hand off to ", "pass to ",
]
```

#### Step B — Add `_detect_persona_routing()` helper

```python
def _detect_persona_routing(message: str) -> str | None:
    """
    Detect if the user is addressing a specific agent by persona name.

    Supports:
      - Name prefix:    "leo: review this contract"
      - Directed phrase: "ask Leo to draft an NDA", "route to Rex", "have Sam find leads"

    Returns the agent routing key (e.g. "legal", "research") or None.
    """
    lower = message.lower().strip()
    for persona, routing_key in _PERSONA_ROUTING.items():
        # 1. Name prefix syntax: "leo: ..." or "leo :"
        if lower.startswith(f"{persona}:") or lower.startswith(f"{persona} :"):
            return routing_key
        # 2. Directed phrase: "ask leo ...", "route to leo", "talk to leo ..."
        for verb in _PERSONA_ROUTE_VERBS:
            if f"{verb}{persona}" in lower:
                return routing_key
    return None
```

#### Step C — Update `_detect_agent_type()` to call `_detect_persona_routing()` first

```python
def _detect_agent_type(message: str) -> str | None:
    """
    Detect whether a message should be routed to a specific power-user agent.

    Returns agent routing key ("research", "developer", "legal", "scheduler",
    "management", "finance", "sales", "marketing", "support", "hr") or None.

    Priority order:
    1. Persona-name routing ("leo: ...", "ask Rex to ...", "route to Sam")
    2. Prefix routing ("research: ...", "developer: ...", "legal: ...")
    3. Keyword routing (research/developer/legal keyword lists)
    """
    # 1. Persona name routing (highest priority — explicit agent addressing)
    persona_route = _detect_persona_routing(message)
    if persona_route:
        return persona_route

    lower = message.lower()
    # 2 & 3. Existing keyword/prefix routing
    if lower.startswith("research:") or any(kw in lower for kw in _RESEARCH_KEYWORDS):
        return "research"
    if lower.startswith("developer:") or any(kw in lower for kw in _DEVELOPER_KEYWORDS):
        return "developer"
    if lower.startswith("legal:") or _is_legal_request(message):
        return "legal"
    return None
```

#### Step D — Ensure department-agent routing keys work in AGENT_MAP

`AGENT_MAP` in `agent_registry.py` already has: `"management"`, `"finance"`, `"sales"`, `"marketing"`, `"support"`, `"hr"` as valid keys. The router's short-circuit for `task["agent"]` already works for these.

In `chat.py`, after `_detected_agent = _detect_agent_type(body.message)`, the result feeds into:
```python
task_payload["agent"] = _detected_agent
```

Verify this assignment path handles all 10 routing keys, not just the 3 special agents. If `task_payload["agent"]` is set to "finance" and the router's `_route_mobile()` checks `AGENT_MAP`, Finance routing will work. **Read the actual assignment code** to confirm — adjust if needed.

---

## Task Breakdown

| # | Task | Agent | Files | Depends On | Est. Sessions | Status |
|---|------|-------|-------|-----------|:-------------:|--------|
| 1 | Backend: system prompt roster + persona routing | Backend | `llm_manager.py`, `chat.py` | None | 1 | NOT STARTED |
| 2 | Tester: update + add tests | Tester | `server/tests/` | Task 1 | 1 | NOT STARTED |
| 3 | Lead review | Lead | plans/ | Task 2 | — | NOT STARTED |

---

## Quality Gate

- [ ] `_build_system_prompt()` output includes "You are **{Persona}**" + full 10-agent roster table
- [ ] `_detect_persona_routing()` correctly maps all 10 persona names to routing keys
- [ ] `_detect_agent_type()` calls persona routing first (highest priority)
- [ ] `"leo: review this"` routes to LegalAgent
- [ ] `"ask Rex to research competitors"` routes to ResearchAgent
- [ ] `"route to Sam"` routes to SalesAgent
- [ ] `"fiona: generate Q1 report"` routes to FinanceAgent
- [ ] False-positive guard: a message mentioning "max items" or "dev environment" does NOT trigger routing
- [ ] All existing tests pass (no regressions)
- [ ] New tests: persona prefix routing, directed phrase routing, false-positive safety

---

## Acceptance Criteria

1. Every agent's LLM system prompt includes the agent's own persona name + full 10-agent roster table
2. Users can invoke any agent by typing `{persona_name}: {message}` (prefix syntax)
3. Users can invoke any agent by natural language: "ask Leo...", "route to Sam...", "have Rex research..."
4. The active agent can explain who other agents are when asked
5. No false-positive routing on ambiguous words (max, dev, sam)
6. Zero test regressions

---

## Version

- **Version:** v1.47.0
- **Deploy:** Restart `mezzofy-api.service` + `mezzofy-celery.service` — no migration needed
- **RN entry:** "All 10 agents now know the full team roster by name and persona. Invoke any agent by typing their name: 'leo: review this contract', 'ask Rex to research competitors', 'fiona: Q1 report'"
