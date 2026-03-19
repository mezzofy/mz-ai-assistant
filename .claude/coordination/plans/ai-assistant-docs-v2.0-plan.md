# Plan: AI Assistant Documentation v2.0
**Workflow:** change-request
**Date:** 2026-03-19
**Created by:** Lead Agent
**Source:** User request — document full features, how agents work together, user guide for agentic agents

---

## Context

The existing `docs/Mezzofy_AI_Assistant_Features_List.txt` was last updated March 15, 2026.
It does NOT reflect:
- Agent Enhancement v2.0 (9 persistent agents with DB identity, AgentRegistry, plan_and_orchestrate orchestration)
- 3 new special agents: ResearchAgent, DeveloperAgent, SchedulerAgent (v1.23–v1.25)
- 11 new skills: deep_research, source_verification, code_generation, code_review, code_execution, api_integration, test_generation, schedule_management, cron_validation, job_monitoring, beat_sync
- How agents collaborate and delegate tasks to each other
- User guide for triggering agentic workflows

The documentation also needs to explain the agent team architecture for non-technical users (business users on mobile/web).

---

## Task Breakdown

| # | Deliverable | Agent | Output Path | Depends On | Est. Sessions |
|---|------------|-------|------------|-----------|:-------------:|
| 1 | Updated Features List (v2.0) | Docs | `docs/Mezzofy_AI_Assistant_Features_List_v2.0.md` | None | 1 |
| 2 | Agent Architecture Guide | Docs | `docs/AGENTS.md` | None | 1 |
| 3 | User Guide: Agentic Features | Docs | `docs/USER_GUIDE_AGENTIC.md` | Tasks 1+2 | 1 |

All 3 tasks can run in ONE Docs Agent session (no dependencies between 1 and 2; 3 wraps both).

---

## Detailed Deliverable Specs

### Task 1 — Updated Features List (docs/Mezzofy_AI_Assistant_Features_List_v2.0.md)

Update the existing features list into a structured Markdown file. Add all v2.0 additions:

**New sections to add:**
- Agent Enhancement v2.0 section (persistent agent identities, AgentRegistry, orchestration)
- ResearchAgent capabilities (deep_research, source_verification)
- DeveloperAgent capabilities (code_generation, code_review, code_execution, api_integration, test_generation)
- SchedulerAgent capabilities (schedule_management, cron_validation, job_monitoring, beat_sync)
- Cross-Department Orchestration (ManagementAgent plan_and_orchestrate)
- RAG Knowledge Namespacing (each agent has private + shared KB)
- Mission Control Admin Portal (v1.33.0)

**Refresh existing sections:**
- Mark items with v-tag (e.g., "(v1.23.0)") for discoverability
- Fix items marked ⚠️ or ❌ if they've since been implemented
- Update version date from March 15, 2026 → March 19, 2026

---

### Task 2 — Agent Architecture Guide (docs/AGENTS.md)

A technical-friendly reference document explaining the 9-agent team. Structure:

```
## Entity Model
- Agents table (id, department, skills, memory_namespace, is_orchestrator)
- agent_task_log (parent/child chain, delegation tracking)

## The 9 Agents

### Management Agent (Orchestrator)
- Role, capabilities, how it decomposes cross-dept tasks
- plan_and_orchestrate() flow diagram (Mermaid)
- Cross-department keywords that trigger orchestration

### Finance Agent
- Department: finance | Skills: financial_reporting, data_analysis
- Typical tasks, tools used

### Sales Agent
- Department: sales | Skills: email_outreach, pitch_deck_generation, linkedin_prospecting
- Typical tasks, tools used

### Marketing Agent
- Department: marketing | Skills: content_generation, web_research
- Typical tasks, tools used

### Support Agent
- Department: support | Skills: web_research
- Typical tasks, tools used

### HR Agent
- Department: hr | Skills: data_analysis
- Typical tasks, tools used

### Research Agent (Special)
- Department: research | Skills: deep_research, source_verification, web_research
- Trigger: message contains research keywords → task["agent"]="research"
- Agentic web-search loop (up to 8 iterations)

### Developer Agent (Special)
- Department: developer | Skills: code_generation, code_review, code_execution, api_integration, test_generation
- Trigger: message contains code/build keywords → task["agent"]="developer"
- Runs Claude Code headless subprocess

### Scheduler Agent (Special)
- Department: scheduler | Skills: schedule_management, cron_validation, job_monitoring, beat_sync
- Trigger: scheduler keywords → task["agent"]="scheduler"

## How Agents Work Together
- Routing flow diagram (Mermaid): User message → chat.py → router.py → Agent
- AgentRegistry: DB-backed lookup, skill-based discovery
- Delegation chain: delegate_task() → Celery → agent_task_log parent/child
- RAG namespace isolation (each agent's knowledge stays private)

## Skills Catalogue
Table: Skill name | Agent | Description | Tools provided
```

---

### Task 3 — User Guide: Agentic Features (docs/USER_GUIDE_AGENTIC.md)

A non-technical guide for business users on how to use and get the most from agentic capabilities. Structure:

```
## What are Agentic Features?
Plain-language explanation of AI agents vs. simple chatbot

## Your AI Team
Who each agent is, their department, what they're best at (non-technical language)

## How to Talk to the AI
- Natural language examples by department/scenario
- How to phrase requests for best results

## Triggering Special Agents
### Research Agent
- Sample prompts: "Research our top 5 competitors in Singapore"
- What it does (web search loop, synthesises report)
- Expected output format

### Developer Agent
- Sample prompts: "Build a Python script to process our leads CSV"
- What it does, expected output

### Scheduler Agent
- Sample prompts: "Schedule a weekly sales report every Monday at 9am SGT"
- Cron format explanation (SGT → UTC)
- Managing scheduled jobs (list, trigger, delete)

## Cross-Department Requests (Orchestration)
- What triggers multi-agent orchestration (keywords: "compare", "across departments", etc.)
- What happens step-by-step (Management Agent orchestrates → sub-agents → synthesised report)
- Example: "Compare sales and finance performance this quarter"

## Scheduled Jobs Reference
- Create, list, trigger, delete
- Timezone guide (SGT/HKT → UTC conversion table)
- Rate limits (10 jobs max, 15 min minimum interval)

## File Storage Guide
- Personal vs. Department vs. Company folders
- How to request file delivery to specific folders

## Tips & Tricks
- How to attach files for analysis (PDF, image)
- How to request output in different formats (PDF, PPTX, CSV)
- Using the scheduler for automated reports
```

---

## Source Files for Docs Agent to Read

**Key source files (read-only, for accuracy):**
- `docs/Mezzofy_AI_Assistant_Features_List.txt` — existing baseline
- `server/app/agents/agent_registry.py` — SAMPLE_AGENTS seed data (9 agents, their skills)
- `server/app/agents/management_agent.py` — _is_cross_department_task keywords, plan_and_orchestrate flow
- `server/app/agents/research_agent.py` — can_handle(), capabilities
- `server/app/agents/developer_agent.py` — can_handle(), capabilities
- `server/app/agents/scheduler_agent.py` — _SYSTEM_PROMPT, rules
- `server/app/skills/available/*.yaml` — skill metadata (capabilities, tool names)
- `server/scripts/migrate.py` — agents table seed data (skills per agent)
- `.claude/coordination/memory.md` — key patterns and decisions for accuracy

**Do NOT read:** Full LLM client code, test files, infrastructure files.

---

## Quality Gate

Lead reviews all 3 docs for:
- [ ] Accuracy — does it match the actual code? (spot-check agents' skills lists)
- [ ] Completeness — all 9 agents documented, all 11 skills mentioned
- [ ] User-friendliness — non-technical users can follow USER_GUIDE_AGENTIC.md
- [ ] Mermaid diagrams render without syntax errors
- [ ] No broken cross-references between documents

---

## Output Summary

| File | Type | Audience |
|------|------|---------|
| `docs/Mezzofy_AI_Assistant_Features_List_v2.0.md` | Features reference | Admins, PMs |
| `docs/AGENTS.md` | Architecture reference | Developers, Admins |
| `docs/USER_GUIDE_AGENTIC.md` | User guide | All business users |
