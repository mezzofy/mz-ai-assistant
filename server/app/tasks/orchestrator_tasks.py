"""
orchestrator_tasks.py — Celery tasks for the v2.5 PLAN→DELEGATE→AGGREGATE pipeline.

Tasks:
    execute_plan_task        — Main loop: load plan → dispatch steps → repeat
    parallel_join_task       — Chord callback: fires handle_step_completion for each result
    handle_step_completion   — Per-step review + retry / advance plan
    orchestrator_synthesise  — Final synthesis + WebSocket notification
    notify_step_start        — WS notification: step starting
    notify_step_complete     — WS notification: step done
    notify_step_retry        — WS notification: step retrying

All Celery task bodies are synchronous. Async operations are wrapped in asyncio.run().
Per project standard: `from app.core.database import engine; engine.sync_engine.dispose()`
precedes every asyncio.run() call to prevent "Future attached to a different loop" errors.
"""

import asyncio
import json
import logging
import os
from datetime import datetime

from app.tasks.celery_app import celery_app
from app.orchestrator.plan_manager import plan_manager

logger = logging.getLogger("mezzofy.tasks.orchestrator")


# ── Helper: import process_delegated_agent_task lazily to avoid circular imports ──

def _get_process_delegated_task():
    """Lazy import of process_delegated_agent_task to avoid circular imports."""
    from app.tasks.tasks import process_delegated_agent_task
    return process_delegated_agent_task


# ── route_to_celery_task ───────────────────────────────────────────────────────

def route_to_celery_task(agent_id: str):
    """
    Map an agent_id string to the Celery task function that will execute it.

    All agents share process_delegated_agent_task — the agent_id in the task
    payload determines which Python agent class runs inside the task.
    """
    AGENT_TASK_MAP = {
        "agent_management": True,
        "agent_finance":    True,
        "agent_sales":      True,
        "agent_marketing":  True,
        "agent_support":    True,
        "agent_hr":         True,
        "agent_legal":      True,
        "agent_research":   True,
        "agent_developer":  True,
        "agent_scheduler":  True,
    }
    if agent_id not in AGENT_TASK_MAP:
        raise ValueError(f"route_to_celery_task: unknown agent_id {agent_id!r}")
    return _get_process_delegated_task()


# ── execute_plan_task ──────────────────────────────────────────────────────────

@celery_app.task(
    bind=True,
    max_retries=0,
    name="app.tasks.orchestrator_tasks.execute_plan_task",
)
def execute_plan_task(self, plan_id: str):
    """
    Main orchestration loop.

    Loads plan → gets next steps → dispatches parallel group (chord) or
    next sequential step. Called again by handle_step_completion when a step
    completes without triggering plan completion.
    """
    try:
        plan = plan_manager.load_plan(plan_id)
    except KeyError:
        logger.error(f"execute_plan_task: plan not found: {plan_id}")
        return

    if plan_manager.is_plan_complete(plan):
        logger.info(f"execute_plan_task: plan {plan_id} already complete — triggering synthesis")
        orchestrator_synthesise.delay(plan_id)
        return

    next_steps = plan_manager.get_next_steps(plan)
    if not next_steps:
        logger.info(f"execute_plan_task: plan {plan_id} — no next steps (all in flight or blocked)")
        return

    parallel_group = plan_manager.get_parallel_group(plan)

    if len(parallel_group) > 1:
        # Multiple parallel-eligible steps — use Celery chord
        logger.info(f"execute_plan_task: plan {plan_id} — dispatching {len(parallel_group)} parallel steps")
        dispatch_parallel_steps(plan_id, parallel_group)
    else:
        # Sequential — dispatch only the first next step
        step = next_steps[0]
        logger.info(f"execute_plan_task: plan {plan_id} — dispatching sequential step {step.step_id}")
        dispatch_sequential_step(plan_id, step)


# ── dispatch_sequential_step ───────────────────────────────────────────────────

def dispatch_sequential_step(plan_id: str, step) -> None:
    """
    Dispatch a single plan step as a Celery sub-task (Pattern 2 — sequential).

    Builds task payload with plan_id, step_id, context, and instructions,
    then routes to process_delegated_agent_task via route_to_celery_task().
    """
    plan = plan_manager.load_plan(plan_id)

    # Build context dict from shared_context using this step's context_keys
    context = {
        k: plan.shared_context[k]
        for k in step.context_keys
        if k in plan.shared_context
    }

    # Build task payload — merge original task context with orchestrator fields
    safe_original = {
        k: v for k, v in plan.original_task.items()
        if k not in ("_config",)
    }

    task_payload = {
        **safe_original,
        "message": step.description,
        "_plan_id": plan_id,
        "_step_id": step.step_id,
        "_context": context,
        "_instructions": step.instructions,
        "_feedback": None,
        "source": "agent_delegation",
        "_requesting_agent_id": "agent_management",
        "_parent_task_id": plan_id,
    }

    celery_task = route_to_celery_task(step.agent_id).apply_async(
        kwargs={
            "task_data": task_payload,
            "agent_id": step.agent_id,
            "parent_task_id": plan_id,
            "requested_by_agent_id": "agent_management",
        }
    )

    plan_manager.update_step(plan_id, step.step_id, status="STARTED", celery_task_id=celery_task.id)
    notify_step_start(plan_id, step)
    logger.info(f"dispatch_sequential_step: plan={plan_id} step={step.step_id} celery_id={celery_task.id}")


# ── dispatch_parallel_steps ────────────────────────────────────────────────────

def dispatch_parallel_steps(plan_id: str, steps: list) -> None:
    """
    Dispatch multiple steps in parallel using a Celery group + chord (Pattern 3).

    The chord callback (parallel_join_task) fires after ALL group tasks complete
    and calls handle_step_completion for each result.
    """
    from celery import group, chord

    plan = plan_manager.load_plan(plan_id)
    process_delegated = _get_process_delegated_task()

    job_signatures = []
    for step in steps:
        context = {
            k: plan.shared_context[k]
            for k in step.context_keys
            if k in plan.shared_context
        }
        safe_original = {
            k: v for k, v in plan.original_task.items()
            if k not in ("_config",)
        }
        task_payload = {
            **safe_original,
            "message": step.description,
            "_plan_id": plan_id,
            "_step_id": step.step_id,
            "_context": context,
            "_instructions": step.instructions,
            "_feedback": None,
            "source": "agent_delegation",
            "_requesting_agent_id": "agent_management",
            "_parent_task_id": plan_id,
        }
        sig = process_delegated.s(
            task_data=task_payload,
            agent_id=step.agent_id,
            parent_task_id=plan_id,
            requested_by_agent_id="agent_management",
        )
        job_signatures.append(sig)

    step_ids = [s.step_id for s in steps]
    callback = parallel_join_task.s(plan_id=plan_id, step_ids=step_ids)
    chord(group(job_signatures))(callback)

    for step in steps:
        plan_manager.update_step(plan_id, step.step_id, status="STARTED")
        notify_step_start(plan_id, step)

    logger.info(f"dispatch_parallel_steps: plan={plan_id} steps={step_ids}")


# ── parallel_join_task ─────────────────────────────────────────────────────────

@celery_app.task(name="app.tasks.orchestrator_tasks.parallel_join_task")
def parallel_join_task(results: list, plan_id: str, step_ids: list):
    """
    Chord callback: fires after all parallel steps complete.

    Calls handle_step_completion for each step_id/result pair.
    """
    logger.info(f"parallel_join_task: plan={plan_id} steps={step_ids} results_count={len(results)}")
    for step_id, result in zip(step_ids, results):
        if isinstance(result, dict):
            # Already a normalised dict or raw agent result — normalise if needed
            if "status" not in result or "summary" not in result:
                from app.tasks.tasks import _normalise_agent_output
                result = _normalise_agent_output(result)
        else:
            result = {
                "status": "failed",
                "result": {},
                "summary": str(result)[:500] if result else "No result",
                "deliverable": None,
                "quality_score": 0.0,
                "issues": [str(result)],
            }
        handle_step_completion.delay(plan_id, step_id, result)


# ── handle_step_completion ─────────────────────────────────────────────────────

@celery_app.task(name="app.tasks.orchestrator_tasks.handle_step_completion")
def handle_step_completion(plan_id: str, step_id: str, result: dict):
    """
    Called when a plan step completes (by _run_delegated_agent_task or chord).

    Flow:
        1. Update step status to COMPLETED with output
        2. Run orchestrator review (Claude API)
        3. If review says retry → _retry_step
        4. Else → notify complete → check if plan done → synthesise or continue
    """
    logger.info(f"handle_step_completion: plan={plan_id} step={step_id}")

    plan_manager.update_step(plan_id, step_id, status="COMPLETED", output=result)

    try:
        review = _orchestrator_review(plan_id, step_id)
    except Exception as e:
        logger.warning(f"handle_step_completion: review failed (non-fatal): {e}")
        review = {"should_retry": False, "proceed": True}

    if review.get("should_retry"):
        gaps = review.get("gaps", [])
        logger.info(f"handle_step_completion: retrying step={step_id} gaps={gaps}")
        _retry_step(plan_id, step_id, gaps)
    else:
        summary = ""
        if isinstance(result, dict):
            summary = result.get("summary", "")
        notify_step_complete(plan_id, step_id, summary)

        try:
            plan = plan_manager.load_plan(plan_id)
        except Exception as e:
            logger.error(f"handle_step_completion: failed to load plan for completion check: {e}")
            return

        if plan_manager.is_plan_complete(plan):
            logger.info(f"handle_step_completion: plan {plan_id} complete — triggering synthesis")
            orchestrator_synthesise.delay(plan_id)
        else:
            logger.info(f"handle_step_completion: plan {plan_id} — continuing with remaining steps")
            execute_plan_task.delay(plan_id)


# ── _orchestrator_review ───────────────────────────────────────────────────────

def _orchestrator_review(plan_id: str, step_id: str) -> dict:
    """
    Synchronous helper: calls Claude API to review a completed step.

    Builds review prompt, calls Claude, parses JSON response, saves review
    to the step, and returns the review dict.
    """
    try:
        plan = plan_manager.load_plan(plan_id)
    except Exception as e:
        logger.warning(f"_orchestrator_review: failed to load plan {plan_id}: {e}")
        return {"should_retry": False, "proceed": True}

    step = next((s for s in plan.steps if s.step_id == step_id), None)
    if step is None:
        return {"should_retry": False, "proceed": True}

    output_snippet = ""
    if step.output:
        output_snippet = json.dumps(step.output, indent=2)[:1000]

    review_prompt = (
        f"You are the Mezzofy AI Orchestrator reviewing a completed step.\n"
        f"Plan goal: {plan.goal}\n"
        f"Step: {step.description}\n"
        f"Instructions given: {step.instructions}\n"
        f"Agent output: {output_snippet}\n"
        f"Quality score: {step.output.get('quality_score', 'unknown') if step.output else 'unknown'}\n"
        f"Retry count: {step.retry_count}/{step.max_retries}\n\n"
        "Review and return ONLY valid JSON:\n"
        "{\n"
        '  "addresses_goal": true/false,\n'
        '  "quality_sufficient": true/false,\n'
        '  "completeness_score": 0.0-1.0,\n'
        '  "gaps": ["..."],\n'
        '  "should_retry": true/false,\n'
        '  "proceed": true/false\n'
        "}\n\n"
        "Rules: should_retry=true only if quality_sufficient=false AND "
        f"retry_count ({step.retry_count}) < max_retries ({step.max_retries}). "
        "Be lenient on first attempt."
    )

    review_result = asyncio.run(_call_claude_for_review(review_prompt))

    # Save review to step
    try:
        plan_manager.update_step(plan_id, step_id, status="COMPLETED", review=review_result)
    except Exception as e:
        logger.warning(f"_orchestrator_review: failed to save review: {e}")

    return review_result


async def _call_claude_for_review(prompt: str) -> dict:
    """Async Claude API call for step review. Returns parsed review dict."""
    import anthropic
    client = anthropic.AsyncAnthropic()
    try:
        response = await client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text if response.content else "{}"
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(raw[start:end])
    except Exception as e:
        logger.warning(f"_call_claude_for_review: Claude API failed: {e}")
    return {"addresses_goal": True, "quality_sufficient": True, "completeness_score": 0.7,
            "gaps": [], "should_retry": False, "proceed": True}


# ── _retry_step ────────────────────────────────────────────────────────────────

def _retry_step(plan_id: str, step_id: str, gaps: list) -> None:
    """
    Re-dispatch a step with retry feedback, or mark complete if max_retries reached.
    """
    try:
        plan = plan_manager.load_plan(plan_id)
    except Exception as e:
        logger.error(f"_retry_step: failed to load plan {plan_id}: {e}")
        return

    step = next((s for s in plan.steps if s.step_id == step_id), None)
    if step is None:
        return

    if step.retry_count >= step.max_retries:
        logger.info(f"_retry_step: max retries reached for step={step_id} — marking completed with limitations")
        plan_manager.update_step(plan_id, step_id, status="COMPLETED")
        notify_step_complete(plan_id, step_id, f"Completed with limitations: {', '.join(gaps)}")
        return

    # Increment retry count and mark as RETRYING
    step.retry_count += 1
    step.status = "RETRYING"
    plan_manager.save_plan(plan)

    feedback = f"Previous attempt had these issues: {'; '.join(gaps)}. Address all of them."
    context = {
        k: plan.shared_context[k]
        for k in step.context_keys
        if k in plan.shared_context
    }

    notify_step_retry(plan_id, step_id, gaps)

    safe_original = {
        k: v for k, v in plan.original_task.items()
        if k not in ("_config",)
    }
    task_payload = {
        **safe_original,
        "message": step.description,
        "_plan_id": plan_id,
        "_step_id": step_id,
        "_context": context,
        "_instructions": step.instructions,
        "_feedback": feedback,
        "source": "agent_delegation",
        "_requesting_agent_id": "agent_management",
        "_parent_task_id": plan_id,
    }

    route_to_celery_task(step.agent_id).apply_async(
        kwargs={
            "task_data": task_payload,
            "agent_id": step.agent_id,
            "parent_task_id": plan_id,
            "requested_by_agent_id": "agent_management",
        }
    )
    logger.info(f"_retry_step: re-dispatched step={step_id} attempt={step.retry_count}")


# ── orchestrator_synthesise ────────────────────────────────────────────────────

@celery_app.task(name="app.tasks.orchestrator_tasks.orchestrator_synthesise")
def orchestrator_synthesise(plan_id: str):
    """
    Final synthesis task.

    Collects all step summaries and deliverables, calls Claude for a concise
    response, persists plan as COMPLETED, sends WebSocket notification, and
    appends to conversation history.
    """
    try:
        plan = plan_manager.load_plan(plan_id)
    except Exception as e:
        logger.error(f"orchestrator_synthesise: failed to load plan {plan_id}: {e}")
        return

    # Collect step summaries and deliverables
    step_summaries = []
    deliverables = []
    for step in plan.steps:
        summary_entry = {
            "step_id": step.step_id,
            "agent_id": step.agent_id,
            "description": step.description,
            "status": step.status,
        }
        if step.output:
            summary_entry["summary"] = step.output.get("summary", "")[:500]
            d = step.output.get("deliverable")
            if d:
                deliverables.append(d)
        step_summaries.append(summary_entry)

    synthesis_prompt = (
        "You are the Mezzofy AI Assistant responding to a user.\n"
        f"The user asked: {plan.goal}\n"
        f"Here is what each agent completed:\n{json.dumps(step_summaries, indent=2)}\n"
        f"Deliverables: {json.dumps(deliverables, indent=2)}\n\n"
        "Write a concise, professional response (max 150 words):\n"
        "1. Confirm completion\n"
        "2. Summarise key findings in 2-4 sentences\n"
        "3. Mention each deliverable with download link\n"
        "4. Flag any limitations\n"
        "5. Offer a natural next step\n"
        "Rules: No raw JSON. No 'step_1' references. Brand voice: direct, results-focused."
    )

    final_response = asyncio.run(_call_claude_synthesis(synthesis_prompt))

    # Persist final state
    plan.final_output = final_response
    plan.status = "COMPLETED"
    plan.completed_at = datetime.utcnow().isoformat()
    plan_manager.save_plan(plan)

    # Notify user via WebSocket + Redis pub/sub
    _send_ws_to_user(plan.user_id, plan.session_id, final_response, deliverables)

    # Append to conversation history
    try:
        asyncio.run(_append_to_conversation(plan.session_id, final_response, plan_id, deliverables))
    except Exception as e:
        logger.warning(f"orchestrator_synthesise: _append_to_conversation failed (non-fatal): {e}")

    logger.info(f"orchestrator_synthesise: plan {plan_id} completed")


async def _call_claude_synthesis(prompt: str) -> str:
    """Async Claude API call for final synthesis. Returns response text."""
    import anthropic
    client = anthropic.AsyncAnthropic()
    try:
        response = await client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text if response.content else "Task completed."
    except Exception as e:
        logger.warning(f"_call_claude_synthesis: Claude API failed: {e}")
        return "Your multi-agent task has been completed. Please check the Background Tasks page for details."


async def _append_to_conversation(
    session_id: str,
    final_response: str,
    plan_id: str,
    deliverables: list,
) -> None:
    """Append the final synthesised response to the conversation in PostgreSQL."""
    if not session_id:
        return
    try:
        from app.core.database import AsyncSessionLocal
        from sqlalchemy import text
        import json as _json

        message_obj = {
            "role": "assistant",
            "content": final_response,
            "plan_id": plan_id,
            "deliverables": deliverables,
        }

        async with AsyncSessionLocal() as db:
            await db.execute(
                text("""
                    UPDATE conversations
                    SET messages = messages || :msg::jsonb,
                        updated_at = NOW()
                    WHERE id = :session_id
                """),
                {
                    "msg": _json.dumps([message_obj]),
                    "session_id": session_id,
                },
            )
            await db.commit()
    except Exception as e:
        logger.warning(f"_append_to_conversation: failed (session={session_id}): {e}")


# ── WebSocket notification helpers ─────────────────────────────────────────────

def _send_ws_to_user(user_id: str, session_id: str, response: str, deliverables: list) -> None:
    """
    Send final response to user via Redis pub/sub (cross-worker safe).

    Uses the same Redis channel pattern as process_chat_task:
    publish to user:{user_id}:notifications.
    """
    if not user_id:
        return
    try:
        import redis as _redis_sync
        from app.core.config import get_config
        config = get_config()
        redis_url = config.get("redis", {}).get("url", os.getenv("REDIS_URL", "redis://localhost:6379/0"))
        r = _redis_sync.from_url(redis_url, decode_responses=True)
        payload = json.dumps({
            "type": "task_complete",
            "task_id": f"plan:{session_id}",
            "session_id": session_id or "",
            "message": "Your multi-agent task is ready.",
            "response": response,
            "deliverables": deliverables,
        })
        r.publish(f"user:{user_id}:notifications", payload)
        r.close()
    except Exception as e:
        logger.warning(f"_send_ws_to_user: Redis publish failed (non-fatal): {e}")


def notify_step_start(plan_id: str, step) -> None:
    """Publish a WebSocket progress notification that a step is starting."""
    try:
        plan = plan_manager.load_plan(plan_id)
        _publish_plan_event(plan.user_id, {
            "type": "plan_step_start",
            "plan_id": plan_id,
            "step_id": step.step_id,
            "step_number": step.step_number,
            "agent_id": step.agent_id,
            "description": step.description,
            "message": f"Starting: {step.description} ({step.agent_id})",
        })
    except Exception as e:
        logger.debug(f"notify_step_start: failed (non-fatal): {e}")


def notify_step_complete(plan_id: str, step_id: str, summary: str) -> None:
    """Publish a WebSocket progress notification that a step completed."""
    try:
        plan = plan_manager.load_plan(plan_id)
        step = next((s for s in plan.steps if s.step_id == step_id), None)
        desc = step.description if step else step_id
        _publish_plan_event(plan.user_id, {
            "type": "plan_step_complete",
            "plan_id": plan_id,
            "step_id": step_id,
            "summary": summary[:200],
            "message": f"Completed: {desc} — {summary[:100]}",
        })
    except Exception as e:
        logger.debug(f"notify_step_complete: failed (non-fatal): {e}")


def notify_step_retry(plan_id: str, step_id: str, gaps: list) -> None:
    """Publish a WebSocket progress notification that a step is being retried."""
    try:
        plan = plan_manager.load_plan(plan_id)
        step = next((s for s in plan.steps if s.step_id == step_id), None)
        desc = step.description if step else step_id
        first_gap = gaps[0] if gaps else "quality check failed"
        _publish_plan_event(plan.user_id, {
            "type": "plan_step_retry",
            "plan_id": plan_id,
            "step_id": step_id,
            "gaps": gaps,
            "message": f"Improving: {desc} — {first_gap}",
        })
    except Exception as e:
        logger.debug(f"notify_step_retry: failed (non-fatal): {e}")


def _publish_plan_event(user_id: str, payload: dict) -> None:
    """Publish a plan event to Redis for WebSocket delivery."""
    if not user_id:
        return
    try:
        import redis as _redis_sync
        from app.core.config import get_config
        config = get_config()
        redis_url = config.get("redis", {}).get("url", os.getenv("REDIS_URL", "redis://localhost:6379/0"))
        r = _redis_sync.from_url(redis_url, decode_responses=True)
        r.publish(f"user:{user_id}:notifications", json.dumps(payload))
        r.close()
    except Exception as e:
        logger.debug(f"_publish_plan_event: Redis publish failed (non-fatal): {e}")
