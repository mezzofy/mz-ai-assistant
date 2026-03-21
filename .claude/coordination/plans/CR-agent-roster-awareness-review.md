# Review: CR — Agent Team Roster Awareness + Persona-Name Routing
**Date:** 2026-03-21
**Reviewer:** Lead Agent
**Plan:** CR-agent-roster-awareness-plan.md

---

## Quality Gate Checklist

### System Prompt (llm_manager.py)
- [x] `_AGENT_PERSONA_MAP` present — all 10 dept→persona entries correct
- [x] `_AGENT_TEAM_ROSTER` constant present — 10-agent table with persona, dept, specialty, invoke syntax
- [x] `_build_system_prompt()` prepends `self_identity + roster + "\n"` before existing template
- [x] Self-identity format: "You are **{Persona}**, Mezzofy's {Dept} Agent."
- [x] Roster appears BEFORE existing system prompt content (correct ordering verified in tests)
- [x] Unknown dept falls back to "AI Assistant" gracefully

### Routing (chat.py)
- [x] `_PERSONA_ROUTING` dict — all 10 persona→routing key mappings present
- [x] `_PERSONA_ROUTE_VERBS` — 14 directed-verb phrases
- [x] `_detect_persona_routing()` handles both prefix ("leo:") and directed phrase ("ask leo")
- [x] `_detect_agent_type()` calls `_detect_persona_routing()` first (highest priority)
- [x] Existing keyword/prefix routing still works unchanged (falls through)
- [x] False-positive safety: "max items", "dev environment", "sam is working" → None

### Tests
- [x] `test_agent_roster_routing.py` created — 53 new tests
- [x] All 10 persona map entries tested
- [x] All 10 name-prefix routes tested ("leo:", "rex:", ... "hana:")
- [x] Directed phrase routing tested ("ask Leo...", "route to Rex", "have Sam...")
- [x] False-positive safety tests (5 cases returning None)
- [x] Full `_detect_agent_type()` integration: persona > prefix > keyword priority confirmed
- [x] 501 existing tests pass — 17 pre-existing infrastructure failures (Redis/Outlook, unchanged)

---

## Decision: ✅ PASS

Agent team awareness is fully implemented at both layers:
1. **LLM layer** — every agent now tells Claude who it is and shows the full team roster in its system prompt
2. **Routing layer** — users can invoke any agent by name prefix or directed phrase

---

## Deploy Instructions

```bash
# On EC2
git pull
sudo systemctl restart mezzofy-api.service
sudo systemctl restart mezzofy-celery.service
# No migrate.py needed
```

**Version:** v1.47.0

**Example interactions now working:**
- "leo: review this NDA" → routes to Leo (LegalAgent)
- "ask Rex to research our competitors" → routes to Rex (ResearchAgent)
- "route to Sam" → routes to Sam (SalesAgent)
- "fiona: generate Q1 financial report" → routes to Fiona (FinanceAgent)
- "who is on your team?" → current agent explains all 10 agents by name
