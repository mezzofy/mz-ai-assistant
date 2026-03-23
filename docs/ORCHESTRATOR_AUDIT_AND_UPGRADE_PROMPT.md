# Mezzofy AI — Orchestrator Audit & Upgrade Prompt
# Use this prompt in Claude Code from ~/mz-ai-assistant

Review the existing Orchestrator in the Mezzofy AI Assistant project at
~/mz-ai-assistant and ensure it correctly implements all three responsibilities:
PLAN, DELEGATE, and AGGREGATE.

The Orchestrator must follow Pattern 2 (sequential with review) and Pattern 3
(parallel with join) depending on task dependency. Pattern 1 (fire and forget)
must be eliminated entirely wherever it exists.

Pattern definitions for reference:
  Pattern 1 — Fire and forget (FORBIDDEN)
    Orchestrator spawns agent → gets result → passes raw output to user.
    No plan, no review, no synthesis. Must be replaced.

  Pattern 2 — Sequential with review (REQUIRED for dependent steps)
    Orchestrator writes plan → spawns Agent A → reviews output →
    spawns Agent B with A's output as context → reviews → synthesises
    final response → sends to user.

  Pattern 3 — Parallel with join (REQUIRED for independent steps)
    Orchestrator writes plan → spawns Agent A + B + C simultaneously
    (Celery group) → waits for all (Celery chord) → reviews all outputs
    together → synthesises final response → sends to user.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE 1 — DEEP AUDIT: CURRENT ORCHESTRATOR IMPLEMENTATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Read every file related to the Orchestrator — the main orchestrator module,
all agent files, all routing logic, all task dispatchers, and any planning
or context management code. Do not skim. Read the full content of each file.

Answer every question below with specific file names and line numbers.

── 1A. PLAN — Does the Orchestrator write a plan before spawning agents? ──

  1. Is there any code that analyses the user request and produces a
     structured plan (list of steps, agents, dependencies) BEFORE
     any agent is spawned?

  2. Is the plan persisted anywhere (Redis, DB, file)?
     Or does it exist only in memory / as a local variable?

  3. Does the plan include:
     - Step-by-step breakdown with agent assignments?
     - Dependencies between steps (which steps must complete before others)?
     - Which steps can run in parallel vs must run sequentially?
     - Expected output type for each step?
     If any of these are missing, list which ones.

  4. Can the plan be inspected externally (via API or portal)?
     Or is it invisible to the outside world?

  5. Verdict: PASS / PARTIAL / FAIL
     If PARTIAL or FAIL — list exactly what is missing.

── 1B. DELEGATE — How does the Orchestrator spawn agents? ──

  6. When the Orchestrator spawns an agent, what context does it pass?
     - Does it pass the shared context (outputs of prior steps)?
     - Does it pass the original user goal?
     - Does it pass specific instructions for this step?
     - Does it pass retry feedback if this is a retry?
     List what IS passed and what is NOT passed.

  7. Are agents spawned as Celery tasks or in-process calls?
     If in-process — this is a Pattern 1 symptom. Flag it.

  8. For multi-step requests, are dependent steps always executed
     sequentially (Pattern 2)? Or are they sometimes spawned all at
     once regardless of dependencies (Pattern 1)?

  9. For independent steps (no dependency between them), are they
     spawned in parallel using Celery group + chord (Pattern 3)?
     Or are they spawned sequentially even when they could run in
     parallel (inefficiency)?

  10. Does each agent have a uniform interface contract?
      Specifically — does every agent task accept:
        - plan_id, step_id, context, instructions, feedback?
      And return:
        - status, result, summary, deliverable, quality_score, issues?
      List any agents that do NOT follow this contract.

  11. Verdict: PASS / PARTIAL / FAIL
      If PARTIAL or FAIL — list exactly what is missing.

── 1C. AGGREGATE — How does the Orchestrator collect and review outputs? ──

  12. After an agent completes, does the Orchestrator review the output
      against the original goal before proceeding?
      - Is this review a real Claude API call?
      - Or is it a heuristic / keyword check?
      - Or does no review happen at all?

  13. Does the review result in any action?
      - Can it trigger a retry of the step with gap feedback?
      - Can it block the next step from starting until quality passes?
      - Or is the output always accepted regardless of quality?

  14. Is there a shared context store that accumulates agent outputs
      so downstream agents can see what prior agents produced?
      - Where is it stored (Redis, memory, DB)?
      - Does it survive a FastAPI restart?

  15. When all steps complete, does the Orchestrator synthesise a
      coherent final response?
      - Is this synthesis a real Claude API call with all step outputs?
      - Or does it pass raw agent output directly to the user?
      - Does the synthesised response include: confirmation of what was
        done, key findings summary, deliverable link?

  16. Verdict: PASS / PARTIAL / FAIL
      If PARTIAL or FAIL — list exactly what is missing.

── 1D. PATTERN CLASSIFICATION ──

For each type of user request the system currently handles, classify
which pattern the Orchestrator uses:

  | Request type          | Current pattern | Should be |
  |-----------------------|-----------------|-----------|
  | Single agent task     | ?               | P2        |
  | Multi-step dependent  | ?               | P2        |
  | Multi-step independent| ?               | P3        |
  | Mixed (some deps)     | ?               | P2 + P3   |

Identify every case where Pattern 1 is used — these are all gaps.

── 1E. SUMMARY BEFORE PROCEEDING ──

Produce a gap report in this format before starting Phase 2:

  PLAN gaps:     [list or "none"]
  DELEGATE gaps: [list or "none"]
  AGGREGATE gaps:[list or "none"]
  Pattern 1 usage found in: [list files and functions or "none"]
  Pattern 2 missing for:    [list request types or "none"]
  Pattern 3 missing for:    [list request types or "none"]

Do not proceed to Phase 2 until this report is complete.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE 2 — FIX: PLAN
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

If the PLAN gap report from Phase 1 shows PARTIAL or FAIL, implement
the following. If PASS, skip to Phase 3.

── 2A. Data Structures ──

Create server/orchestrator/plan_manager.py with these dataclasses:

  @dataclass
  class PlanStep:
      step_id: str                    # e.g. "step_1"
      step_number: int
      agent: str                      # e.g. "Research Agent"
      description: str                # human-readable what this step does
      depends_on: list[str]           # step_ids that must complete first
      can_run_parallel: bool          # True if no dependencies
      status: str                     # PENDING|STARTED|COMPLETED|FAILED|RETRYING
      celery_task_id: str | None
      instructions: str               # specific instructions from Orchestrator
      context_keys: list[str]         # which shared_context keys this step needs
      output: dict | None             # written by agent on completion
      review: dict | None             # written by Orchestrator after reviewing
      retry_count: int = 0
      max_retries: int = 2
      started_at: str | None = None
      completed_at: str | None = None

  @dataclass
  class ExecutionPlan:
      plan_id: str
      goal: str                       # original user request
      user_id: str
      conversation_id: str
      steps: list[PlanStep]
      shared_context: dict            # accumulates all agent outputs
      execution_mode: str             # "sequential"|"parallel"|"mixed"
      status: str                     # PENDING|IN_PROGRESS|COMPLETED|FAILED
      created_at: str
      completed_at: str | None = None
      final_output: str | None = None
      total_retries: int = 0

── 2B. PlanManager Class ──

  class PlanManager:

    REDIS_DB = 3  # broker=0, backend=1, beat=2, plans=3
    KEY_PREFIX = "mz:plan:"
    INDEX_KEY = "mz:plan:index"

    def create_plan(goal, user_id, conversation_id) -> ExecutionPlan:
      # Calls Claude API to analyse goal and produce structured plan
      # Claude must return JSON with steps, dependencies, parallel flags
      # Saves plan to Redis DB 3
      # Registers plan_id in index hash for listing
      # Returns ExecutionPlan

    def save_plan(plan: ExecutionPlan):
      # Serialise and write to Redis DB 3
      # Key: mz:plan:{plan_id}
      # Also update index: mz:plan:index hset plan_id → serialised summary

    def load_plan(plan_id: str) -> ExecutionPlan:
      # Read from Redis DB 3 and deserialise

    def update_step(plan_id, step_id, status, output=None, review=None):
      # Load plan, update the specific step, save plan
      # Also append to shared_context if output provided:
      #   shared_context[step_id] = output

    def get_next_steps(plan: ExecutionPlan) -> list[PlanStep]:
      # Returns steps whose dependencies are all COMPLETED
      # and whose own status is PENDING
      # These are ready to execute right now

    def get_parallel_group(plan: ExecutionPlan) -> list[PlanStep]:
      # Returns subset of get_next_steps() where can_run_parallel=True
      # These should be dispatched as a Celery group

    def is_plan_complete(plan: ExecutionPlan) -> bool:
      # True if all steps are COMPLETED or if any step is FAILED
      # with retry_count >= max_retries

    def list_plans(user_id: str) -> list[dict]:
      # Read from mz:plan:index, filter by user_id
      # Return summary list (not full plan objects)

── 2C. Planning Claude API Call ──

  The Claude API call inside create_plan() must use this system prompt:

    You are the Mezzofy AI Orchestrator planning an execution.
    Given the user's goal, produce a structured execution plan in JSON.

    Available agents and their capabilities:
      Research Agent   — web research, competitor analysis, data gathering,
                         summarisation of findings
      Developer Agent  — PPTX generation, PDF creation, DOCX writing,
                         XLSX modelling, code generation
      Outreach Agent   — lead generation, CRM enrichment, email drafting,
                         LinkedIn outreach sequences
      [add any other agents found in the codebase]

    Rules for planning:
    - Break the goal into the minimum number of steps needed
    - Assign each step to the most appropriate agent
    - Mark depends_on for any step that needs a prior step's output
    - Mark can_run_parallel: true only when step has NO dependencies
    - Write specific instructions for each step — not generic
    - Identify the expected output type for each step

    Return ONLY valid JSON in this exact format, no prose:
    {
      "goal_summary": "...",
      "execution_mode": "sequential|parallel|mixed",
      "steps": [
        {
          "step_id": "step_1",
          "step_number": 1,
          "agent": "Research Agent",
          "description": "...",
          "instructions": "...",
          "depends_on": [],
          "can_run_parallel": false,
          "context_keys": [],
          "expected_output_type": "research_findings"
        }
      ]
    }

  Validate that the returned JSON is parseable and all depends_on
  references point to valid step_ids before saving the plan.
  If validation fails, retry the planning call once with the error
  appended to the prompt.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE 3 — FIX: DELEGATE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

If the DELEGATE gap report from Phase 1 shows PARTIAL or FAIL, implement
the following. If PASS, skip to Phase 4.

── 3A. Uniform Agent Interface Contract ──

Every agent task in the codebase must be updated to accept and return
the same interface. Update all existing agent tasks to match:

  INPUT (Celery task arguments):
    plan_id: str          # which plan this step belongs to
    step_id: str          # which step within that plan
    context: dict         # shared_context from plan — all prior outputs
    instructions: str     # specific instructions for this step
    feedback: str | None  # populated on retry — what to fix

  OUTPUT (returned dict on task completion):
    {
      "status": "completed" | "failed",
      "result": {...},           # agent-specific structured output
      "summary": "...",          # 1-2 sentence human-readable summary
      "deliverable": {           # null if no file produced
          "type": "pptx|pdf|docx|xlsx|data|null",
          "path": "...",
          "url": "..."
      },
      "quality_score": 0.0-1.0,  # agent's self-assessed confidence
      "issues": []                # problems the agent flagged itself
    }

  ON COMPLETION every agent task must call:
    from tasks.orchestrator_tasks import handle_step_completion
    handle_step_completion.delay(plan_id, step_id, output)

  Do not change the agent's internal logic — only wrap the input/output
  to match this contract. If an agent currently returns a different
  structure, add a normalisation layer at the end of the task.

── 3B. Pattern 2 — Sequential Dispatch with Review ──

Create or update tasks/orchestrator_tasks.py:

  @celery.task(bind=True, name="mz.orchestrator.execute_plan")
  def execute_plan_task(self, plan_id: str):
    plan = plan_manager.load_plan(plan_id)
    self.update_state(state="STARTED", meta={
        "plan_id": plan_id,
        "goal": plan.goal,
        "status": "IN_PROGRESS"
    })

    while not plan_manager.is_plan_complete(plan):
        plan = plan_manager.load_plan(plan_id)  # reload for latest state
        next_steps = plan_manager.get_next_steps(plan)

        if not next_steps:
            # All remaining steps are waiting on running steps
            time.sleep(2)
            continue

        parallel_steps = plan_manager.get_parallel_group(plan)
        sequential_steps = [s for s in next_steps
                           if s not in parallel_steps]

        # Pattern 3: dispatch independent steps as Celery group
        if len(parallel_steps) > 1:
            dispatch_parallel_steps(plan_id, parallel_steps)

        # Pattern 2: dispatch dependent steps one at a time
        for step in sequential_steps:
            dispatch_sequential_step(plan_id, step)

    # All steps complete — synthesise and respond
    orchestrator_synthesise.delay(plan_id)

  def dispatch_sequential_step(plan_id: str, step: PlanStep):
    plan = plan_manager.load_plan(plan_id)
    context = {k: plan.shared_context[k]
               for k in step.context_keys
               if k in plan.shared_context}

    task = route_to_agent(step.agent).apply_async(
        kwargs={
            "plan_id": plan_id,
            "step_id": step.step_id,
            "context": context,
            "instructions": step.instructions,
            "feedback": None
        }
    )
    plan_manager.update_step(plan_id, step.step_id,
                             status="STARTED",
                             celery_task_id=task.id)

── 3C. Pattern 3 — Parallel Dispatch with Chord ──

  def dispatch_parallel_steps(plan_id: str, steps: list[PlanStep]):
    plan = plan_manager.load_plan(plan_id)

    # Build Celery group — all tasks start simultaneously
    job_group = group([
        route_to_agent(step.agent).s(
            plan_id=plan_id,
            step_id=step.step_id,
            context={k: plan.shared_context[k]
                     for k in step.context_keys
                     if k in plan.shared_context},
            instructions=step.instructions,
            feedback=None
        )
        for step in steps
    ])

    # Chord: run group in parallel, call parallel_join when ALL complete
    chord(job_group)(parallel_join_task.s(
        plan_id=plan_id,
        step_ids=[s.step_id for s in steps]
    ))

    # Mark all parallel steps as STARTED
    for step in steps:
        plan_manager.update_step(plan_id, step.step_id, status="STARTED")

  @celery.task(name="mz.orchestrator.parallel_join")
  def parallel_join_task(results: list, plan_id: str, step_ids: list[str]):
    # Called automatically by Celery chord when ALL parallel tasks complete
    # results is a list of outputs from each parallel task in order
    for step_id, result in zip(step_ids, results):
        handle_step_completion(plan_id, step_id, result)

── 3D. Agent Router ──

  def route_to_agent(agent_name: str):
    # Maps agent name string to the correct Celery task function
    AGENT_MAP = {
        "Research Agent":   tasks.agent_tasks.research_agent_task,
        "Developer Agent":  tasks.agent_tasks.developer_agent_task,
        "Outreach Agent":   tasks.outreach_tasks.outreach_agent_task,
        # add all agents found in codebase
    }
    if agent_name not in AGENT_MAP:
        raise ValueError(f"Unknown agent: {agent_name}")
    return AGENT_MAP[agent_name]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE 4 — FIX: AGGREGATE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

If the AGGREGATE gap report from Phase 1 shows PARTIAL or FAIL, implement
the following. If PASS, skip to Phase 5.

── 4A. Step Completion Handler ──

  @celery.task(name="mz.orchestrator.handle_step_completion")
  def handle_step_completion(plan_id: str, step_id: str, result: dict):

    # 1. Write agent output to plan context
    plan_manager.update_step(
        plan_id, step_id,
        status="COMPLETED",
        output=result
    )

    # 2. Trigger Orchestrator review of this output
    review = orchestrator_review(plan_id, step_id)

    # 3. Act on review result
    if review["should_retry"]:
        retry_step(plan_id, step_id, review["gaps"])
    else:
        # 4. Emit real-time WebSocket update to user
        notify_user_step_complete(plan_id, step_id, result["summary"])

        # 5. Check if plan is now complete
        plan = plan_manager.load_plan(plan_id)
        if plan_manager.is_plan_complete(plan):
            orchestrator_synthesise.delay(plan_id)

── 4B. Orchestrator Review (Claude API call) ──

  def orchestrator_review(plan_id: str, step_id: str) -> dict:
    plan = plan_manager.load_plan(plan_id)
    step = next(s for s in plan.steps if s.step_id == step_id)

    review_prompt = f"""
    You are the Mezzofy AI Orchestrator reviewing an agent's output.

    Original user goal: {plan.goal}
    Step description: {step.description}
    Step instructions given to agent: {step.instructions}
    Agent output received: {json.dumps(step.output, indent=2)}
    Agent self-reported quality score: {step.output.get("quality_score")}
    Agent self-reported issues: {step.output.get("issues")}
    This is retry number: {step.retry_count} of {step.max_retries}

    Review this output and respond in JSON only, no prose:
    {{
      "addresses_goal": true|false,
      "quality_sufficient": true|false,
      "completeness_score": 0.0-1.0,
      "gaps": ["list of specific gaps or missing items"],
      "should_retry": true|false,
      "retry_instructions": "specific instructions to fix gaps (if retry)",
      "proceed": true|false,
      "review_notes": "brief reviewer notes"
    }}

    Set should_retry=true only if:
    - Critical gaps exist AND retry_count < max_retries
    - Do not retry for minor or cosmetic issues
    - Do not retry if retry_count >= max_retries (accept and proceed)
    """

    response = call_claude_api(review_prompt)
    review_result = parse_json_response(response)

    # Save review to step
    plan_manager.update_step(plan_id, step_id, review=review_result)
    return review_result

── 4C. Retry with Feedback ──

  def retry_step(plan_id: str, step_id: str, gaps: list[str]):
    plan = plan_manager.load_plan(plan_id)
    step = next(s for s in plan.steps if s.step_id == step_id)

    if step.retry_count >= step.max_retries:
        # Max retries reached — mark as completed with warning and proceed
        plan_manager.update_step(plan_id, step_id, status="COMPLETED")
        notify_user_step_complete(
            plan_id, step_id,
            f"Completed with some limitations: {', '.join(gaps)}"
        )
        return

    # Increment retry count and re-dispatch with feedback
    step.retry_count += 1
    step.status = "RETRYING"
    plan_manager.save_plan(plan)

    feedback = (
        f"Previous attempt had these issues: {'; '.join(gaps)}. "
        f"Please address all of them in this retry."
    )

    context = {k: plan.shared_context[k]
               for k in step.context_keys
               if k in plan.shared_context}

    route_to_agent(step.agent).apply_async(kwargs={
        "plan_id": plan_id,
        "step_id": step_id,
        "context": context,
        "instructions": step.instructions,
        "feedback": feedback
    })

── 4D. Final Synthesis (Claude API call) ──

  @celery.task(name="mz.orchestrator.synthesise")
  def orchestrator_synthesise(plan_id: str):
    plan = plan_manager.load_plan(plan_id)

    # Collect all step summaries and deliverables
    step_summaries = []
    deliverables = []
    for step in plan.steps:
        if step.output:
            step_summaries.append({
                "agent": step.agent,
                "description": step.description,
                "summary": step.output.get("summary"),
                "issues": step.output.get("issues", [])
            })
            if step.output.get("deliverable"):
                deliverables.append(step.output["deliverable"])

    synthesis_prompt = f"""
    You are the Mezzofy AI Assistant responding to a user.

    The user asked: {plan.goal}

    Here is what each agent completed:
    {json.dumps(step_summaries, indent=2)}

    Deliverables produced:
    {json.dumps(deliverables, indent=2)}

    Write a concise, professional response to the user that:
    1. Confirms the request has been completed
    2. Summarises the key findings or outputs in 2-4 sentences
    3. Mentions each deliverable with its download link if applicable
    4. Flags any limitations or issues the user should know about
    5. Offers a natural next step or follow-up question

    Rules:
    - Do NOT dump raw agent output or JSON
    - Do NOT use technical terms like "step_1" or "celery task"
    - Write as Mezzofy AI Assistant — confident, friendly, results-focused
    - Keep it under 150 words unless deliverables require more explanation
    - Use Mezzofy brand voice: direct, no filler phrases, no passive voice
    """

    final_response = call_claude_api(synthesis_prompt)

    # Save final output to plan
    plan.final_output = final_response
    plan.status = "COMPLETED"
    plan.completed_at = datetime.utcnow().isoformat()
    plan_manager.save_plan(plan)

    # Send to user via WebSocket
    send_to_user_websocket(
        user_id=plan.user_id,
        conversation_id=plan.conversation_id,
        message=final_response,
        deliverables=deliverables
    )

    # Append to conversation history so context is maintained
    append_to_conversation_history(
        conversation_id=plan.conversation_id,
        role="assistant",
        content=final_response,
        metadata={"plan_id": plan_id, "deliverables": deliverables}
    )

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE 5 — ELIMINATE ALL PATTERN 1 USAGE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Using the Pattern 1 list from the Phase 1 gap report, fix every instance:

For each Pattern 1 occurrence found:

  1. Identify whether the request type needs Pattern 2 or Pattern 3:
       - Has step dependencies?        → Pattern 2
       - All steps independent?        → Pattern 3
       - Mix of both?                  → Pattern 2 + 3 (mixed plan)

  2. Replace the fire-and-forget call with:
       a. A call to plan_manager.create_plan() to write a plan first
       b. A call to execute_plan_task.delay(plan_id) to start execution
       c. Return plan_id to the API caller immediately

  3. Remove any code that:
       - Passes raw agent output directly to the user
       - Awaits agent completion synchronously in the API handler
       - Skips the review step after agent completion
       - Calls agents without passing plan_id and step_id

  4. For single-agent requests that were previously Pattern 1:
     These still need a plan — even a one-step plan goes through
     the full PLAN → DELEGATE → AGGREGATE cycle so:
       - The step is reviewed before responding
       - The response is synthesised not raw
       - The task appears in the Background Tasks portal
       - The execution survives a FastAPI restart

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE 6 — REAL-TIME USER UPDATES VIA WEBSOCKET
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

The user must receive progress updates during plan execution — not just
silence until the final response arrives. Implement or verify:

  Step start notification:
    "Starting [step description] with [Agent name]..."

  Step complete notification:
    "✓ [Step description] — [agent summary in 1 sentence]"

  Retry notification:
    "Improving [step description] — [gap being fixed]..."

  Final response:
    Full synthesised response + deliverable links

  Error notification:
    "One step encountered an issue: [plain English description].
     Continuing with available results."

  Each notification must be sent via the existing WebSocket connection
  to the user's active conversation. Use the existing WebSocket send
  mechanism already in the codebase — do not create a new one.

  Notification format must match the existing message format in the
  frontend so it renders correctly in the chat UI — inspect the
  current message structure before implementing.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE 7 — PORTAL: AGENT PLANS TAB
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Extend the Background Tasks portal page (already built) to add a third tab.

Add Tab 3: "Agent Plans" to the existing tabbed Background Tasks page.

── Plan List View ──

  Table columns:
    Goal | Steps | Status | Agent(s) | Created | Duration | Actions

  Each row example:
  ┌────────────────────────────────────────────────────────────────────┐
  │ Competitor research + pitch deck  5 steps  ● IN_PROGRESS          │
  │ Research Agent, Developer Agent   10:15 AM  running 4m 32s        │
  │ ██████░░░░ 3/5 steps done                                         │
  │ [View Detail]                                                      │
  └────────────────────────────────────────────────────────────────────┘

  Status badges (Mezzofy brand):
    PENDING     → grey
    IN_PROGRESS → orange pulsing (#f97316)
    COMPLETED   → black with ✓
    FAILED      → red with ✗

── Plan Detail View (expand or side panel) ──

  Header:
    - Plan ID (short, copyable)
    - Original user goal (full text)
    - Overall status and duration

  Step timeline (one row per step):
  ┌──────────────────────────────────────────────────────────────────┐
  │ ✓  Step 1  Research Agent    Competitor analysis    10:15–10:18  │
  │    Quality: 0.94  No issues                                      │
  │    [View Output]  [View Review]                                  │
  ├──────────────────────────────────────────────────────────────────┤
  │ →  Step 2  Research Agent    Summarise findings     In progress  │
  │    Started: 10:18                                                │
  ├──────────────────────────────────────────────────────────────────┤
  │ ○  Step 3  Developer Agent   Generate PPTX          Pending      │
  │    Waiting on: Step 2                                            │
  └──────────────────────────────────────────────────────────────────┘

  Step expand (click [View Output]):
    - Agent name and description
    - Agent summary text
    - Quality score and issues list
    - Deliverable download button if applicable
    - Raw result JSON (collapsed, expandable)

  Step expand (click [View Review]):
    - Orchestrator review result
    - completeness_score, gaps found, should_retry decision
    - Retry history if step was retried (show each attempt)

  Final output section (shown when plan COMPLETED):
    - Full synthesised response text
    - All deliverables with download links

── New API Endpoints for Plans Tab ──

  GET  /api/plans
       List plans from Redis DB 3.
       Filter: ?user_id=&status=&limit=20&offset=0

  GET  /api/plans/{plan_id}
       Full plan detail with all steps, outputs, and reviews.

  GET  /api/plans/{plan_id}/steps/{step_id}
       Single step detail including full output and review.

  Note: declare /api/plans/stats BEFORE /api/plans/{plan_id} in router
  to avoid FastAPI treating "stats" as a plan_id.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE 8 — END-TO-END VERIFICATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Run every test below. Report PASS or FAIL with evidence for each.

── 8A. Pattern 2 — Sequential with Review ──

  Test: Submit a request that requires dependent steps
  (e.g. "Research our competitors and write a summary report")

  Verify:
  [ ] Plan is written to Redis before any agent starts
      redis-cli -n 3 keys "mz:plan:*"

  [ ] Step 2 does NOT start before Step 1 is COMPLETED
      Check timestamps in plan detail — step_2.started_at must be
      after step_1.completed_at

  [ ] Step 1 output appears in Step 2's context
      Log or inspect: developer_agent_task received context with
      step_1 key populated

  [ ] Orchestrator review runs after each step
      Check: each step has a non-null review field in Redis

  [ ] Review can trigger retry
      Manually set quality_score=0.1 in a test task output and
      verify retry is triggered with feedback

  [ ] Retry receives feedback from review
      Log: agent task received feedback parameter with gap description

  [ ] Final response is synthesised — not raw agent output
      The user-facing message must be prose, not JSON

  [ ] User received WebSocket updates at each step

── 8B. Pattern 3 — Parallel with Join ──

  Test: Submit a request with independent steps
  (e.g. "Research competitor A, competitor B, and competitor C")

  Verify:
  [ ] All three research steps start within 2 seconds of each other
      Check started_at timestamps in plan — must be nearly simultaneous

  [ ] parallel_join_task is triggered only after ALL three complete
      Check: join task celery_task_id appears in logs after last
      of the three completes

  [ ] All three outputs are available in shared_context before
      any downstream step begins

  [ ] Celery group + chord used — not three sequential .delay() calls
      Inspect dispatch_parallel_steps code is called, not three
      separate route_to_agent().apply_async() calls

── 8C. Pattern 1 Elimination ──

  [ ] Grep for any remaining fire-and-forget patterns:
      grep -rn "create_task\|add_task\|executor.submit" \
           ~/mz-ai-assistant/server \
           --include="*.py" \
           | grep -v "execute_plan_task\|handle_step_completion"

      Expected: zero results (or only legitimate non-agent uses)

  [ ] Every agent invocation goes through route_to_agent()
      grep -rn "research_agent_task\|developer_agent_task\|outreach_agent_task" \
           ~/mz-ai-assistant/server --include="*.py"

      Expected: only appears inside orchestrator_tasks.py dispatch functions

  [ ] No agent output is passed directly to user without synthesis
      grep -rn "send_to_user\|websocket.send\|stream_response" \
           ~/mz-ai-assistant/server --include="*.py"

      Expected: only appears inside orchestrator_synthesise() and
      notify_user_step_complete() — not in agent task files

── 8D. Resilience ──

  [ ] Submit a multi-step plan, restart FastAPI mid-execution:
      sudo systemctl restart mz-ai-assistant
      Plan must continue executing — Celery worker was not restarted
      User receives final synthesised response after restart

  [ ] Verify plan survives full service restart:
      redis-cli -n 3 get mz:plan:{plan_id}
      Must return full plan JSON after FastAPI restart

── 8E. Portal Verification ──

  [ ] Agent Plans tab appears in Background Tasks page
  [ ] Plan list shows correct steps count, status, agents, duration
  [ ] Step timeline shows correct sequence and dependency indicators
  [ ] [View Output] shows agent result summary and quality score
  [ ] [View Review] shows Orchestrator review with gaps and decision
  [ ] Retry history visible for any retried step
  [ ] Final synthesised response shown at bottom of completed plan
  [ ] Deliverable download links work from plan detail view

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CONSTRAINTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

- Read every relevant file in full before writing any code.
  Do not assume what a file contains — open and read it.

- Do not break any existing single-agent flows. The plan architecture
  is additive — even a single-agent request gets a one-step plan.

- Do not remove any existing agent logic. Only wrap inputs/outputs
  to match the uniform interface contract.

- Every Claude API call (planning, review, synthesis) must be a real
  API call — not a heuristic, keyword match, or hardcoded decision.

- Final response to user must ALWAYS be synthesised by the Orchestrator.
  Never pass raw agent output directly to the user. This is absolute.

- Orchestrator review must run after EVERY step completion.
  It cannot be skipped for "simple" or "fast" steps.

- shared_context must be passed to every agent that has context_keys.
  No agent should be blind to what prior agents produced.

- Redis DB separation must be maintained:
    broker=DB0, backend=DB1, beat=DB2, plans=DB3

- WebSocket notifications must use the existing WebSocket mechanism
  already in the codebase. Do not create a new WebSocket layer.

- Brand colours apply to all new portal components:
    primary orange #f97316, black #000000, white #ffffff,
    light orange #fef3ea

- Report Phase 1 gap report in full before writing any code.
  Report each subsequent phase completion before starting the next.

- If a gap from Phase 1 is already correctly implemented, say so
  explicitly and skip that fix phase. Do not re-implement working code.
