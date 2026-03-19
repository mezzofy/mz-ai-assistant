# Plan: Agent Enhancement v2.0 — Users vs Agents Separation & Agentic Team Upgrade
**Workflow:** change-request
**Date:** 2026-03-19
**Created by:** Lead Agent
**Source:** docs/AGENT_ENHANCEMENT_PROMPT.md

---

## Phase 0 Audit Findings

**What EXISTS (current state):**
- `agent_tasks` DB table (Celery task tracking only — NOT the new agent_task_log)
- `base_agent.py` — basic abstract class, NO delegation/logging methods
- `agent_registry.py` — module-level dict mapping dept→class, NO DB backing, NO AgentRegistry class
- `research_agent.py` — v1.23.0 web-search loop (minimal; no market_intelligence/competitive_analysis etc.)
- `developer_agent.py` — v1.23.0 Claude Code subprocess (minimal; no review_code/debug_code etc.)
- `scheduler_agent.py` — v1.25.0 CRUD scheduler (functional; no validate_cron/health_report etc.)
- `management_agent.py` — KPI dashboards only; NO plan_and_orchestrate()
- `tasks.py` — has process_agent_task; NO process_delegated_agent_task
- 7 skill files (none for Research/Developer/Scheduler agents)
- NO knowledge/ namespace directories

**What DOES NOT EXIST (needs to be built):**
- `agents` DB table (persistent agent records with skill manifest)
- `agent_task_log` DB table (parent/child task chain tracking)
- `AgentRegistry` class (DB-backed, with load()/get()/find_by_skill()/find_capable_agent())
- BaseAgent new methods: delegate_task(), await_delegation(), log_task_start/complete/failed(), requires_skill(), can_handle_with_delegation(), _load_knowledge()
- ManagementAgent: plan_and_orchestrate(), _is_cross_department_task()
- process_delegated_agent_task Celery task + get_agent_by_id() helper
- knowledge/ namespace directories (9 namespaces + shared)
- 11 new skill files for Research/Developer/Scheduler agents

**Key project decision:** Project uses migrate.py (NOT Alembic) — add tables there, not via Alembic migrations.

---

## Task Breakdown

| # | Task | Agent | Scope | Depends On | Est. Sessions | Status |
|---|------|-------|-------|-----------|:-------------:|--------|
| 1 | DB tables: agents + agent_task_log in migrate.py | Backend | server/scripts/ | None | 1 | NOT STARTED |
| 2 | New DB-backed AgentRegistry class + keep backward-compat | Backend | server/app/agents/agent_registry.py | Task 1 | 1 | NOT STARTED |
| 3 | Extend BaseAgent with delegation + logging + _load_knowledge() | Backend | server/app/agents/base_agent.py | Task 1 | 1 | NOT STARTED |
| 4 | Extend ManagementAgent: plan_and_orchestrate() + _is_cross_department_task() | Backend | server/app/agents/management_agent.py | Tasks 2,3 | 1 | NOT STARTED |
| 5 | New Celery task: process_delegated_agent_task + get_agent_by_id() | Backend | server/app/tasks/tasks.py | Tasks 1,2,3 | 1 | NOT STARTED |
| 6 | Update Router to use AgentRegistry + department→agent_id guard | Backend | server/app/tasks/tasks.py + router | Tasks 2,3 | 1 | NOT STARTED |
| 7 | Create knowledge/ namespace directories + README stubs | Backend | server/knowledge/ | None | 1 | NOT STARTED |
| 8 | Create 11 new skill files for Research/Developer/Scheduler agents | Backend | server/app/skills/available/ | None | 1 | NOT STARTED |
| 9 | FastAPI startup: register AgentRegistry.load() in main.py lifespan | Backend | server/main.py | Task 2 | 1 | NOT STARTED |
| 10 | Write test_agent_separation.py (16 tests per Phase 9 spec) | Tester | server/tests/ | Tasks 1-9 | 1 | NOT STARTED |

**Total Backend sessions: ~4–5 (tasks 1–9)**
**Total Tester sessions: ~1 (task 10)**

---

## Parallel Opportunities
- Tasks 7 and 8 can run in parallel with Tasks 1–6 (no dependencies)
- Task 10 starts only after ALL backend tasks complete

---

## Quality Gates

**Gate 1 (after Tasks 1–3):** Lead reviews DB schema + BaseAgent new methods
**Gate 2 (after Tasks 4–6):** Lead reviews ManagementAgent orchestration + Router + Celery
**Gate 3 (after Tasks 7–9):** Lead reviews knowledge dirs + skills + startup wiring
**Gate 4 (after Task 10):** Lead reviews all 16 tests pass

---

## Acceptance Criteria (from AGENT_ENHANCEMENT_PROMPT.md)

**Separation verification:**
- [ ] users table has NO agent-related columns
- [ ] agents table has NO user authentication columns
- [ ] JWT token payload references user_id only (never agent_id)
- [ ] All Celery tasks carry agent_id as separate field (never user_id as proxy)
- [ ] Router resolves: user_department → agent_id via agent_registry (not directly to class)
- [ ] Management Agent orchestration tasks appear in agent_task_log with parent/child chain
- [ ] No agent can read knowledge files from another agent's namespace

**All-additive rule:** No existing working code is modified in a breaking way — only additions and targeted non-breaking extensions.

---

## Implementation Notes for Backend Agent

### DB Migration (Task 1) — add to migrate.py
Add two new CREATE TABLE IF NOT EXISTS blocks after the existing `agent_tasks` table:
1. `agents` table — see full schema in docs/AGENT_ENHANCEMENT_PROMPT.md Lines 89–207
2. `agent_task_log` table — see full schema in Lines 213–266
Add seed INSERT for all 9 agents with `ON CONFLICT (id) DO NOTHING`

### AgentRegistry (Task 2) — extend agent_registry.py
Add `AgentRegistry` class ABOVE the existing module-level functions. Keep `get_agent_for_task()` and `AGENT_MAP` fully intact (backward compatible). New class:
- `async def load(self)` — loads from agents DB table into `self._agents: dict`
- `def get(agent_id)`, `get_by_department(dept)`, `find_by_skill(skill)`, `find_capable_agent(task_type)`, `all_active()`, `get_orchestrator()`
- Module-level singleton: `agent_registry = AgentRegistry()`

### BaseAgent (Task 3) — extend base_agent.py
ADD new methods (do NOT touch __init__ or existing abstract methods):
- `async def delegate_task(target_agent_id, task, parent_task_id)` → Celery enqueue + agent_task_log insert
- `async def await_delegation(task_id, timeout_seconds=300)` → Redis pub/sub poll
- `def requires_skill(skill_name)` → checks self.agent_record["skills"]
- `def can_handle_with_delegation(task, agent_registry)` → returns (bool, list[agent_id])
- `async def log_task_start(task, parent_task_id=None)` → INSERT agent_task_log, return task_id
- `async def log_task_complete(task_id, result)` → UPDATE agent_task_log
- `async def log_task_failed(task_id, error)` → UPDATE agent_task_log
- `def _load_knowledge()` → loads from knowledge/{memory_namespace}/ + knowledge/shared/

Note: `self.agent_record` must be optionally loadable. BaseAgent.__init__ signature stays unchanged — agents load their record lazily: `self.agent_record: Optional[dict] = None`. load_agent_record() called lazily or injected.

### ManagementAgent (Task 4) — extend management_agent.py
Add AT THE TOP of execute() (before existing logic):
```python
if self._is_cross_department_task(task):
    return await self.plan_and_orchestrate(task)
```
Add new methods:
- `async def plan_and_orchestrate(task)` — LLM decompose → log plan → execute sub-tasks → synthesise → deliver
- `def _is_cross_department_task(task)` — keyword-based detection (e.g. "and sales", "compare", multi-dept keywords)

### tasks.py (Task 5)
ADD alongside existing process_agent_task:
- `process_delegated_agent_task` Celery task with Redis pub/sub result publish
- `get_agent_by_id(agent_id)` helper with full AGENT_ID_MAP including all 9 agents

### Knowledge Directories (Task 7)
Create in server/knowledge/:
- management/, finance/, sales/, marketing/, support/, hr/, research/, developer/, developer/schema/, scheduler/, shared/
- Each directory gets a .gitkeep + README.md stub

### New Skills (Task 8)
Create in server/app/skills/available/:
Research: deep_research.py, source_verification.py
Developer: code_generation.py, code_review.py, code_execution.py, api_integration.py, test_generation.py
Scheduler: schedule_management.py, cron_validation.py, job_monitoring.py, beat_sync.py
Each follows BaseTool pattern from existing skills. See docs/AGENT_ENHANCEMENT_PROMPT.md Lines 1053–1073 for YAML+Python structure.

---

## Files to Create/Modify

**New files:**
- `server/knowledge/` directories (11 dirs + stubs)
- `server/app/skills/available/deep_research.py`
- `server/app/skills/available/source_verification.py`
- `server/app/skills/available/code_generation.py`
- `server/app/skills/available/code_review.py`
- `server/app/skills/available/code_execution.py`
- `server/app/skills/available/api_integration.py`
- `server/app/skills/available/test_generation.py`
- `server/app/skills/available/schedule_management.py`
- `server/app/skills/available/cron_validation.py`
- `server/app/skills/available/job_monitoring.py`
- `server/app/skills/available/beat_sync.py`
- `server/tests/test_agent_separation.py` (Tester)

**Modified files (additive only):**
- `server/scripts/migrate.py` — add agents + agent_task_log tables + seed data
- `server/app/agents/agent_registry.py` — add AgentRegistry class (keep existing functions)
- `server/app/agents/base_agent.py` — add 8 new methods
- `server/app/agents/management_agent.py` — add 2 new methods + routing check
- `server/app/tasks/tasks.py` — add process_delegated_agent_task + get_agent_by_id()
- `server/main.py` — add agent_registry.load() to startup lifespan

---

## Backend Agent Resume Instructions

After booting: read docs/AGENT_ENHANCEMENT_PROMPT.md (full file) for implementation details.
Start with Task 1 (migrate.py DB tables), then Tasks 2+3 in the same session, then Tasks 4+5, then 6+7+8+9.
All changes ADDITIVE — never remove or break existing functions.
Follow lazy inline import pattern for all new DB/Celery calls.
agent_record on BaseAgent must be optional (None default) — not all code paths load from DB.
