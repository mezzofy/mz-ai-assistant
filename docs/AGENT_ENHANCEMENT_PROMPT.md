# Claude Code CLI Prompt — Users vs Agents Separation & Agentic Team Enhancement
## Mezzofy AI Assistant · Architecture Audit + Upgrade

---

## CONTEXT — What We Are Fixing and Why

The current codebase blurs two fundamentally different entities:

- **Users** — human Mezzofy staff who authenticate via the mobile app, send messages, and receive responses. They have departments, roles, and permissions. They are rows in the `users` table. They log in with JWT.

- **Agents** — autonomous AI team members (Finance, Sales, Marketing, Support, HR, Management, **Research, Developer, Scheduler**). They have skills, RAG memory, tool access, and the ability to work in the background without any human present. They are currently defined only as Python class files with no persistent identity, no registry, no inter-agent communication protocol, and no ability to delegate to each other.

> **Note:** Research, Developer, and Scheduler are **special-purpose cross-departmental agents** — they do not belong to a single business department. They operate as shared infrastructure agents: Research surfaces information and intelligence for any agent that needs it; Developer builds, maintains, and debugs code and integrations; Scheduler manages the full lifecycle of cron jobs and scheduled tasks on behalf of all agents and users. All three can be delegated to by the Management Agent and by other specialist agents.

**The goal of this prompt is:**
1. Audit the current codebase to confirm exactly where the two entities are conflated or confused.
2. Establish Agents as first-class persistent entities with their own DB table, registry, skill manifest, and memory namespace — completely separate from the `users` table.
3. Implement inter-agent communication: any agent can request work from another agent when a required skill is not in its own set.
4. Upgrade the Management Agent to act as an orchestrator that can decompose a complex task plan and spawn sub-tasks to the appropriate specialist agents, collecting results and assembling a final output.
5. All changes must be additive — no existing working code is modified or deleted.

---

## PHASE 0 — Codebase Audit (Run This First)

Before writing any code, read and report on the following:

```
Audit targets:

[ ] server/app/models/  OR  server/scripts/migrate.py
    → Does a separate `agents` table exist, or are agents only Python classes?
    → Does the `users` table have any agent-related columns that should not be there?
    → Are there any foreign keys referencing agents by Python class name (string)?

[ ] server/agents/base_agent.py
    → Does BaseAgent have an agent_id, a persistent identity, or a DB record?
    → Is there any mechanism for one agent to call another agent's execute()?
    → Does execute() accept a caller_agent_id context for sub-task tracking?

[ ] server/agents/management_agent.py
    → Can the Management Agent currently break a task into sub-tasks?
    → Can it dispatch sub-tasks to other agents and await results?
    → Is there a task_plan structure, or does it just run tools itself?

[ ] server/agents/research_agent.py  (may or may not exist yet)
    → Does it exist? If yes, what skills and tools does it currently declare?
    → Is it registered in AGENT_MAP / router?

[ ] server/agents/developer_agent.py  (may or may not exist yet)
    → Does it exist? If yes, what skills and tools does it currently declare?
    → Does it have code execution, git, or API testing capabilities?

[ ] server/agents/scheduler_agent.py  (may or may not exist yet)
    → Does it exist? If yes, what does it manage — beat_schedule only, or also DB jobs?
    → Can it create, pause, resume, and delete scheduled jobs programmatically?

[ ] server/app/router.py
    → Does the router ever route to agents using user identity fields?
    → Is there any check that guards against routing user messages to the wrong agent?

[ ] server/scheduler/tasks.py
    → Are Celery tasks associated with an agent_id or just an agent name string?
    → Is there a parent_task_id concept for tracking sub-tasks spawned by the Management Agent?

[ ] server/skills/skill_registry.py  OR  skill_loader.py
    → Are skills associated with an agent_id, or just a string name like "sales"?
    → Is there a central registry mapping agent → list of skill names?

[ ] server/knowledge/  directory
    → Are knowledge base (RAG) files organised by agent or mixed together?
    → Is there an index mapping which files belong to which agent?

[ ] Any existing `agent_tasks` table
    → Does it track inter-agent delegation (parent/child task relationships)?

Report findings as a numbered list before proceeding to Phase 1.
```

---

## PHASE 1 — Establish Agents as First-Class Entities

### 1.1 New `agents` DB Table

Add via a new Alembic migration: `server/alembic/versions/XXXX_agents_as_entities.py`

```sql
CREATE TABLE IF NOT EXISTS agents (
    id              VARCHAR(32) PRIMARY KEY,
    -- e.g. "agent_finance", "agent_sales", "agent_management"

    name            VARCHAR(64) NOT NULL,
    -- e.g. "Finance Agent", "Sales Agent"

    display_name    VARCHAR(64) NOT NULL,
    -- e.g. "Fiona (Finance)", "Sam (Sales)"
    -- Each agent has a persona name for Teams/email signatures

    department      VARCHAR(32) NOT NULL,
    -- "finance" | "sales" | "marketing" | "support" | "hr" | "management"

    description     TEXT,
    -- Short bio: "I handle financial reporting, P&L statements, and budget analysis."

    skills          JSONB NOT NULL DEFAULT '[]',
    -- Array of skill names this agent owns
    -- e.g. ["financial_reporting", "data_analysis"]

    tools_allowed   JSONB NOT NULL DEFAULT '[]',
    -- Array of tool names this agent may invoke directly
    -- e.g. ["outlook_send_email", "pdf_generator", "database_query"]

    llm_model       VARCHAR(64) NOT NULL DEFAULT 'claude-haiku-4-5-20251001',
    -- Which LLM this agent uses by default

    memory_namespace VARCHAR(64) UNIQUE NOT NULL,
    -- Subdirectory key for this agent's RAG knowledge files
    -- e.g. "finance", "sales" — maps to /knowledge/{memory_namespace}/

    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    can_be_spawned  BOOLEAN NOT NULL DEFAULT TRUE,
    -- Management Agent is the only one that spawns others;
    -- all specialist agents can BE spawned by Management Agent

    is_orchestrator BOOLEAN NOT NULL DEFAULT FALSE,
    -- TRUE only for Management Agent

    max_concurrent_tasks  INTEGER NOT NULL DEFAULT 2,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Seed all 9 agents immediately after table creation:
INSERT INTO agents (id, name, display_name, department, description, skills, tools_allowed, llm_model, memory_namespace, is_orchestrator, can_be_spawned)
VALUES
  ('agent_management', 'Management Agent', 'Max (Management)', 'management',
   'I oversee cross-department operations, break down complex tasks, delegate to specialist agents, and synthesise final results.',
   '["data_analysis","web_research"]',
   '["database_query","teams_post_message","outlook_send_email","pdf_generator"]',
   'claude-sonnet-4-6', 'management', TRUE, FALSE),

  ('agent_finance', 'Finance Agent', 'Fiona (Finance)', 'finance',
   'I handle financial statements, P&L reports, budgets, invoices, and cost analysis.',
   '["financial_reporting","data_analysis"]',
   '["database_query","pdf_generator","csv_ops","outlook_send_email"]',
   'claude-haiku-4-5-20251001', 'finance', FALSE, TRUE),

  ('agent_sales', 'Sales Agent', 'Sam (Sales)', 'sales',
   'I manage lead generation, CRM updates, pitch decks, and prospect outreach.',
   '["linkedin_prospecting","email_outreach","pitch_deck_generation","web_research"]',
   '["crm_query","crm_update","outlook_send_email","pptx_generator","linkedin_search"]',
   'claude-sonnet-4-6', 'sales', FALSE, TRUE),

  ('agent_marketing', 'Marketing Agent', 'Maya (Marketing)', 'marketing',
   'I create website content, campaign copy, playbooks, and social media posts.',
   '["content_generation","web_research"]',
   '["pdf_generator","docx_ops","outlook_send_email","teams_post_message"]',
   'claude-haiku-4-5-20251001', 'marketing', FALSE, TRUE),

  ('agent_support', 'Support Agent', 'Suki (Support)', 'support',
   'I analyse support tickets, surface patterns, draft customer replies, and recommend escalations.',
   '["data_analysis","email_outreach"]',
   '["database_query","outlook_send_email","teams_post_message"]',
   'claude-haiku-4-5-20251001', 'support', FALSE, TRUE),

  ('agent_hr', 'HR Agent', 'Hana (HR)', 'hr',
   'I handle payroll queries, leave balances, headcount reports, onboarding checklists, and offboarding summaries.',
   '["data_analysis","email_outreach"]',
   '["database_query","outlook_send_email","pdf_generator"]',
   'claude-haiku-4-5-20251001', 'hr', FALSE, TRUE),

  -- ---------------------------------------------------------------
  -- SPECIAL-PURPOSE CROSS-DEPARTMENTAL AGENTS
  -- These three serve all departments; department = their function
  -- ---------------------------------------------------------------

  ('agent_research', 'Research Agent', 'Rex (Research)', 'research',
   'I am a dedicated research specialist. I perform deep web research, market intelligence,
   competitive analysis, and fact-finding for any agent or user across all departments.
   I surface structured, cited findings so other agents can act on them immediately.',
   '["web_research","data_analysis","deep_research","source_verification"]',
   '["browser_ops","scraping_ops","search_web","database_query","pdf_generator","csv_ops"]',
   'claude-sonnet-4-6', 'research', FALSE, TRUE),

  ('agent_developer', 'Developer Agent', 'Dev (Developer)', 'developer',
   'I write, review, debug, and maintain code and system integrations. I can generate
   Python scripts, FastAPI endpoints, SQL migrations, Celery tasks, shell scripts,
   and automation tools. I run code safely in sandboxed environments and produce
   tested, documented deliverables.',
   '["code_generation","code_review","code_execution","api_integration","test_generation"]',
   '["bash_exec","file_ops","database_query","git_ops","http_client","pdf_generator","docx_ops"]',
   'claude-sonnet-4-6', 'developer', FALSE, TRUE),

  ('agent_scheduler', 'Scheduler Agent', 'Sched (Scheduler)', 'scheduler',
   'I manage the full lifecycle of scheduled and automated tasks across all departments.
   I can create, modify, pause, resume, and delete Celery Beat jobs and user-defined
   scheduled_jobs. I validate cron expressions, prevent scheduling conflicts, and
   report on job health and run history.',
   '["schedule_management","cron_validation","job_monitoring","beat_sync"]',
   '["database_query","celery_inspect","beat_schedule_ops","teams_post_message","outlook_send_email"]',
   'claude-haiku-4-5-20251001', 'scheduler', FALSE, TRUE)

ON CONFLICT (id) DO NOTHING;
```

### 1.2 New `agent_task_log` DB Table

Track every task — including sub-tasks spawned by the Management Agent.

```sql
CREATE TABLE IF NOT EXISTS agent_task_log (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    agent_id        VARCHAR(32) NOT NULL REFERENCES agents(id),
    -- Which agent executed this task

    parent_task_id  UUID REFERENCES agent_task_log(id),
    -- NULL if this is a top-level task;
    -- SET if this was spawned as a sub-task by the Management Agent

    requested_by_agent_id  VARCHAR(32) REFERENCES agents(id),
    -- NULL if triggered by a human user;
    -- SET if triggered by another agent (e.g. Management → Sales)

    triggered_by_user_id   VARCHAR(64),
    -- The human user_id from the users table who originated the request
    -- (preserved through delegation chain)

    source          VARCHAR(32) NOT NULL,
    -- "mobile" | "scheduler" | "webhook" | "agent_delegation"

    task_type       VARCHAR(64),
    -- e.g. "generate_financial_report", "lead_research", "pitch_deck"

    task_input      JSONB,
    -- Full task dict passed to agent.execute()

    task_plan       JSONB,
    -- For Management Agent: the decomposed sub-task plan
    -- [{ step: 1, agent: "agent_finance", task: "...", status: "pending" }, ...]

    status          VARCHAR(16) NOT NULL DEFAULT 'queued',
    -- "queued" | "running" | "completed" | "failed" | "cancelled"

    result_summary  TEXT,
    -- Human-readable outcome summary

    result_artifacts JSONB DEFAULT '[]',
    -- List of artifact IDs produced

    error_message   TEXT,
    duration_ms     INTEGER,

    queued_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ
);

CREATE INDEX idx_agent_task_log_agent_id     ON agent_task_log(agent_id);
CREATE INDEX idx_agent_task_log_parent       ON agent_task_log(parent_task_id);
CREATE INDEX idx_agent_task_log_user         ON agent_task_log(triggered_by_user_id);
CREATE INDEX idx_agent_task_log_status       ON agent_task_log(status);
```

---

## PHASE 2 — Update BaseAgent for Persistent Identity & Inter-Agent Communication

### File: `server/agents/base_agent.py`

**DO NOT rewrite this file.** Extend it by adding the following methods and constructor changes.

```python
# Add to BaseAgent.__init__:
#   self.agent_id: str       — loaded from agents DB table on startup
#   self.agent_record: dict  — full row from agents table
#   self.skill_registry      — injected SkillRegistry instance

# Add these NEW methods (do not modify existing methods):

async def delegate_task(self, target_agent_id: str, task: dict, parent_task_id: str) -> dict:
    """
    Request work from another specialist agent.
    Called by any agent when a required skill is outside its own skill set.

    Steps:
    1. Look up target agent in AgentRegistry (new class, see Phase 3).
    2. Verify target agent is active and can_be_spawned=True.
    3. Enqueue a Celery task: process_agent_task(task, agent_id=target_agent_id,
       parent_task_id=parent_task_id, requested_by_agent_id=self.agent_id).
    4. Insert a row into agent_task_log with status="queued", parent_task_id set.
    5. Return: { task_id, agent_id: target_agent_id, status: "queued" }

    This is NON-BLOCKING by default. The calling agent continues its own work.
    Use await_delegation() if the result is needed before proceeding.
    """

async def await_delegation(self, task_id: str, timeout_seconds: int = 300) -> dict:
    """
    Block until a delegated sub-task completes (or times out).
    Polls agent_task_log every 5 seconds.
    Used by Management Agent when it needs sub-results before assembling final output.
    Returns the result_summary and result_artifacts from agent_task_log.
    """

def requires_skill(self, skill_name: str) -> bool:
    """Returns True if skill_name is in this agent's skills list (from DB record)."""

def can_handle_with_delegation(self, task: dict, agent_registry) -> tuple[bool, list[str]]:
    """
    Check if this agent can handle a task, possibly by delegating parts.
    Returns: (can_handle: bool, delegation_needed_to: list[agent_id])
    """

async def log_task_start(self, task: dict, parent_task_id=None) -> str:
    """Insert agent_task_log row with status=running. Return task_id (UUID)."""

async def log_task_complete(self, task_id: str, result: dict):
    """Update agent_task_log row: status=completed, result_summary, duration_ms."""

async def log_task_failed(self, task_id: str, error: str):
    """Update agent_task_log row: status=failed, error_message."""
```

---

## PHASE 3 — Agent Registry

### New file: `server/agents/agent_registry.py`

This is a singleton that loads agent definitions from the `agents` DB table at startup and provides lookup by ID, department, and required skill.

```python
class AgentRegistry:
    """
    Central registry for all active AI agents.
    Loaded from the `agents` DB table at application startup.
    Injected into Router, Management Agent, and BaseAgent.
    """

    async def load(self):
        """Load all agents from DB into memory dict keyed by agent_id."""

    def get(self, agent_id: str) -> dict:
        """Return agent record dict. Raise KeyError if not found."""

    def get_by_department(self, department: str) -> dict:
        """Return agent record for the given department."""

    def find_by_skill(self, skill_name: str) -> list[dict]:
        """Return all agents that have skill_name in their skills list."""

    def find_capable_agent(self, task_type: str) -> dict | None:
        """
        Find the best agent for a given task type.
        Tries:
        1. Exact skill name match
        2. Department keyword match (fallback)
        Returns agent record or None.
        """

    def all_active(self) -> list[dict]:
        """Return all agents where is_active=True."""

    def get_orchestrator(self) -> dict:
        """Return the agent where is_orchestrator=True (Management Agent)."""
```

Register as a FastAPI startup event in `main.py`:
```python
@app.on_event("startup")
async def startup():
    await agent_registry.load()
    logger.info(f"Agent registry loaded: {[a['id'] for a in agent_registry.all_active()]}")
```

---

## PHASE 4 — Upgrade Management Agent as Orchestrator

### File: `server/agents/management_agent.py`

**DO NOT rewrite existing methods.** Add the following new capability alongside existing code.

#### New Method: `plan_and_orchestrate(task)`

This is the core new power of the Management Agent. When it receives a complex cross-department task, it:

1. Uses the LLM to decompose the task into a structured plan of sub-tasks, each assigned to a specific agent.
2. Records the plan in `agent_task_log.task_plan`.
3. Dispatches each sub-task via `self.delegate_task()`.
4. Optionally awaits results using `self.await_delegation()` for sequential steps.
5. Synthesises all results into a final executive summary.
6. Delivers via Teams + email.

```python
async def plan_and_orchestrate(self, task: dict) -> dict:
    """
    Orchestrate a multi-agent task plan.

    Step 1 — Plan decomposition (LLM call):
      Prompt: "You are the Management Agent. Break down this task into
               sub-tasks, each assigned to the most capable specialist agent.
               Available agents: {agent_registry.all_active()}.
               Return JSON: [{ step, agent_id, task_description, depends_on_step }]"

    Step 2 — Log the plan:
      INSERT agent_task_log with task_plan = plan JSON, status = "running"

    Step 3 — Execute plan:
      For each step in plan (respecting depends_on_step ordering):
        - If parallel (no dependency): delegate_task() without awaiting
        - If sequential (depends on prior step): await_delegation() before proceeding

    Step 4 — Synthesise:
      Collect all sub-task result_summaries.
      LLM call: "Synthesise these results into an executive summary: {results}"

    Step 5 — Deliver:
      teams_post_message → #management channel
      outlook_send_email → requestor (if triggered by user)
      Update agent_task_log: status=completed, result_summary=synthesis

    Return: { summary, task_id, sub_tasks: [...], artifacts: [...] }
    """

async def can_delegate(self) -> bool:
    """Always True for Management Agent."""
    return True
```

#### Trigger for Orchestration Mode

In Management Agent's `execute()` method, add a routing check at the top:
```python
# At the START of execute(), before existing logic — do not remove existing logic:
if self._is_cross_department_task(task):
    return await self.plan_and_orchestrate(task)
# Otherwise fall through to existing single-agent handling...

def _is_cross_department_task(self, task: dict) -> bool:
    """
    Returns True if the task requires skills from more than one agent.
    Determined by: LLM classification OR explicit keywords in task message
    (e.g. "report from finance and sales", "compare marketing vs support metrics").
    """
```

---

## PHASE 5 — Update Router to Use Agent Registry

### File: `server/app/router.py`

**DO NOT rewrite the router.** Make these targeted additions:

1. Inject `agent_registry` into the Router class constructor.
2. Replace any hardcoded agent class instantiation (e.g. `SalesAgent()`) with `agent_registry.get_by_department(dept)` lookups to retrieve the agent_id, then resolve to the Python class via the existing `AGENT_MAP`.
3. Add a guard: if `task["source"] == "mobile"` and the resolved agent_id's `department` does not match `task["user_department"]`, log a warning and re-route to the correct agent.
4. Pass `agent_registry` into each agent's `execute()` call so agents can call `find_by_skill()` for delegation.

---

## PHASE 6 — Update Celery Task for Agent Delegation

### File: `server/scheduler/tasks.py`

**DO NOT modify the existing `process_agent_task` function.**  
Add a new task alongside it:

```python
@celery_app.task(bind=True, max_retries=3, name="process_delegated_agent_task")
def process_delegated_agent_task(self, task_data: dict, agent_id: str,
                                  parent_task_id: str, requested_by_agent_id: str):
    """
    Execute a sub-task delegated by another agent (typically Management Agent).
    Same mechanics as process_agent_task but:
    - Resolves agent by agent_id (not department)
    - Updates agent_task_log with parent_task_id and requested_by_agent_id
    - On completion: publishes result to Redis pub/sub channel
      key = "agent_result:{parent_task_id}" so await_delegation() can pick it up
    - On failure: retries up to 3 times, then logs failed status
    """
    agent = get_agent_by_id(agent_id)   # new helper, see below
    try:
        # Update log: status=running
        result = agent.execute(task_data)
        # Update log: status=completed, result_summary
        # Publish to Redis: PUBLISH agent_result:{parent_task_id} <result_json>
        return result
    except Exception as e:
        # Update log: status=failed
        raise self.retry(exc=e, countdown=30)
```

Add helper function (new, in `tasks.py`):
```python
def get_agent_by_id(agent_id: str):
    """
    Map agent_id string to Python agent class instance.
    AGENT_ID_MAP = {
        # Department agents
        "agent_finance":    FinanceAgent,
        "agent_sales":      SalesAgent,
        "agent_marketing":  MarketingAgent,
        "agent_support":    SupportAgent,
        "agent_hr":         HRAgent,
        "agent_management": ManagementAgent,
        # Special-purpose cross-departmental agents
        "agent_research":   ResearchAgent,
        "agent_developer":  DeveloperAgent,
        "agent_scheduler":  SchedulerAgent,
    }
    """
```

---

## PHASE 6B — Special-Purpose Agent Python Classes

Create three new agent files. Each follows the exact same `BaseAgent` pattern.

---

### `server/agents/research_agent.py`

```python
"""
Research Agent — Rex
Cross-departmental research specialist. Performs deep web research,
market intelligence, competitive analysis, and fact-finding on demand.
Can be invoked by any agent or user. Never belongs to a single department.
"""
from .base_agent import BaseAgent

RESEARCH_TRIGGERS = [
    "research", "find information", "look up", "investigate", "analyse the market",
    "competitive analysis", "market research", "background check", "fact check",
    "what do we know about", "deep dive", "intelligence report", "news about",
    "industry analysis", "trend analysis", "search for", "gather data on",
    "benchmark", "landscape report", "who is", "what is", "latest on",
]

class ResearchAgent(BaseAgent):
    """
    Rex — Research Agent
    Dedicated research specialist serving all departments.
    Primary consumers: Management Agent (for KPI context), Sales Agent
    (prospect research), Marketing Agent (competitor analysis).
    """

    def can_handle(self, task: dict) -> bool:
        if task.get("agent_override") == "research":
            return True
        message = task.get("message", "").lower()
        return any(t in message for t in RESEARCH_TRIGGERS)

    async def execute(self, task: dict) -> dict:
        """
        Route to the appropriate research workflow:
          - "web_research"        → research_web()
          - "market_intelligence" → market_intelligence()
          - "competitive_analysis"→ competitive_analysis()
          - "fact_verification"   → verify_facts()
          - "news_monitoring"     → news_summary()

        All results returned as structured JSON + optional PDF report.
        Rex never sends emails or posts to Teams unprompted —
        he returns results to the calling agent or user only.
        """
        task_id = await self.log_task_start(task)
        try:
            task_type = await self._classify_research_task(task)

            if task_type == "market_intelligence":
                result = await self.market_intelligence(task)
            elif task_type == "competitive_analysis":
                result = await self.competitive_analysis(task)
            elif task_type == "fact_verification":
                result = await self.verify_facts(task)
            elif task_type == "news_monitoring":
                result = await self.news_summary(task)
            else:
                result = await self.research_web(task)

            await self.log_task_complete(task_id, result)
            return result
        except Exception as e:
            await self.log_task_failed(task_id, str(e))
            raise

    async def research_web(self, task: dict) -> dict:
        """
        General-purpose web research workflow:
        1. _load_skill("web_research") + _load_skill("source_verification")
        2. search_web → gather top N sources on the topic
        3. browser_ops → fetch and parse full content from key sources
        4. LLM → synthesise findings into structured report with citations
        5. Optionally: pdf_generator → research brief PDF
        6. Return: { summary, findings: [{source, excerpt, url}], pdf_path? }
        """

    async def market_intelligence(self, task: dict) -> dict:
        """
        Market intelligence report workflow:
        1. web_research skill → search industry news, reports, analyst commentary
        2. data_analysis skill → structure quantitative data if found
        3. LLM → generate market intelligence brief:
           - Market size and growth trends
           - Key players and market share
           - Regulatory / macro environment
           - Opportunities and risks for Mezzofy
        4. pdf_generator → market intelligence PDF
        5. Return: brief + PDF artifact
        """

    async def competitive_analysis(self, task: dict) -> dict:
        """
        Competitor analysis workflow:
        1. For each competitor named in task:
           a. scraping_ops → scrape company website, pricing page, feature list
           b. web_research → recent news, funding, product updates
        2. LLM → side-by-side comparison table vs Mezzofy
        3. LLM → SWOT summary for Mezzofy's competitive position
        4. pdf_generator → competitive analysis PDF
        5. Return: comparison table + SWOT + PDF artifact
        """

    async def verify_facts(self, task: dict) -> dict:
        """
        Fact verification workflow:
        1. Extract claims from task message
        2. For each claim: search_web → find corroborating or contradicting sources
        3. LLM → verdict per claim: Verified / Unverified / Contradicted + sources
        4. Return: { claims: [{claim, verdict, confidence, sources}] }
        """

    async def news_summary(self, task: dict) -> dict:
        """
        News monitoring and summary workflow:
        1. search_web → latest news for topic/company/industry (last 7 days)
        2. LLM → summarise top stories with relevance scoring for Mezzofy
        3. Return: { stories: [{headline, summary, source, date, relevance_score}] }
        """

    async def _classify_research_task(self, task: dict) -> str:
        """LLM-classify into: web_research | market_intelligence |
           competitive_analysis | fact_verification | news_monitoring"""

    # Skills used:
    #   web_research        — search_web, browser_ops, scraping_ops
    #   deep_research       — multi-source synthesis, citation management
    #   data_analysis       — quantitative data structuring
    #   source_verification — credibility scoring, cross-referencing
```

---

### `server/agents/developer_agent.py`

```python
"""
Developer Agent — Dev
Cross-departmental software developer. Writes, reviews, debugs, and
maintains code, scripts, integrations, and automation for any department.
Executes code in a sandboxed environment. Never deploys to production
without explicit admin confirmation.
"""
from .base_agent import BaseAgent

DEVELOPER_TRIGGERS = [
    "write code", "write a script", "build", "create a function", "generate code",
    "fix this bug", "debug", "review this code", "refactor", "optimise",
    "create an endpoint", "add an api", "integrate", "automate",
    "write a migration", "create a celery task", "write tests", "unit test",
    "sql query", "write a query", "bash script", "shell script",
    "python script", "fastapi", "alembic", "explain this code",
    "what does this code do", "code review", "pull request", "git",
    "dockerfile", "requirements", "dependency", "install", "error in my code",
]

# Hard safety rules — never violate
PRODUCTION_DEPLOY_BLOCKED = True   # Dev never pushes to prod or restarts services
DANGEROUS_OPERATIONS = [
    "DROP TABLE", "DELETE FROM", "TRUNCATE",
    "rm -rf", "shutdown", "reboot", "kill",
    "systemctl restart", "systemctl stop",
]

class DeveloperAgent(BaseAgent):
    """
    Dev — Developer Agent
    Writes, reviews, and debugs code for any department.
    All code execution happens in an isolated sandbox.
    Production changes require explicit admin approval workflow.
    """

    def can_handle(self, task: dict) -> bool:
        if task.get("agent_override") == "developer":
            return True
        message = task.get("message", "").lower()
        return any(t in message for t in DEVELOPER_TRIGGERS)

    async def execute(self, task: dict) -> dict:
        """
        Route to the appropriate developer workflow:
          - "code_generation"   → generate_code()
          - "code_review"       → review_code()
          - "debugging"         → debug_code()
          - "code_execution"    → execute_code()
          - "api_integration"   → build_integration()
          - "test_generation"   → generate_tests()
          - "sql_query"         → write_sql()
          - "explanation"       → explain_code()
        """
        task_id = await self.log_task_start(task)
        try:
            task_type = await self._classify_dev_task(task)

            if task_type == "code_review":
                result = await self.review_code(task)
            elif task_type == "debugging":
                result = await self.debug_code(task)
            elif task_type == "code_execution":
                result = await self.execute_code(task)
            elif task_type == "api_integration":
                result = await self.build_integration(task)
            elif task_type == "test_generation":
                result = await self.generate_tests(task)
            elif task_type == "sql_query":
                result = await self.write_sql(task)
            elif task_type == "explanation":
                result = await self.explain_code(task)
            else:
                result = await self.generate_code(task)

            await self.log_task_complete(task_id, result)
            return result
        except Exception as e:
            await self.log_task_failed(task_id, str(e))
            raise

    async def generate_code(self, task: dict) -> dict:
        """
        Code generation workflow:
        1. _load_knowledge() → load codebase conventions from knowledge/developer/
        2. LLM → generate code with:
           - Correct style (PEP8, type hints, docstrings)
           - Consistent with existing patterns (FastAPI, BaseAgent, etc.)
           - Includes error handling and logging
        3. execute_code() → run in sandbox to verify it executes without error
        4. generate_tests() → generate pytest tests for the new code
        5. Return: { code, language, filename_suggestion, tests, execution_result }

        Safety: scan generated code for DANGEROUS_OPERATIONS before returning.
        If found: strip and warn user.
        """

    async def review_code(self, task: dict) -> dict:
        """
        Code review workflow:
        1. Parse submitted code (from message text or attached file)
        2. LLM → structured review:
           - Summary of what the code does
           - Bugs found (severity: Critical / High / Medium / Low)
           - Security vulnerabilities
           - Performance issues
           - Style / readability suggestions
           - Suggested improvements with corrected code snippets
        3. Return: { summary, issues: [{severity, line, description, fix}], score }
        """

    async def debug_code(self, task: dict) -> dict:
        """
        Debugging workflow:
        1. Parse code + error message / traceback from task
        2. LLM → root cause analysis of the error
        3. LLM → generate fix
        4. execute_code() → run fixed code in sandbox to confirm resolution
        5. Return: { root_cause, fix, fixed_code, sandbox_result }
        """

    async def execute_code(self, task: dict) -> dict:
        """
        Sandboxed code execution workflow:
        1. Safety check: scan for DANGEROUS_OPERATIONS — refuse if found
        2. bash_exec → run in isolated subprocess with:
           - timeout=30s hard limit
           - No network access (unless explicitly permitted)
           - No file system writes outside /tmp/sandbox/
        3. Capture stdout, stderr, exit code
        4. Return: { stdout, stderr, exit_code, duration_ms, safe: bool }

        NEVER execute code that touches production DB, restarts services,
        or modifies files outside the sandbox.
        """

    async def build_integration(self, task: dict) -> dict:
        """
        API/service integration workflow:
        1. Research target API: http_client → fetch API docs or OpenAPI spec
        2. LLM → generate integration code (FastAPI endpoint, Celery task, or tool)
        3. generate_tests() → write integration tests
        4. Return: { integration_code, tests, usage_example, setup_instructions }
        """

    async def generate_tests(self, task: dict) -> dict:
        """
        Test generation workflow:
        1. Parse target code from task
        2. LLM → generate pytest tests:
           - Unit tests for each function/method
           - Edge cases and error conditions
           - Mock dependencies (DB, external APIs, Redis)
        3. execute_code() → run tests in sandbox; report pass/fail
        4. Return: { test_code, test_results, coverage_estimate }
        """

    async def write_sql(self, task: dict) -> dict:
        """
        SQL query writing workflow:
        1. _load_knowledge() → load DB schema docs from knowledge/developer/schema/
        2. LLM → generate SQL query matching the request
        3. Safety check: only SELECT statements run in sandbox;
           DDL/DML returned as text only, never auto-executed
        4. Return: { sql, explanation, is_read_only, results_if_executed? }
        """

    async def explain_code(self, task: dict) -> dict:
        """
        Code explanation workflow:
        1. Parse code from task message or attachment
        2. LLM → plain-language explanation:
           - What the code does overall
           - Step-by-step walkthrough of key sections
           - Potential gotchas or non-obvious behaviours
        3. Return: { explanation, annotated_code }
        """

    async def _classify_dev_task(self, task: dict) -> str:
        """LLM-classify into: code_generation | code_review | debugging |
           code_execution | api_integration | test_generation | sql_query | explanation"""

    def _safety_scan(self, code: str) -> list[str]:
        """Scan code string for DANGEROUS_OPERATIONS. Return list of violations found."""
        return [op for op in DANGEROUS_OPERATIONS if op.upper() in code.upper()]

    # Skills used:
    #   code_generation  — LLM-based code writing, style enforcement
    #   code_review      — static analysis, vulnerability scanning
    #   code_execution   — sandboxed bash_exec, subprocess management
    #   api_integration  — HTTP client, OpenAPI parsing
    #   test_generation  — pytest scaffold generation
```

---

### `server/agents/scheduler_agent.py`

```python
"""
Scheduler Agent — Sched
Cross-departmental scheduling specialist. Manages the full lifecycle of
Celery Beat jobs and user-created scheduled_jobs. Acts as the single
source of truth for what is scheduled, when, and for whom.
Can be delegated to by any agent to schedule follow-up tasks.
"""
from .base_agent import BaseAgent

SCHEDULER_TRIGGERS = [
    "schedule", "schedule a task", "create a job", "set up a cron",
    "run every", "run daily", "run weekly", "run monthly", "run at",
    "automate this task", "set a reminder", "recurring task",
    "pause the job", "resume the job", "cancel the schedule",
    "what jobs are running", "show me scheduled tasks", "list all jobs",
    "job history", "run history", "last run", "next run",
    "trigger manually", "run now", "fire the job",
    "cron expression", "cron schedule", "is it scheduled",
    "when does it run", "how often does it run",
]

class SchedulerAgent(BaseAgent):
    """
    Sched — Scheduler Agent
    Manages cron jobs, scheduled_jobs table, and Celery Beat lifecycle.
    The only agent with write access to beat_schedule configuration.
    Other agents delegate TO Sched when they need to schedule follow-up work.
    """

    def can_handle(self, task: dict) -> bool:
        if task.get("agent_override") == "scheduler":
            return True
        message = task.get("message", "").lower()
        return any(t in message for t in SCHEDULER_TRIGGERS)

    async def execute(self, task: dict) -> dict:
        """
        Route to the appropriate scheduler workflow:
          - "create_job"       → create_scheduled_job()
          - "modify_job"       → modify_scheduled_job()
          - "pause_job"        → toggle_job(is_active=False)
          - "resume_job"       → toggle_job(is_active=True)
          - "delete_job"       → delete_scheduled_job()
          - "list_jobs"        → list_scheduled_jobs()
          - "job_history"      → get_job_history()
          - "manual_trigger"   → trigger_job_now()
          - "validate_cron"    → validate_cron_expression()
          - "health_check"     → jobs_health_report()
        """
        task_id = await self.log_task_start(task)
        try:
            action = await self._classify_scheduler_action(task)

            if action == "create_job":
                result = await self.create_scheduled_job(task)
            elif action == "modify_job":
                result = await self.modify_scheduled_job(task)
            elif action in ("pause_job", "resume_job"):
                result = await self.toggle_job(task, is_active=(action == "resume_job"))
            elif action == "delete_job":
                result = await self.delete_scheduled_job(task)
            elif action == "list_jobs":
                result = await self.list_scheduled_jobs(task)
            elif action == "job_history":
                result = await self.get_job_history(task)
            elif action == "manual_trigger":
                result = await self.trigger_job_now(task)
            elif action == "validate_cron":
                result = await self.validate_cron_expression(task)
            else:
                result = await self.jobs_health_report(task)

            await self.log_task_complete(task_id, result)
            return result
        except Exception as e:
            await self.log_task_failed(task_id, str(e))
            raise

    async def create_scheduled_job(self, task: dict) -> dict:
        """
        Create a new scheduled job workflow:
        1. LLM → extract job parameters from natural language:
           - name, description, target_agent_id, task_message
           - schedule (natural language → cron expression)
           - deliver_to (teams_channel, email list)
           - requested_by_user_id
        2. validate_cron_expression() → verify cron is valid and not conflicting
        3. INSERT into scheduled_jobs table
        4. beat_schedule_ops → add job to live Celery Beat schedule without restart
           (uses celery_app.conf.beat_schedule update + scheduler.store.sync())
        5. Return: { job_id, name, cron, next_run_at, confirmation_message }

        Cron conversion examples:
          "every Monday at 9AM" → "0 9 * * 1"  (UTC+8 → UTC: "0 1 * * 1")
          "daily at 6PM"        → "0 18 * * *" (UTC+8 → UTC: "0 10 * * *")
          "first of every month"→ "0 8 1 * *"  (UTC+8 → UTC: "0 0 1 * *")
        NOTE: All cron expressions stored as UTC in DB; displayed as HKT/SGT in UI.
        """

    async def modify_scheduled_job(self, task: dict) -> dict:
        """
        Modify an existing job's schedule, target agent, or delivery settings.
        1. Identify job by name or ID from task message
        2. LLM → extract which fields to change
        3. validate_cron_expression() if schedule is changing
        4. UPDATE scheduled_jobs table
        5. beat_schedule_ops → update live Celery Beat entry
        6. Return: { job_id, changes_applied, new_next_run_at }
        """

    async def toggle_job(self, task: dict, is_active: bool) -> dict:
        """
        Pause or resume a job.
        1. Identify job by name or ID
        2. UPDATE scheduled_jobs SET is_active = {is_active}
        3. beat_schedule_ops → remove from or add back to live Beat schedule
        4. Return: { job_id, is_active, message }
        """

    async def delete_scheduled_job(self, task: dict) -> dict:
        """
        Delete a scheduled job.
        1. Identify job; confirm it is a user-created job (not a built-in Beat job)
           — built-in jobs (weekly-kpi-report, etc.) cannot be deleted via Sched
        2. DELETE from scheduled_jobs table
        3. beat_schedule_ops → remove from live Beat schedule
        4. Return: { job_id, deleted: true, message }
        """

    async def list_scheduled_jobs(self, task: dict) -> dict:
        """
        List all scheduled jobs visible to the requesting user/agent.
        1. Query scheduled_jobs table (filter by department if user is not admin/management)
        2. celery_inspect → get active Beat schedule for built-in jobs
        3. LLM → format as human-readable summary with next_run_at in HKT
        4. Return: { jobs: [{id, name, schedule_hkt, target_agent, status, last_run, next_run}] }
        """

    async def get_job_history(self, task: dict) -> dict:
        """
        Return execution history for a specific job or all jobs.
        1. Identify job scope from task message
        2. Query agent_task_log WHERE source='scheduler' (+ optional job filter)
        3. Return: { runs: [{run_at, status, duration_ms, result_summary, error?}] }
        """

    async def trigger_job_now(self, task: dict) -> dict:
        """
        Manually fire a scheduled job immediately (outside its cron schedule).
        1. Identify job by name or ID
        2. celery_inspect → enqueue the job's Celery task immediately
        3. INSERT agent_task_log row with source='manual_trigger'
        4. Return: { task_id, job_name, queued_at, message: "Job triggered successfully" }
        """

    async def validate_cron_expression(self, task: dict) -> dict:
        """
        Validate a cron expression and explain it in plain language.
        1. Parse cron string from task
        2. Validate syntax (5-field standard cron)
        3. Calculate next 5 run times in HKT/SGT
        4. LLM → plain-language description ("Runs every Monday at 9:00 AM Singapore time")
        5. Return: { valid, cron_utc, cron_hkt_display, next_runs, description }
        """

    async def jobs_health_report(self, task: dict) -> dict:
        """
        Overall scheduled jobs health check.
        1. Query all active jobs from scheduled_jobs + beat_schedule
        2. For each: check last_run status, last_run duration, failure rate (last 30 days)
        3. Flag: jobs that have not run when expected, jobs with >2 consecutive failures
        4. Return: { total_jobs, healthy, warning, failed,
                     issues: [{job_name, issue, last_failure, recommendation}] }
        """

    async def _classify_scheduler_action(self, task: dict) -> str:
        """LLM-classify into: create_job | modify_job | pause_job | resume_job |
           delete_job | list_jobs | job_history | manual_trigger |
           validate_cron | health_check"""

    # Skills used:
    #   schedule_management  — CRUD on scheduled_jobs table, beat sync
    #   cron_validation      — expression parsing, next-run calculation, HKT conversion
    #   job_monitoring       — health checks, failure rate analysis, alert generation
    #   beat_sync            — live Celery Beat schedule modification without restart
```

---

### Special Agent Skills

Create the following new skill YAML + Python pairs in `server/skills/available/`:

**Skills for Research Agent:**
- `deep_research.yaml + .py` — multi-source research synthesis with citation tracking
- `source_verification.yaml + .py` — credibility scoring and cross-referencing sources

**Skills for Developer Agent:**
- `code_generation.yaml + .py` — LLM-based code writing with style enforcement
- `code_review.yaml + .py` — static analysis, bug detection, security scanning
- `code_execution.yaml + .py` — sandboxed subprocess execution with safety checks
- `api_integration.yaml + .py` — HTTP client, OpenAPI spec parsing, integration scaffolding
- `test_generation.yaml + .py` — pytest scaffold generation and sandbox test running

**Skills for Scheduler Agent:**
- `schedule_management.yaml + .py` — CRUD on scheduled_jobs + live Beat sync
- `cron_validation.yaml + .py` — expression validation, HKT↔UTC conversion, next-run calc
- `job_monitoring.yaml + .py` — health checks, failure detection, run history analysis
- `beat_sync.yaml + .py` — live Celery Beat schedule modification without service restart

Each skill follows the standard YAML + Python pattern from SKILLS.md.
YAML declares: name, version, description, primary_agent, dependencies, capabilities, tools.
Python implements: one method per tool, consistent with BaseTool pattern.


### Objective
Each agent must have its own isolated knowledge directory. No agent should be able to load knowledge files intended for another agent.

### Directory Structure
Ensure (create if missing):
```
server/knowledge/
├── management/     ← Management Agent RAG files
├── finance/        ← Finance Agent RAG files
├── sales/          ← Sales Agent RAG files
├── marketing/      ← Marketing Agent RAG files
├── support/        ← Support Agent RAG files
├── hr/             ← HR Agent RAG files
├── research/       ← Research Agent RAG files (research methodologies, trusted source list)
├── developer/      ← Developer Agent RAG files
│   └── schema/     ← DB schema docs for SQL generation
├── scheduler/      ← Scheduler Agent RAG files (cron reference, job patterns)
└── shared/         ← Cross-agent shared docs (Mezzofy product overview, brand guidelines)
```

### Update BaseAgent `_load_knowledge()`
If this method exists: update it to only load from `knowledge/{self.agent_record['memory_namespace']}/` and `knowledge/shared/`.  
If this method does not exist: create it with the above scoping.

```python
def _load_knowledge(self) -> list[str]:
    """
    Load RAG knowledge files for this agent only.
    Paths: knowledge/{memory_namespace}/ + knowledge/shared/
    Returns list of file paths to inject into LLM context.
    """
    namespace = self.agent_record["memory_namespace"]
    agent_dir = KNOWLEDGE_BASE_PATH / namespace
    shared_dir = KNOWLEDGE_BASE_PATH / "shared"
    files = []
    for d in [agent_dir, shared_dir]:
        if d.exists():
            files.extend(d.glob("*.md"))
            files.extend(d.glob("*.txt"))
            files.extend(d.glob("*.pdf"))
    return files
```

---

## PHASE 8 — Clean Separation Verification

After completing Phases 1–7, verify the following hard rules are true:

```
Separation verification checklist:

[ ] users table has NO agent-related columns
    (no skill_set, no agent_id FK, no memory_namespace)

[ ] agents table has NO user authentication columns
    (no password_hash, no refresh_token, no last_login_at)

[ ] JWT token payload references user_id (from users table) only —
    NEVER agent_id

[ ] All Celery tasks that represent agent work carry agent_id (from agents table)
    as a separate field — never using user_id as a proxy for agent identity

[ ] Router resolves: user_department → agent_id (via agent_registry)
    Never: user_id → agent class directly

[ ] Management Agent's orchestration tasks appear in agent_task_log
    with parent_task_id = NULL (top level) and child sub-tasks with
    parent_task_id = parent UUID

[ ] No agent can read knowledge files from another agent's namespace
    (test: assert finance agent knowledge loader returns zero files from /sales/)
```

---

## PHASE 9 — Tests

Create `server/tests/test_agent_separation.py`:

```python
# Tests to implement:

# 1. test_users_table_has_no_agent_columns
#    — Inspect DB schema; assert no agent-specific columns on users

# 2. test_agents_table_seeded
#    — SELECT COUNT(*) FROM agents = 9; all IDs present including
#      agent_research, agent_developer, agent_scheduler

# 3. test_agent_registry_loads
#    — AgentRegistry.load() runs without error; get("agent_sales") returns dict
#    — get("agent_research"), get("agent_developer"), get("agent_scheduler") all return dicts

# 4. test_find_agent_by_skill
#    — find_by_skill("pitch_deck_generation") returns agent_sales record
#    — find_by_skill("code_generation") returns agent_developer record
#    — find_by_skill("schedule_management") returns agent_scheduler record
#    — find_by_skill("deep_research") returns agent_research record

# 5. test_router_resolves_department_to_agent_id
#    — Mock task with department="finance"; router returns "agent_finance" not FinanceAgent class

# 6. test_management_agent_delegates
#    — Mock plan_and_orchestrate with a cross-dept task
#    — Assert delegate_task() is called with correct target agent_id
#    — Assert agent_task_log has parent_task_id set on sub-tasks

# 7. test_rag_namespace_isolation
#    — FinanceAgent._load_knowledge() returns ONLY files from knowledge/finance/ and knowledge/shared/
#    — Assert zero files from knowledge/sales/ are returned

# 8. test_agent_task_log_chain
#    — Insert a parent task (agent_management) + 2 child tasks (agent_finance, agent_sales)
#    — Query by parent_task_id; assert 2 children returned

# 9. test_delegation_result_redis_pubsub
#    — Mock Redis publish; assert process_delegated_agent_task publishes to correct channel
#    — Mock Redis subscribe in await_delegation(); assert it receives and returns result

# 10. test_user_cannot_impersonate_agent
#     — JWT with user_id="user_123" and role="admin" cannot invoke agent_registry.get_orchestrator()
#       directly via the chat API — must go through router

# 11. test_research_agent_triggers_correctly
#     — ResearchAgent.can_handle({"message": "research our top 3 competitors"}) → True
#     — FinanceAgent.can_handle({"message": "research our top 3 competitors"}) → False

# 12. test_developer_agent_safety_scan
#     — DeveloperAgent._safety_scan("DROP TABLE users") returns ["DROP TABLE"]
#     — DeveloperAgent._safety_scan("SELECT * FROM users") returns []
#     — execute_code() refuses to run code containing DANGEROUS_OPERATIONS

# 13. test_scheduler_agent_cron_validation
#     — validate_cron_expression("0 1 * * 1") returns valid=True, next_runs list of 5
#     — validate_cron_expression("99 99 * * *") returns valid=False

# 14. test_scheduler_agent_cannot_delete_builtin_jobs
#     — delete_scheduled_job({"message": "delete the weekly-kpi-report job"})
#       raises PermissionError or returns { deleted: false, reason: "Built-in jobs cannot be deleted" }

# 15. test_management_can_delegate_to_all_three_special_agents
#     — Mock plan_and_orchestrate with task requiring research + code + scheduling
#     — Assert delegate_task() called with agent_ids:
#       "agent_research", "agent_developer", "agent_scheduler"
#     — Assert all 3 appear in agent_task_log with correct parent_task_id

# 16. test_special_agent_rag_namespace_isolation
#     — ResearchAgent._load_knowledge() returns ONLY files from knowledge/research/ and shared/
#     — DeveloperAgent._load_knowledge() returns ONLY files from knowledge/developer/ and shared/
#     — SchedulerAgent._load_knowledge() returns ONLY files from knowledge/scheduler/ and shared/
```

Run: `pytest server/tests/test_agent_separation.py -v`

---

## PHASE 10 — Update Documentation

After all code is verified, update the following doc files (additive edits only, no deletion):

### `AGENTS.md` — Add section at top:
```
## Entity Model

Agents are SEPARATE from Users.

| Property         | User (users table)           | Agent (agents table)              |
|------------------|------------------------------|-----------------------------------|
| Identity         | Mezzofy staff member         | Autonomous AI team member         |
| Auth             | JWT (email + password + OTP) | None — invoked by system/user     |
| Persistence      | users table row              | agents table row                  |
| Skills           | N/A                          | YAML skill modules                |
| Memory           | Conversation history         | RAG knowledge namespace           |
| Task source      | Mobile app message           | Scheduler / webhook / delegation  |
| Can delegate?    | No                           | Yes (via delegate_task())         |
| Can be spawned?  | No                           | Yes (by Management Agent)         |

## Agent Roster (9 agents total)

### Department Agents (6) — each belongs to one business department
| Agent ID           | Persona           | Department  | LLM Model     |
|--------------------|-------------------|-------------|---------------|
| agent_management   | Max (Management)  | management  | claude-sonnet |
| agent_finance      | Fiona (Finance)   | finance     | claude-haiku  |
| agent_sales        | Sam (Sales)       | sales       | claude-sonnet |
| agent_marketing    | Maya (Marketing)  | marketing   | claude-haiku  |
| agent_support      | Suki (Support)    | support     | claude-haiku  |
| agent_hr           | Hana (HR)         | hr          | claude-haiku  |

### Special-Purpose Agents (3) — cross-departmental, serve all teams
| Agent ID           | Persona           | Function    | LLM Model     |
|--------------------|-------------------|-------------|---------------|
| agent_research     | Rex (Research)    | research    | claude-sonnet |
| agent_developer    | Dev (Developer)   | developer   | claude-sonnet |
| agent_scheduler    | Sched (Scheduler) | scheduler   | claude-haiku  |

**Special agents are cross-departmental.** Any department user can request their
services. The Management Agent delegates to all three. Other specialist agents
may also delegate (e.g. Sales Agent delegates web research to Rex; Finance Agent
delegates a new SQL query to Dev; any agent delegates follow-up scheduling to Sched).

The Management Agent is the only orchestrator. It is the only agent that:
- Calls plan_and_orchestrate() on complex tasks
- Spawns sub-tasks assigned to any of the other 8 specialist agents
- Synthesises cross-department results
- Is never spawned itself (can_be_spawned = FALSE)

Developer Agent safety rules (never violate):
- Never executes code containing DROP TABLE, DELETE FROM, TRUNCATE, rm -rf,
  shutdown, reboot, kill, systemctl restart/stop
- Never deploys to production or restarts any service
- All code execution occurs in an isolated sandbox subprocess
- Production changes require explicit admin approval — Dev proposes, human approves

Scheduler Agent safety rules:
- Built-in Celery Beat jobs (weekly-kpi-report, monthly-financial-summary, etc.)
  cannot be deleted or modified by Sched — only paused
- All cron expressions stored as UTC; displayed as HKT/SGT (UTC+8) in UI and responses
- beat_sync operates without service restart using Celery's live schedule update API
```

### `MEMORY.md` — Add to Core Tables section:
```
| `agents`          | AI agent identity, skills, tools, memory namespace | AgentRegistry    |
| `agent_task_log`  | Full task execution audit trail, delegation chains | BaseAgent, Tasks |
```

---

## EXECUTION ORDER

```
Phase 0  → Audit codebase — check for all 9 agent files, report findings
Phase 1  → New DB tables (agents + agent_task_log) + seed all 9 agents → alembic upgrade head
Phase 2  → Extend BaseAgent (additive only)
Phase 3  → Create AgentRegistry + register in main.py startup
Phase 4  → Upgrade ManagementAgent (add plan_and_orchestrate, keep existing code)
Phase 5  → Update Router to use AgentRegistry (targeted edits only)
Phase 6  → Add process_delegated_agent_task Celery task + update AGENT_ID_MAP with all 9
Phase 6B → Create research_agent.py, developer_agent.py, scheduler_agent.py
           + 11 new skill YAML+Python pairs for the 3 special agents
Phase 7  → RAG namespace directory structure (9 namespaces + shared) + update _load_knowledge()
Phase 8  → Run separation verification checklist
Phase 9  → Run pytest suite (16 tests), fix all failures
Phase 10 → Update AGENTS.md (full 9-agent roster) and MEMORY.md documentation
```

**Hard rules — never violate:**
- Do NOT restart FastAPI, Celery worker, or Celery Beat during this session.
- Do NOT modify or delete any existing working agent `execute()` methods.
- Do NOT add agent_id columns to the `users` table.
- Do NOT add user authentication columns to the `agents` table.
- All new code is additive: new files, new methods, new DB tables only.
- Alembic migration must use `ADD COLUMN IF NOT EXISTS` and `CREATE TABLE IF NOT EXISTS` guards.
