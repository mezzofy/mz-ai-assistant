"""
PlanManager — Redis DB3 persistence for execution plans.

Stores ExecutionPlan objects (dataclasses) in Redis DB3 under:
  mz:plan:{plan_id}   — full plan JSON
  mz:plan:index       — hash of {plan_id: user_id} for listing

The sync Redis client is used deliberately so PlanManager methods work from
both async (management_agent) and sync (Celery tasks) contexts without wrapping.
"""

import json
import logging
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional

logger = logging.getLogger("mezzofy.orchestrator.plan_manager")


# ── Data structures ────────────────────────────────────────────────────────────

@dataclass
class PlanStep:
    step_id: str                     # e.g. "step_1"
    step_number: int
    agent_id: str                    # e.g. "agent_sales"
    description: str
    depends_on: list                 # step_ids that must complete first
    can_run_parallel: bool           # True if no dependencies
    status: str                      # PENDING|STARTED|COMPLETED|FAILED|RETRYING
    celery_task_id: Optional[str] = None
    instructions: str = ""
    context_keys: list = field(default_factory=list)
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
    steps: list                      # list[PlanStep] — stored as list for JSON serialisation
    shared_context: dict = field(default_factory=dict)
    execution_mode: str = "sequential"   # sequential|parallel|mixed
    status: str = "PENDING"              # PENDING|IN_PROGRESS|COMPLETED|FAILED
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    completed_at: Optional[str] = None
    final_output: Optional[str] = None
    total_retries: int = 0
    original_task: dict = field(default_factory=dict)  # preserves original task context


# ── PlanManager ────────────────────────────────────────────────────────────────

class PlanManager:
    """
    Manages execution plans persisted in Redis DB3.

    All public methods are synchronous (use plain redis, not aioredis) so they
    can be called from both Celery task bodies and async FastAPI handlers without
    wrapping. Async callers use create_plan() which internally runs the Claude
    API call via asyncio.
    """

    REDIS_DB = 3
    KEY_PREFIX = "mz:plan:"
    INDEX_KEY = "mz:plan:index"

    def __init__(self):
        import redis as _redis
        from app.core.config import get_config
        config = get_config()
        redis_url = config.get("redis", {}).get("url", "redis://localhost:6379")
        self._redis = _redis.from_url(redis_url, db=self.REDIS_DB, decode_responses=True)

    # ── Plan creation (async — calls Claude API) ───────────────────────────────

    async def create_plan(
        self,
        goal: str,
        user_id: str,
        session_id: str,
        task: dict,
        available_agents: list,
    ) -> "ExecutionPlan":
        """
        Call Claude API to decompose the goal into steps, validate JSON, and
        persist the resulting ExecutionPlan to Redis DB3.

        Returns the saved ExecutionPlan.
        """
        import anthropic

        # Build agent list for the prompt
        agent_list = json.dumps([
            {
                "id": a.get("id", ""),
                "department": a.get("department", ""),
                "skills": a.get("skills", []),
            }
            for a in available_agents
        ], indent=2)

        planning_prompt = (
            "You are the Mezzofy AI Orchestrator planning an execution.\n"
            "Given the user's goal, produce a structured execution plan in JSON.\n\n"
            f"Available agents:\n{agent_list}\n\n"
            "Rules:\n"
            "- Break the goal into the minimum number of steps needed\n"
            "- Assign each step to the most appropriate agent (use agent_id, e.g. \"agent_sales\")\n"
            "- Mark depends_on for any step that needs a prior step's output (use step_id strings)\n"
            "- Mark can_run_parallel: true only when step has NO dependencies\n"
            "- Write specific instructions for each step — not generic\n"
            "- Identify the expected output type for each step\n\n"
            "Return ONLY valid JSON, no prose:\n"
            "{\n"
            "  \"goal_summary\": \"...\",\n"
            "  \"execution_mode\": \"sequential|parallel|mixed\",\n"
            "  \"steps\": [\n"
            "    {\n"
            "      \"step_id\": \"step_1\",\n"
            "      \"step_number\": 1,\n"
            "      \"agent_id\": \"agent_sales\",\n"
            "      \"description\": \"...\",\n"
            "      \"instructions\": \"...\",\n"
            "      \"depends_on\": [],\n"
            "      \"can_run_parallel\": false,\n"
            "      \"context_keys\": [],\n"
            "      \"expected_output_type\": \"sales_data\"\n"
            "    }\n"
            "  ]\n"
            "}\n\n"
            "Validate: depends_on must reference only step_ids defined in this plan.\n\n"
            f"Goal: {goal}"
        )

        client = anthropic.AsyncAnthropic()
        plan_data = None
        last_error = ""

        for attempt in range(2):
            prompt_with_error = planning_prompt
            if attempt == 1 and last_error:
                prompt_with_error = planning_prompt + f"\n\nPrevious attempt error: {last_error}\nFix the depends_on references."

            try:
                response = await client.messages.create(
                    model="claude-sonnet-4-5",
                    max_tokens=2000,
                    messages=[{"role": "user", "content": prompt_with_error}],
                )
                raw = response.content[0].text if response.content else "{}"

                # Extract JSON object from response
                start = raw.find("{")
                end = raw.rfind("}") + 1
                if start >= 0 and end > start:
                    plan_data = json.loads(raw[start:end])
                else:
                    raise ValueError("No JSON object found in LLM response")

                # Validate depends_on references
                step_ids = {s["step_id"] for s in plan_data.get("steps", [])}
                for s in plan_data.get("steps", []):
                    for dep in s.get("depends_on", []):
                        if dep not in step_ids:
                            last_error = f"Step {s['step_id']} depends_on '{dep}' which does not exist in steps."
                            plan_data = None
                            break
                    if plan_data is None:
                        break

                if plan_data is not None:
                    break  # Valid plan — stop retrying

            except Exception as e:
                logger.warning(f"PlanManager.create_plan attempt {attempt+1} failed: {e}")
                last_error = str(e)
                plan_data = None

        # Build PlanStep objects
        if not plan_data or not plan_data.get("steps"):
            logger.warning("PlanManager.create_plan: LLM returned no valid steps — creating single-step fallback")
            plan_data = {
                "goal_summary": goal[:200],
                "execution_mode": "sequential",
                "steps": [
                    {
                        "step_id": "step_1",
                        "step_number": 1,
                        "agent_id": "agent_management",
                        "description": goal[:200],
                        "instructions": goal,
                        "depends_on": [],
                        "can_run_parallel": False,
                        "context_keys": [],
                        "expected_output_type": "general",
                    }
                ],
            }

        steps = []
        for s in plan_data["steps"]:
            steps.append(PlanStep(
                step_id=s.get("step_id", f"step_{s.get('step_number', len(steps)+1)}"),
                step_number=int(s.get("step_number", len(steps) + 1)),
                agent_id=s.get("agent_id", "agent_management"),
                description=s.get("description", ""),
                depends_on=s.get("depends_on", []),
                can_run_parallel=bool(s.get("can_run_parallel", not s.get("depends_on"))),
                status="PENDING",
                instructions=s.get("instructions", ""),
                context_keys=s.get("context_keys", []),
                expected_output_type=s.get("expected_output_type", "general"),
            ))

        # Strip non-serialisable keys from original task before storing
        original_task_clean = {
            k: v for k, v in task.items()
            if k not in ("_config", "_progress_callback", "db", "conversation_history")
            and isinstance(v, (str, int, float, bool, list, dict, type(None)))
        }

        plan = ExecutionPlan(
            plan_id=str(uuid.uuid4()),
            goal=goal,
            user_id=user_id,
            session_id=session_id,
            steps=steps,
            execution_mode=plan_data.get("execution_mode", "sequential"),
            original_task=original_task_clean,
        )

        self.save_plan(plan)
        logger.info(f"PlanManager: created plan {plan.plan_id} with {len(steps)} steps")
        return plan

    # ── Redis persistence ──────────────────────────────────────────────────────

    def save_plan(self, plan: "ExecutionPlan") -> None:
        """Serialise ExecutionPlan + PlanSteps to JSON and write to Redis DB3."""
        try:
            # Convert steps (PlanStep dataclasses) to dicts for serialisation
            plan_dict = asdict(plan)
            key = f"{self.KEY_PREFIX}{plan.plan_id}"
            self._redis.set(key, json.dumps(plan_dict))
            # Update index: plan_id → user_id
            self._redis.hset(self.INDEX_KEY, plan.plan_id, plan.user_id)
        except Exception as e:
            logger.error(f"PlanManager.save_plan failed for plan_id={plan.plan_id}: {e}")
            raise

    def load_plan(self, plan_id: str) -> "ExecutionPlan":
        """Read plan from Redis DB3 and deserialise to ExecutionPlan dataclass."""
        key = f"{self.KEY_PREFIX}{plan_id}"
        raw = self._redis.get(key)
        if not raw:
            raise KeyError(f"Plan not found in Redis: {plan_id}")
        data = json.loads(raw)

        # Reconstruct PlanStep objects from dicts
        steps = []
        for s in data.get("steps", []):
            steps.append(PlanStep(
                step_id=s["step_id"],
                step_number=s["step_number"],
                agent_id=s["agent_id"],
                description=s["description"],
                depends_on=s.get("depends_on", []),
                can_run_parallel=s.get("can_run_parallel", False),
                status=s.get("status", "PENDING"),
                celery_task_id=s.get("celery_task_id"),
                instructions=s.get("instructions", ""),
                context_keys=s.get("context_keys", []),
                expected_output_type=s.get("expected_output_type", "general"),
                output=s.get("output"),
                review=s.get("review"),
                retry_count=s.get("retry_count", 0),
                max_retries=s.get("max_retries", 2),
                started_at=s.get("started_at"),
                completed_at=s.get("completed_at"),
                error=s.get("error"),
            ))

        data["steps"] = steps
        plan = ExecutionPlan(**data)
        return plan

    def update_step(
        self,
        plan_id: str,
        step_id: str,
        status: str,
        output: dict = None,
        review: dict = None,
        celery_task_id: str = None,
        error: str = None,
    ) -> None:
        """
        Load plan, update the named step's fields, optionally append output
        summary to shared_context, and save plan back to Redis.
        """
        plan = self.load_plan(plan_id)
        step = next((s for s in plan.steps if s.step_id == step_id), None)
        if step is None:
            logger.warning(f"update_step: step_id={step_id!r} not found in plan {plan_id}")
            return

        step.status = status
        if output is not None:
            step.output = output
            # Append summary to shared_context so subsequent steps can reference it
            summary = output.get("summary", output.get("result", {}).get("content", ""))
            if isinstance(summary, str):
                plan.shared_context[f"{step_id}_output"] = summary[:1000]
        if review is not None:
            step.review = review
        if celery_task_id is not None:
            step.celery_task_id = celery_task_id
        if error is not None:
            step.error = error
        if status == "STARTED" and not step.started_at:
            step.started_at = datetime.utcnow().isoformat()
        if status in ("COMPLETED", "FAILED") and not step.completed_at:
            step.completed_at = datetime.utcnow().isoformat()

        # Update plan-level status
        if plan.status == "PENDING":
            plan.status = "IN_PROGRESS"

        self.save_plan(plan)

    # ── Step dispatch helpers ──────────────────────────────────────────────────

    def get_next_steps(self, plan: "ExecutionPlan") -> list:
        """
        Return steps whose depends_on are all COMPLETED and whose own status
        is PENDING.
        """
        completed_ids = {s.step_id for s in plan.steps if s.status == "COMPLETED"}
        return [
            s for s in plan.steps
            if s.status == "PENDING"
            and all(dep in completed_ids for dep in s.depends_on)
        ]

    def get_parallel_group(self, plan: "ExecutionPlan") -> list:
        """
        Return the subset of get_next_steps() where can_run_parallel=True.
        Falls back to the full next_steps list if all are parallel-eligible.
        """
        next_steps = self.get_next_steps(plan)
        parallel = [s for s in next_steps if s.can_run_parallel]
        return parallel

    def is_plan_complete(self, plan: "ExecutionPlan") -> bool:
        """
        Return True if all steps are COMPLETED, or if any step is FAILED
        with retry_count >= max_retries (treat as terminal).
        """
        for step in plan.steps:
            if step.status == "FAILED" and step.retry_count >= step.max_retries:
                return True  # Terminal failure
            if step.status not in ("COMPLETED",):
                return False
        return True

    # ── Listing ────────────────────────────────────────────────────────────────

    def list_plans(self, user_id: str = None, limit: int = 20) -> list:
        """
        Read the index hash and return plan summaries.
        Optionally filter by user_id.
        """
        try:
            index = self._redis.hgetall(self.INDEX_KEY)
        except Exception as e:
            logger.warning(f"PlanManager.list_plans: Redis error: {e}")
            return []

        summaries = []
        for plan_id, uid in index.items():
            if user_id and uid != user_id:
                continue
            try:
                plan = self.load_plan(plan_id)
                total = len(plan.steps)
                completed = sum(1 for s in plan.steps if s.status == "COMPLETED")
                failed = sum(1 for s in plan.steps if s.status == "FAILED")
                summaries.append({
                    "plan_id": plan.plan_id,
                    "goal": plan.goal[:200],
                    "status": plan.status,
                    "user_id": plan.user_id,
                    "session_id": plan.session_id,
                    "execution_mode": plan.execution_mode,
                    "created_at": plan.created_at,
                    "completed_at": plan.completed_at,
                    "steps_total": total,
                    "steps_completed": completed,
                    "steps_failed": failed,
                    "agents": list({s.agent_id for s in plan.steps}),
                })
            except Exception as e:
                logger.warning(f"PlanManager.list_plans: failed to load plan {plan_id}: {e}")
                continue

        # Sort by created_at descending, apply limit
        summaries.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return summaries[:limit]


# ── Module-level singleton ─────────────────────────────────────────────────────

plan_manager = PlanManager()
