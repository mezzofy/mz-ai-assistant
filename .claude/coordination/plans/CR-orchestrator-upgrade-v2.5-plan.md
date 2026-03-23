# Change Request: Orchestrator Upgrade v2.5
## Full PLAN → DELEGATE → AGGREGATE Implementation
**Workflow:** change-request
**Date:** 2026-03-23
**Created by:** Lead Agent
**Source:** `docs/ORCHESTRATOR_AUDIT_AND_UPGRADE_PROMPT.md`
**Branch:** eric-design

---

## Phase 1 Audit Results (Completed)

### PLAN: PARTIAL

| Check | Status | Details |
|-------|--------|---------|
| LLM decomposes task before spawning | ✅ | `plan_and_orchestrate()` management_agent.py:403–443 |
| Dependencies between steps | ✅ | `depends_on_step` field, checked at line 483 |
| Parallel vs sequential logic | ✅ | null depends_on → parallel; non-null → sequential |
| Plan persisted to storage | ✅ | PostgreSQL `agent_task_log.task_plan` JSONB |
| Expected output type per step | ❌ | Not requested from LLM, not stored |
| Plan inspectable via API/portal | ❌ | No endpoint exists |
| Plan versioning / update | ❌ | Written once, never updated |

### DELEGATE: FAIL

| Check | Status | Details |
|-------|--------|---------|
| Celery async dispatch | ✅ | `celery_app.send_task()` in base_agent.py:480–488 |
| Sequential steps awaited | ✅ | `await_delegation()` at management_agent.py:495 |
| Parallel steps fire concurrently | ✅ | asyncio.gather() at management_agent.py:517 (fixed today) |
| plan_id in task payload | ❌ | MISSING |
| step_id in task payload | ❌ | MISSING |
| Structured context (prior step outputs) | ❌ | String-only: `"Context from prior step: {summary[:500]}"` |
| Step-specific instructions | ❌ | Only task description, no targeted instructions |
| Retry feedback | ❌ | MISSING — no retry mechanism exists |
| Uniform agent interface contract | ❌ | `_run_delegated_agent_task` has no schema; tasks get raw dict |

### AGGREGATE: FAIL

| Check | Status | Details |
|-------|--------|---------|
| Final synthesis via Claude API | ✅ | `llm_mod.get().chat()` at management_agent.py:558–562 |
| Per-step quality review | ❌ | MISSING — no validation after each step completes |
| Review can trigger retry | ❌ | MISSING — all outputs accepted regardless of quality |
| Shared context persisted | ❌ | In-memory `step_results` dict only; lost on crash |
| Context survives FastAPI restart | ❌ | NO — in-memory only |
| Artifact accumulation from sub-tasks | ❌ | Only text summaries collected, no file/artifact links |

### Pattern 1 Locations (fire-and-forget, no review, raw output to user)

All single-agent flows currently bypass the orchestrator entirely:
- `chat.py:send_message:371–425` (sync path)
- `chat.py:send_media:430–489`
- `chat.py:send_url:494–532`
- `chat.py:send_artifact:537–621`
- `chat.py:_handle_ws_text:883–924`
- `tasks.py:process_agent_task:148–173`

### Gap Report Summary

```
PLAN gaps:      No expected output type per step; no API to inspect plan; no update mechanism
DELEGATE gaps:  No plan_id/step_id in payload; context is string-only; no instructions/feedback; no retry
AGGREGATE gaps: No per-step review; no retry with feedback; context in-memory only (not persisted)
Pattern 1 in:   chat.py (5 endpoints + WS), tasks.py:process_agent_task
Pattern 2 missing for: all single-agent flows
Pattern 3 missing for: Celery chord not used (asyncio.gather used instead — semantically equivalent but not chord)
```

---

## Scope Decision (Lead Assessment)

The upgrade document requests Pattern 1 elimination for ALL flows — including single-agent direct requests. This would route every "what's the weather?" type message through Redis plan creation + Celery execution. **Lead recommends a phased scope:**

**Wave A (this CR — high value, lower risk):** Fix the orchestrator's own PLAN/DELEGATE/AGGREGATE gaps for multi-agent cross-department tasks. This is where the value is.

**Wave B (separate CR):** Pattern 1 elimination for single-agent flows — requires careful latency analysis before committing.

---

## Task Breakdown (Wave A)

| # | Task | Agent | File(s) | Sessions | Status |
|---|------|-------|---------|:--------:|--------|
| 1 | PlanManager — Redis DB3 persistence | Backend | `server/app/orchestrator/plan_manager.py` (NEW) | 1 | NOT STARTED |
| 2 | Uniform agent interface (input/output contract) | Backend | `server/app/tasks/tasks.py` | 1 | NOT STARTED |
| 3 | orchestrator_tasks.py — execute_plan, parallel chord, sequential dispatch | Backend | `server/app/tasks/orchestrator_tasks.py` (NEW) | 1 | NOT STARTED |
| 4 | Per-step review + retry (Claude API) | Backend | `server/app/tasks/orchestrator_tasks.py` | 1 | NOT STARTED |
| 5 | Final synthesis + WebSocket progress notifications | Backend | `server/app/tasks/orchestrator_tasks.py` | 0.5 | NOT STARTED |
| 6 | Replace plan_and_orchestrate() to use PlanManager + orchestrator_tasks | Backend | `server/app/agents/management_agent.py` | 0.5 | NOT STARTED |
| 7 | Backend API — GET /api/plans, /api/plans/{id}, /api/plans/{id}/steps/{step_id} | Backend | `server/app/api/admin_portal.py` | 0.5 | NOT STARTED |
| 8 | Portal — "Agent Plans" tab | Frontend | `portal/src/pages/BackgroundTasksPage.tsx` | 2 | NOT STARTED |

**Tasks 1–7 must run sequentially (each depends on the previous). Task 8 (portal) can start after Task 7.**

**Estimated sessions:** Backend 5 sessions · Frontend 2 sessions

---

## Detailed Implementation Specs

### Task 1 — PlanManager (`server/app/orchestrator/plan_manager.py`)

Create `server/app/orchestrator/` directory with `__init__.py` and `plan_manager.py`.

**Data structures:**
```python
from dataclasses import dataclass, field
from typing import Optional
import uuid
from datetime import datetime

@dataclass
class PlanStep:
    step_id: str                    # e.g. "step_1"
    step_number: int
    agent_id: str                   # e.g. "agent_sales"
    description: str
    depends_on: list[str]           # step_ids that must complete first
    can_run_parallel: bool          # True if no dependencies
    status: str                     # PENDING|STARTED|COMPLETED|FAILED|RETRYING
    celery_task_id: Optional[str] = None
    instructions: str = ""
    context_keys: list[str] = field(default_factory=list)
    expected_output_type: str = "general"
    output: Optional[dict] = None
    review: Optional[dict] = None
    retry_count: int = 0
    max_retries: int = 2
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None

@dataclass
class ExecutionPlan:
    plan_id: str
    goal: str
    user_id: str
    session_id: str
    steps: list[PlanStep]
    shared_context: dict = field(default_factory=dict)
    execution_mode: str = "sequential"   # sequential|parallel|mixed
    status: str = "PENDING"              # PENDING|IN_PROGRESS|COMPLETED|FAILED
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    completed_at: Optional[str] = None
    final_output: Optional[str] = None
    total_retries: int = 0
    original_task: dict = field(default_factory=dict)  # preserves original task context
```

**PlanManager class:**
```python
class PlanManager:
    REDIS_DB = 3
    KEY_PREFIX = "mz:plan:"
    INDEX_KEY = "mz:plan:index"

    def __init__(self):
        import redis
        from app.core.config import get_config
        config = get_config()
        redis_url = config.get("redis", {}).get("url", "redis://localhost:6379")
        self._redis = redis.from_url(redis_url, db=self.REDIS_DB, decode_responses=True)

    async def create_plan(self, goal: str, user_id: str, session_id: str,
                          task: dict, available_agents: list[dict]) -> ExecutionPlan:
        # Claude API call to decompose goal into steps
        # Returns ExecutionPlan with steps populated
        ...

    def save_plan(self, plan: ExecutionPlan) -> None:
        # Serialise to JSON, write to Redis DB3 at mz:plan:{plan_id}
        # Update index hash
        ...

    def load_plan(self, plan_id: str) -> ExecutionPlan:
        # Read from Redis DB3, deserialise
        ...

    def update_step(self, plan_id: str, step_id: str, status: str,
                    output: dict = None, review: dict = None,
                    celery_task_id: str = None, error: str = None) -> None:
        # Load plan, update step, append to shared_context if output provided, save
        ...

    def get_next_steps(self, plan: ExecutionPlan) -> list[PlanStep]:
        # Steps whose depends_on are all COMPLETED and own status is PENDING
        ...

    def get_parallel_group(self, plan: ExecutionPlan) -> list[PlanStep]:
        # Subset of get_next_steps() where can_run_parallel=True
        ...

    def is_plan_complete(self, plan: ExecutionPlan) -> bool:
        # All steps COMPLETED, or any step FAILED with retry_count >= max_retries
        ...

    def list_plans(self, user_id: str = None, limit: int = 20) -> list[dict]:
        # Read from index, filter by user_id if provided, return summaries
        ...
```

**Planning LLM prompt** (inside `create_plan()`):
```
You are the Mezzofy AI Orchestrator planning an execution.
Given the user's goal, produce a structured execution plan in JSON.

Available agents:
{agent_list}

Rules:
- Break the goal into the minimum number of steps needed
- Assign each step to the most appropriate agent (use agent_id, e.g. "agent_sales")
- Mark depends_on for any step that needs a prior step's output (use step_id strings)
- Mark can_run_parallel: true only when step has NO dependencies
- Write specific instructions for each step — not generic
- Identify the expected output type for each step

Return ONLY valid JSON, no prose:
{
  "goal_summary": "...",
  "execution_mode": "sequential|parallel|mixed",
  "steps": [
    {
      "step_id": "step_1",
      "step_number": 1,
      "agent_id": "agent_sales",
      "description": "...",
      "instructions": "...",
      "depends_on": [],
      "can_run_parallel": false,
      "context_keys": [],
      "expected_output_type": "sales_data"
    }
  ]
}

Validate: depends_on must reference only step_ids defined in this plan.
```

Validate JSON before saving. If depends_on references non-existent step_ids → retry Claude call once with error appended.

**module-level singleton:**
```python
plan_manager = PlanManager()
```

---

### Task 2 — Uniform Agent Interface Contract (`tasks.py`)

Update `_run_delegated_agent_task()` to accept and propagate the new contract fields.

The function currently accepts: `task_data, agent_id, parent_task_id, log_id`

Add extraction of structured fields from `task_data`:
```python
plan_id = task_data.get("_plan_id", "")
step_id = task_data.get("_step_id", "")
context = task_data.get("_context", {})     # prior step outputs
instructions = task_data.get("_instructions", "")
feedback = task_data.get("_feedback", "")   # retry feedback
```

On completion, the result dict should be normalised to the uniform output contract:
```python
def _normalise_agent_output(result: dict, quality_estimate: float = 0.8) -> dict:
    """Wrap agent result in uniform output contract."""
    return {
        "status": "completed" if result.get("success") else "failed",
        "result": result,
        "summary": result.get("content", "")[:500],
        "deliverable": _extract_deliverable(result.get("artifacts", [])),
        "quality_score": quality_estimate,
        "issues": [] if result.get("success") else [result.get("content", "error")],
    }
```

After normalisation, if `plan_id` and `step_id` are set, call:
```python
from app.tasks.orchestrator_tasks import handle_step_completion
handle_step_completion.delay(plan_id, step_id, normalised_output)
```

---

### Task 3 — orchestrator_tasks.py (NEW)

Create `server/app/tasks/orchestrator_tasks.py` with:

**execute_plan_task** — main loop:
```python
@celery_app.task(bind=True, name="app.tasks.orchestrator_tasks.execute_plan_task", max_retries=0)
def execute_plan_task(self, plan_id: str):
    # Loop until plan complete:
    #   load plan → get_next_steps → dispatch parallel (chord) or sequential
    # When complete: call orchestrator_synthesise.delay(plan_id)
```

**dispatch_sequential_step** — Pattern 2:
```python
def dispatch_sequential_step(plan_id: str, step: PlanStep):
    plan = plan_manager.load_plan(plan_id)
    context = {k: plan.shared_context[k] for k in step.context_keys if k in plan.shared_context}
    task = route_to_celery_task(step.agent_id).apply_async(kwargs={
        "plan_id": plan_id, "step_id": step.step_id,
        "context": context, "instructions": step.instructions, "feedback": None,
        **plan.original_task   # pass user/session/dept context
    })
    plan_manager.update_step(plan_id, step.step_id, status="STARTED", celery_task_id=task.id)
    notify_step_start(plan_id, step)
```

**dispatch_parallel_steps** — Pattern 3 (Celery group + chord):
```python
from celery import group, chord

def dispatch_parallel_steps(plan_id: str, steps: list[PlanStep]):
    plan = plan_manager.load_plan(plan_id)
    job_group = group([
        route_to_celery_task(step.agent_id).s(
            plan_id=plan_id, step_id=step.step_id,
            context={k: plan.shared_context[k] for k in step.context_keys if k in plan.shared_context},
            instructions=step.instructions, feedback=None,
            **{k: v for k, v in plan.original_task.items() if k not in ("_config",)}
        )
        for step in steps
    ])
    chord(job_group)(parallel_join_task.s(plan_id=plan_id, step_ids=[s.step_id for s in steps]))
    for step in steps:
        plan_manager.update_step(plan_id, step.step_id, status="STARTED")
        notify_step_start(plan_id, step)
```

**parallel_join_task** — chord callback:
```python
@celery_app.task(name="app.tasks.orchestrator_tasks.parallel_join_task")
def parallel_join_task(results: list, plan_id: str, step_ids: list[str]):
    for step_id, result in zip(step_ids, results):
        handle_step_completion.delay(plan_id, step_id, result)
```

**route_to_celery_task** — agent ID → Celery task mapping:
```python
def route_to_celery_task(agent_id: str):
    AGENT_TASK_MAP = {
        "agent_management": process_delegated_agent_task,
        "agent_finance":    process_delegated_agent_task,
        "agent_sales":      process_delegated_agent_task,
        "agent_marketing":  process_delegated_agent_task,
        "agent_support":    process_delegated_agent_task,
        "agent_hr":         process_delegated_agent_task,
        "agent_legal":      process_delegated_agent_task,
        "agent_research":   process_delegated_agent_task,
        "agent_developer":  process_delegated_agent_task,
        "agent_scheduler":  process_delegated_agent_task,
    }
    # All agents use the same Celery task function — agent_id in payload determines which class runs
    task = AGENT_TASK_MAP.get(agent_id)
    if not task:
        raise ValueError(f"Unknown agent_id: {agent_id}")
    return task
```

Note: All agents already share `process_delegated_agent_task` — we route via `agent_id` kwarg.

---

### Task 4 — Per-Step Review + Retry

Add to `orchestrator_tasks.py`:

**handle_step_completion:**
```python
@celery_app.task(name="app.tasks.orchestrator_tasks.handle_step_completion")
def handle_step_completion(plan_id: str, step_id: str, result: dict):
    plan_manager.update_step(plan_id, step_id, status="COMPLETED", output=result)
    review = _orchestrator_review(plan_id, step_id)
    if review.get("should_retry"):
        _retry_step(plan_id, step_id, review.get("gaps", []))
    else:
        notify_step_complete(plan_id, step_id, result.get("summary", ""))
        plan = plan_manager.load_plan(plan_id)
        if plan_manager.is_plan_complete(plan):
            orchestrator_synthesise.delay(plan_id)
        else:
            execute_plan_task.delay(plan_id)  # continue with remaining steps
```

**_orchestrator_review** (Claude API call):
```python
def _orchestrator_review(plan_id: str, step_id: str) -> dict:
    # Load plan + step
    # Build review prompt with: goal, step description, instructions, agent output, quality_score, retry_count
    # Call Claude API (sync via asyncio.run())
    # Parse JSON response: addresses_goal, quality_sufficient, completeness_score, gaps, should_retry, proceed
    # Save review to step via plan_manager.update_step(..., review=review_result)
    # Return review_result
```

**_retry_step:**
```python
def _retry_step(plan_id: str, step_id: str, gaps: list[str]):
    plan = plan_manager.load_plan(plan_id)
    step = next(s for s in plan.steps if s.step_id == step_id)
    if step.retry_count >= step.max_retries:
        # Max retries — mark completed with warning
        plan_manager.update_step(plan_id, step_id, status="COMPLETED")
        notify_step_complete(plan_id, step_id, f"Completed with limitations: {', '.join(gaps)}")
        return
    step.retry_count += 1
    step.status = "RETRYING"
    plan_manager.save_plan(plan)
    feedback = f"Previous attempt had these issues: {'; '.join(gaps)}. Address all of them."
    context = {k: plan.shared_context[k] for k in step.context_keys if k in plan.shared_context}
    notify_step_retry(plan_id, step_id, gaps)
    route_to_celery_task(step.agent_id).apply_async(kwargs={
        "plan_id": plan_id, "step_id": step_id,
        "context": context, "instructions": step.instructions, "feedback": feedback,
        **{k: v for k, v in plan.original_task.items() if k not in ("_config",)}
    })
```

---

### Task 5 — Final Synthesis + WebSocket Notifications

**orchestrator_synthesise:**
```python
@celery_app.task(name="app.tasks.orchestrator_tasks.orchestrator_synthesise")
def orchestrator_synthesise(plan_id: str):
    plan = plan_manager.load_plan(plan_id)
    step_summaries = [...]   # collect all step summaries
    deliverables = [...]     # collect all artifacts

    synthesis_prompt = f"""
    You are the Mezzofy AI Assistant responding to a user.
    The user asked: {plan.goal}
    Here is what each agent completed: {json.dumps(step_summaries, indent=2)}
    Deliverables: {json.dumps(deliverables, indent=2)}
    Write a concise, professional response (max 150 words):
    1. Confirm completion
    2. Summarise key findings in 2-4 sentences
    3. Mention each deliverable with download link
    4. Flag any limitations
    5. Offer a natural next step
    Rules: No raw JSON. No "step_1" references. Brand voice: direct, results-focused.
    """
    final_response = call_claude_api_sync(synthesis_prompt)

    plan.final_output = final_response
    plan.status = "COMPLETED"
    plan.completed_at = datetime.utcnow().isoformat()
    plan_manager.save_plan(plan)

    _send_ws_to_user(plan.user_id, plan.session_id, final_response, deliverables)
    _append_to_conversation(plan.session_id, final_response, plan_id, deliverables)
```

**WebSocket notifications** (use existing WSConnectionManager):
```python
def notify_step_start(plan_id: str, step: PlanStep):
    # send WS message: "Starting {step.description} with {step.agent_id}..."
    # Use existing: from app.api.chat import ws_manager; ws_manager.send_to_user(user_id, msg)

def notify_step_complete(plan_id: str, step_id: str, summary: str):
    # send WS message: "✓ {step.description} — {summary}"

def notify_step_retry(plan_id: str, step_id: str, gaps: list[str]):
    # send WS message: "Improving {step.description} — {first gap}"
```

Look up existing WS send pattern from `app.api.chat` / `app.websocket` before implementing — do NOT create a new WebSocket layer.

---

### Task 6 — Update plan_and_orchestrate() in management_agent.py

Replace the current ~200-line `plan_and_orchestrate()` method body with:
```python
async def plan_and_orchestrate(self, task: dict) -> dict:
    from app.orchestrator.plan_manager import plan_manager
    from app.agents.agent_registry import agent_registry as _registry

    active_agents = _registry.all_active()
    plan = await plan_manager.create_plan(
        goal=task.get("message", ""),
        user_id=task.get("user_id", ""),
        session_id=task.get("session_id", ""),
        task=task,
        available_agents=active_agents,
    )

    # Fire-and-forget: Celery takes over the full PLAN→DELEGATE→AGGREGATE cycle
    from app.tasks.orchestrator_tasks import execute_plan_task
    execute_plan_task.delay(plan.plan_id)

    # Return immediately — user will receive WS updates as steps complete
    return self._ok(
        content=f"I'm working on that. I'll send you updates as each step completes. Plan ID: {plan.plan_id}",
        tools_called=["plan_and_orchestrate"],
    )
```

This makes plan_and_orchestrate() a thin dispatcher. All orchestration logic moves to orchestrator_tasks.py.

---

### Task 7 — API Endpoints for Plans

Add to `server/app/api/admin_portal.py` (or new `server/app/api/plans.py`):

```python
GET  /api/plans                        → list_plans(user_id=, status=, limit=20, offset=0)
GET  /api/plans/{plan_id}              → get_plan(plan_id) — full detail
GET  /api/plans/{plan_id}/steps/{step_id} → get_plan_step(plan_id, step_id)
```

Note: Declare `/api/plans/stats` BEFORE `/api/plans/{plan_id}` to avoid FastAPI treating "stats" as a plan_id.

All endpoints read from Redis DB3 via `plan_manager.load_plan()` and `plan_manager.list_plans()`.

---

### Task 8 — Portal "Agent Plans" Tab (Frontend)

Add Tab 3 "Agent Plans" to `portal/src/pages/BackgroundTasksPage.tsx`.

**Plan list view:**
```
Goal | Steps | Status | Agent(s) | Created | Duration | Actions
```

Each row shows:
- Goal text (truncated to 60 chars)
- Step count + completion fraction (e.g., "3/5")
- Status badge: PENDING (grey) | IN_PROGRESS (pulsing orange #f97316) | COMPLETED (black ✓) | FAILED (red ✗)
- Progress bar: `████░░ 3/5 steps done`
- [View Detail] button

**Plan detail view** (expand in-place or slide-over):
- Header: Plan ID (copyable), goal, status, duration
- Step timeline: ✓ completed | → in progress | ○ pending (with "Waiting on: step_X")
- Per step: agent name, description, quality score, [View Output] + [View Review] buttons
- Retry history if step was retried
- Final synthesised response at bottom when COMPLETED
- Deliverable download links

**New API calls in `portal/src/api/portal.ts`:**
```typescript
getPlans(userId?: string, status?: string): Promise<Plan[]>
getPlanDetail(planId: string): Promise<PlanDetail>
getPlanStep(planId: string, stepId: string): Promise<PlanStep>
```

**New types in `portal/src/types/index.ts`:**
```typescript
interface Plan {
  plan_id: string
  goal: string
  status: 'PENDING' | 'IN_PROGRESS' | 'COMPLETED' | 'FAILED'
  steps_total: number
  steps_completed: number
  agents: string[]
  created_at: string
  completed_at?: string
  duration_ms?: number
}

interface PlanStep {
  step_id: string
  step_number: number
  agent_id: string
  description: string
  status: string
  quality_score?: number
  summary?: string
  issues?: string[]
  review?: object
  retry_count: number
  started_at?: string
  completed_at?: string
}
```

Brand colours apply: primary orange #f97316, black #000000, white #ffffff.

---

## Deployment Checklist

```bash
# After all Backend sessions complete:
git pull
# No migration needed — Redis DB3 used for plans (self-initialising)
sudo systemctl restart mezzofy-api.service
sudo systemctl restart mezzofy-celery.service

# Verify Redis DB3 is writable:
redis-cli -n 3 ping   # should return PONG

# After Frontend session:
cd portal && npm install && npm run build
sudo mkdir -p /var/www/mission-control
sudo cp -r dist/* /var/www/mission-control/
```

---

## Quality Gate Checklist

### Backend Gates

- [ ] `plan_manager.py` — PlanStep + ExecutionPlan dataclasses correct; PlanManager Redis DB3 ops work; create_plan() calls Claude and validates JSON
- [ ] Uniform interface — `_run_delegated_agent_task()` extracts plan_id/step_id/context/instructions/feedback; output normalised
- [ ] `orchestrator_tasks.py` — execute_plan_task loops correctly; parallel chord fires simultaneously; sequential awaits completion first
- [ ] Per-step review — Claude API called after EVERY step; review saved to plan step; retry triggered when should_retry=true
- [ ] Retry — feedback passed to re-dispatched agent; retry_count incremented; max_retries respected
- [ ] Synthesis — Claude API called with all step summaries; final output not raw JSON; WS notification sent
- [ ] `plan_and_orchestrate()` reduced to thin dispatcher; full logic in orchestrator_tasks.py
- [ ] API endpoints — /api/plans and /api/plans/{id} return correct data from Redis DB3
- [ ] Redis DB3 separation maintained (broker=0, backend=1, beat=2, plans=3)

### Frontend Gates

- [ ] "Agent Plans" tab appears in BackgroundTasksPage
- [ ] Plan list shows goal, status badge, step fraction, progress bar
- [ ] Pulsing orange animation for IN_PROGRESS
- [ ] Step timeline shows ✓/→/○ states with dependency labels
- [ ] [View Output] shows agent summary, quality score, issues
- [ ] [View Review] shows Orchestrator review: completeness_score, gaps, should_retry
- [ ] Retry history visible
- [ ] Final synthesised response at bottom of completed plans
- [ ] Deliverable download links functional
- [ ] Memory upload/delete not regressed (no changes to Agents tab)

---

## Delegation Instructions

**Backend Agent — Session 1:** Tasks 1 + 2 (PlanManager + uniform interface)
**Backend Agent — Session 2:** Task 3 (orchestrator_tasks.py — execute_plan_task, dispatch functions, chord)
**Backend Agent — Session 3:** Task 4 (handle_step_completion, orchestrator_review, retry_step)
**Backend Agent — Session 4:** Task 5 + 6 (synthesis, WS notifications, update plan_and_orchestrate)
**Backend Agent — Session 5:** Task 7 (API endpoints)
**Frontend Agent — Session 1:** Task 8 Part A (types, API functions, plan list view)
**Frontend Agent — Session 2:** Task 8 Part B (plan detail view, step timeline, output/review expand)

Backend Sessions 1–5 must be sequential. Frontend can start after Task 7 is complete.

---

## Risk Notes

1. **Celery chord requires result backend** — Celery chord needs the result backend (Redis DB1) to be configured. Confirm `CELERY_RESULT_BACKEND` is set in config. Without it, chord callback never fires.
2. **asyncio.run() in Celery** — All async code in orchestrator_tasks.py Celery tasks must be wrapped in `asyncio.run()`. Existing pattern: `from app.core.database import engine; engine.sync_engine.dispose()` before each `asyncio.run()` call.
3. **WS connection scoping** — WSConnectionManager is in-process singleton. In multi-worker EC2 deployment, WS send may not reach the right worker. Check existing WS send mechanism first — may need Redis pub/sub (see memory.md note about multi-worker WS).
4. **Plan_and_orchestrate() is now fire-and-forget** — The method returns immediately before results are ready. The user-facing message ("I'm working on that...") must be clearly worded. Portal Background Tasks shows progress.
