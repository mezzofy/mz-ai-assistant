# Context Checkpoint: Lead Agent
**Date:** 2026-03-19
**Session:** Portal v1.41.0 Planning
**Task:** Add Leo (Legal Agent) + agentic metadata to Mission Control Portal

---

## Assessment Complete

### Current State
- Portal v1.33.0 deployed to EC2 with 9 agents (no Leo)
- `AGENT_REGISTRY` in `admin_portal.py` is hardcoded with simplified skills (not matching AGENTS.md)
- `AgentOffice.tsx` canvas has 9 agent positions (no legal dept)
- `AgentsPage.tsx` shows only: name, dept, skills, tasks, memory — no persona/tools/llm_model
- Leo backend NOT yet implemented (separate plan: `legal-agent-backend-plan.md`)

### Files Needing Changes
- `server/app/api/admin_portal.py` — Replace AGENT_REGISTRY (lines ~459–469) with 10-agent full spec
- `portal/src/types/index.ts` — Extend Agent interface (add persona, description, tools_allowed, llm_model, is_orchestrator)
- `portal/src/components/AgentOffice.tsx` — Add legal dept at position (550, 190) + scales sprite
- `portal/src/pages/AgentsPage.tsx` — Enhanced cards (persona, description, type badge, tools, LLM footer)

---

## Plan Written
- `.claude/coordination/plans/portal-v1.41.0-agents-update-plan.md`

## Quality Gate Criteria
- All 10 agent cards visible in Agents page
- Leo sprite appears in AgentOffice canvas at (550, 190)
- Each card shows: persona, description, type badge (ORCHESTRATOR/SPECIAL/DEPT), skills, tools, llm_model
- AGENT_REGISTRY matches docs/AGENTS.md exactly
- No regressions in memory upload/delete

## Next Step After Completion
- Lead reviews both agent outputs against verification checklist
- Deploy to EC2 (git pull + service restart + portal rebuild)
- Update memory.md with completion note
