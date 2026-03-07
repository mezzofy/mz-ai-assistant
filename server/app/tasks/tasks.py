"""
Core Celery Tasks — background task definitions for mz-ai-assistant.

Tasks:
    process_agent_task(task_data)  — Run an agent workflow as a background job.
                                     Used for: scheduled reports, long video processing,
                                     batch email outreach, webhook-triggered workflows.
    health_check()                 — Periodic system health check (every 5 minutes).

Celery workers run in separate processes; async agent code is called via asyncio.run().
"""

import asyncio
import logging

from app.tasks.celery_app import celery_app

logger = logging.getLogger("mezzofy.tasks.core")


# ── Main background task ───────────────────────────────────────────────────────

@celery_app.task(bind=True, max_retries=3, name="app.tasks.tasks.process_agent_task")
def process_agent_task(self, task_data: dict):
    """
    Execute an agent workflow as a Celery background task.

    Used for: scheduled reports, long-running agent workflows, batch operations.
    Delivers results via Teams/email/push based on task_data["deliver_to"].

    Args:
        task_data: Standard task dict with keys:
            - agent:       Agent name ("sales", "finance", etc.)
            - message:     Natural language task description
            - deliver_to:  {"teams_channel": "sales", "email": ["ceo@co.com"]}
            - user_id:     (optional) User to notify via WebSocket / push
            - department:  Department context
            - source:      "scheduler" | "webhook" (affects permission bypass)
    """
    try:
        result = asyncio.run(_run_agent_task(task_data))
        logger.info(
            f"process_agent_task completed: agent={task_data.get('agent')!r} "
            f"user={task_data.get('user_id')!r}"
        )
        return result
    except Exception as exc:
        logger.error(f"process_agent_task failed: {exc}", exc_info=True)
        raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))


async def _run_agent_task(task_data: dict) -> dict:
    """Async core for process_agent_task: run agent + deliver results."""
    from app.core.config import get_config
    from app.agents.agent_registry import get_agent_for_task, AGENT_MAP

    config = get_config()
    task_data["_config"] = config

    # Ensure source is set (enables permission bypass for system tasks)
    if not task_data.get("source"):
        task_data["source"] = "scheduler"

    # Fill in defaults if caller didn't set them
    task_data.setdefault("input_type", "text")
    task_data.setdefault("permissions", ["all"])
    task_data.setdefault("attachments", [])
    task_data.setdefault("conversation_history", [])

    # Get agent — try by explicit name first, then auto-detect
    agent_name = task_data.get("agent", "")
    if agent_name and agent_name in AGENT_MAP:
        agent = AGENT_MAP[agent_name](config)
    else:
        agent = get_agent_for_task(task_data, config)

    if agent is None:
        logger.warning(f"No agent found for task (agent={agent_name!r})")
        return {
            "success": False,
            "content": f"Agent {agent_name!r} not available",
            "agent_used": "none",
        }

    # Execute agent — update agent_tasks lifecycle if agent_task_id is present
    agent_task_id = task_data.get("agent_task_id")
    if agent_task_id:
        await _update_agent_task_status(agent_task_id, "running")

    # Inject progress callback so the LLM manager can report step + tool progress
    if agent_task_id:
        import json as _json
        _agent_class_name = type(agent).__name__
        _routing = f"department:{task_data.get('department', 'unknown')}"
        await _update_agent_task_step(
            agent_task_id,
            _json.dumps({
                "agent": _agent_class_name,
                "routing": _routing,
                "tool": None,
                "iteration": 0,
                "max_iterations": 5,
                "description": "Initializing",
            }),
            5,
        )

        async def _progress_callback(tool, iteration, max_iter):
            _progress = min(5 + iteration * 15, 80)
            await _update_agent_task_step(
                agent_task_id,
                _json.dumps({
                    "agent": _agent_class_name,
                    "routing": _routing,
                    "tool": tool,
                    "iteration": iteration,
                    "max_iterations": max_iter,
                    "description": (
                        f"Using tool: {tool}" if tool
                        else f"Thinking (step {iteration}/{max_iter})"
                    ),
                }),
                _progress,
            )

        task_data["_progress_callback"] = _progress_callback

    try:
        result = await agent.execute(task_data)
        if agent_task_id:
            await _update_agent_task_done(agent_task_id, result)
    except Exception as exc:
        if agent_task_id:
            await _update_agent_task_failed(agent_task_id, str(exc))
        raise

    # Store result in scheduled_jobs.last_run if this is a scheduled job
    job_id = task_data.get("_job_id")
    if job_id:
        await _update_job_last_run(job_id)

    # Deliver results if configured
    deliver_to = task_data.get("deliver_to") or {}
    if deliver_to:
        from app.tasks.webhook_tasks import _deliver_results_async
        await _deliver_results_async(result, deliver_to, config)

    return result


@celery_app.task(
    bind=True,
    max_retries=2,
    name="app.tasks.tasks.process_chat_task",
)
def process_chat_task(self, task_data: dict):
    """
    Execute a long-running chat task as a Celery background job.

    Dispatched by POST /chat/send when the message contains long-running keywords.
    On completion: sends push notification + Redis pub/sub WS notification.
    On failure: sends failure push, retries up to 2 times with 10s delay.

    task_data keys:
        user_id, session_id, message, department, agent,
        device_token (optional), platform (optional, default "android")
    """
    task_data["_celery_task_id"] = self.request.id
    try:
        result = asyncio.run(_run_chat_task(task_data))
        logger.info(
            f"process_chat_task completed: user={task_data.get('user_id')!r} "
            f"task_id={self.request.id}"
        )
        return result
    except Exception as exc:
        logger.error(f"process_chat_task failed: {exc}", exc_info=True)
        agent_task_id = task_data.get("agent_task_id")
        try:
            raise self.retry(exc=exc, countdown=10)
        except self.MaxRetriesExceededError:
            if agent_task_id:
                asyncio.run(_update_agent_task_failed(agent_task_id, str(exc)))
            raise


async def _run_chat_task(task_data: dict) -> dict:
    """
    Async core for process_chat_task.

    Flow:
        1. Resolve config + agent
        2. Load/create session, get conversation history
        3. Execute agent
        4. Save result to DB via process_result()
        5. Publish completion to Redis (WebSocket notification)
        6. Send push notification (if device_token present)
    """
    import json
    import os
    from app.core.config import get_config
    from app.agents.agent_registry import get_agent_for_task, AGENT_MAP
    from app.core.database import AsyncSessionLocal
    from app.context.session_manager import get_or_create_session
    from app.context.processor import process_result
    from app.tools.communication.push_ops import send_push

    config = get_config()
    task_data["_config"] = config
    task_data.setdefault("source", "mobile")
    task_data.setdefault("input_type", "text")
    task_data.setdefault("permissions", ["all"])
    task_data.setdefault("attachments", [])
    task_data.setdefault("conversation_history", [])

    user_id = task_data["user_id"]
    session_id = task_data.get("session_id")
    device_token = task_data.get("device_token", "")
    platform = task_data.get("platform", "android")
    celery_task_id = task_data.get("_celery_task_id", "")
    agent_task_id = task_data.get("agent_task_id")

    # Resolve agent
    agent_name = task_data.get("agent", "")
    if agent_name and agent_name in AGENT_MAP:
        agent = AGENT_MAP[agent_name](config)
    else:
        agent = get_agent_for_task(task_data, config)
    if agent is None:
        raise RuntimeError(f"No agent found for task (agent={agent_name!r})")

    # Mark task as running now that Celery worker has picked it up
    if agent_task_id:
        await _update_agent_task_status(agent_task_id, "running")

    # Inject progress callback so the LLM manager can report step + tool progress
    if agent_task_id:
        import json as _json
        _agent_class_name = type(agent).__name__
        _routing = f"department:{task_data.get('department', 'unknown')}"
        await _update_agent_task_step(
            agent_task_id,
            _json.dumps({
                "agent": _agent_class_name,
                "routing": _routing,
                "tool": None,
                "iteration": 0,
                "max_iterations": 5,
                "description": "Initializing",
            }),
            5,
        )

        async def _progress_callback(tool, iteration, max_iter):
            _progress = min(5 + iteration * 15, 80)
            await _update_agent_task_step(
                agent_task_id,
                _json.dumps({
                    "agent": _agent_class_name,
                    "routing": _routing,
                    "tool": tool,
                    "iteration": iteration,
                    "max_iterations": max_iter,
                    "description": (
                        f"Using tool: {tool}" if tool
                        else f"Thinking (step {iteration}/{max_iter})"
                    ),
                }),
                _progress,
            )

        task_data["_progress_callback"] = _progress_callback

    file_url = None
    try:
        async with AsyncSessionLocal() as db:
            # Load or create session and conversation history
            session = await get_or_create_session(
                db, user_id, session_id, task_data.get("department", "")
            )
            task_data["session_id"] = session["id"]
            task_data["conversation_history"] = session["messages"]

            # Write the resolved session_id back to agent_tasks if it was null
            # (first message has no session yet — worker creates it above)
            if agent_task_id and not session_id:
                await _update_agent_task_session(agent_task_id, session["id"])

            # Execute agent
            agent_result = await agent.execute(task_data)

            # Save result to DB (updates existing agent_tasks row to 'completed' if agent_task_id given)
            response = await process_result(
                db=db,
                user_id=user_id,
                session_id=session["id"],
                user_message=task_data["message"],
                agent_result=agent_result,
                input_summary=task_data.get("input_summary", ""),
                department=task_data.get("department", ""),
                agent_task_id=agent_task_id,
            )

        # Extract file_url from artifacts if present
        artifacts = response.get("artifacts", [])
        if artifacts:
            file_url = artifacts[0].get("download_url")

        # Publish to Redis for WebSocket delivery
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        import redis.asyncio as aioredis
        async with aioredis.from_url(redis_url) as redis_client:
            summary = (task_data["message"][:60] + "…") if len(task_data["message"]) > 60 else task_data["message"]
            notification_payload = json.dumps({
                "type": "task_complete",
                "task_id": agent_task_id or celery_task_id,
                "session_id": session["id"],
                "message": summary,
                "file_url": file_url,
            })
            await redis_client.publish(f"user:{user_id}:notifications", notification_payload)

        # Send push notification if device_token is present
        if device_token:
            # Summarize to ≤10 words for push body
            words = task_data["message"].split()
            push_body = " ".join(words[:10]) + ("…" if len(words) > 10 else "")
            push_data = {"session_id": session["id"], "file_url": file_url or ""}
            await send_push(
                user_id=user_id,
                device_token=device_token,
                platform=platform,
                title="Your task is ready",
                body=push_body,
                data=push_data,
            )

        return response

    except Exception as exc:
        # Send failure push if device_token is available; then re-raise for Celery retry
        if device_token:
            try:
                await send_push(
                    user_id=user_id,
                    device_token=device_token,
                    platform=platform,
                    title="Task failed",
                    body="Something went wrong. Please try again.",
                )
            except Exception:
                pass  # Don't let push failure block the retry
        raise


async def _update_job_last_run(job_id: str):
    """Update scheduled_jobs.last_run timestamp after successful execution."""
    try:
        from app.core.database import AsyncSessionLocal
        from sqlalchemy import text

        async with AsyncSessionLocal() as db:
            await db.execute(
                text("UPDATE scheduled_jobs SET last_run = NOW() WHERE id = :id"),
                {"id": job_id},
            )
            await db.commit()
    except Exception as e:
        logger.warning(f"Failed to update job last_run (id={job_id}): {e}")


async def _update_agent_task_status(agent_task_id: str, new_status: str):
    """Mark an agent_tasks row as running."""
    try:
        from app.core.database import AsyncSessionLocal
        from sqlalchemy import text

        async with AsyncSessionLocal() as db:
            await db.execute(
                text(
                    "UPDATE agent_tasks SET status = :status, started_at = NOW() "
                    "WHERE id = :id"
                ),
                {"status": new_status, "id": agent_task_id},
            )
            await db.commit()
    except Exception as e:
        logger.warning(f"Failed to update agent_task status (id={agent_task_id}): {e}")


async def _update_agent_task_done(agent_task_id: str, result: dict):
    """Mark an agent_tasks row as completed with its result."""
    try:
        import json
        from app.core.database import AsyncSessionLocal
        from sqlalchemy import text

        async with AsyncSessionLocal() as db:
            await db.execute(
                text(
                    "UPDATE agent_tasks "
                    "SET status = 'completed', completed_at = NOW(), result = :result, "
                    "progress = 100, current_step = NULL "
                    "WHERE id = :id"
                ),
                {"result": json.dumps(result), "id": agent_task_id},
            )
            await db.commit()
    except Exception as e:
        logger.warning(f"Failed to update agent_task done (id={agent_task_id}): {e}")


async def _update_agent_task_failed(agent_task_id: str, error_msg: str):
    """Mark an agent_tasks row as failed with the error message."""
    try:
        from app.core.database import AsyncSessionLocal
        from sqlalchemy import text

        async with AsyncSessionLocal() as db:
            await db.execute(
                text(
                    "UPDATE agent_tasks "
                    "SET status = 'failed', completed_at = NOW(), error = :error "
                    "WHERE id = :id"
                ),
                {"error": error_msg, "id": agent_task_id},
            )
            await db.commit()
    except Exception as e:
        logger.warning(f"Failed to update agent_task failed (id={agent_task_id}): {e}")


async def _update_agent_task_session(agent_task_id: str, session_id: str):
    """Write the resolved session_id back to agent_tasks after session creation."""
    try:
        from app.core.database import AsyncSessionLocal
        from sqlalchemy import text

        async with AsyncSessionLocal() as db:
            await db.execute(
                text("UPDATE agent_tasks SET session_id = :session_id WHERE id = :id"),
                {"session_id": session_id, "id": agent_task_id},
            )
            await db.commit()
    except Exception as e:
        logger.warning(f"Failed to update agent_task session_id (id={agent_task_id}): {e}")


async def _update_agent_task_step(agent_task_id: str, step_json: str, progress: int):
    """Update current_step and progress for an in-flight agent task."""
    try:
        from app.core.database import AsyncSessionLocal
        from sqlalchemy import text

        async with AsyncSessionLocal() as db:
            await db.execute(
                text(
                    "UPDATE agent_tasks "
                    "SET current_step = :step, progress = :progress "
                    "WHERE id = :id"
                ),
                {"step": step_json, "progress": progress, "id": agent_task_id},
            )
            await db.commit()
    except Exception as e:
        logger.warning(f"Failed to update agent_task step (id={agent_task_id}): {e}")


# ── Health check task ──────────────────────────────────────────────────────────

@celery_app.task(name="app.tasks.tasks.health_check")
def health_check():
    """
    Periodic system health check task — runs every 5 minutes via Celery Beat.

    Checks: PostgreSQL, Redis connectivity, LLM manager status.
    Logs results; does NOT raise exceptions (task must succeed to be rescheduled).
    """
    results = {}

    # PostgreSQL
    try:
        asyncio.run(_check_db())
        results["database"] = "ok"
    except Exception as e:
        results["database"] = f"FAIL: {e}"
        logger.error(f"Health check DB failed: {e}")

    # Redis (via celery backend — already connected if this task ran)
    results["celery_worker"] = "ok"

    # LLM manager
    try:
        from app.llm import llm_manager as llm_mod
        llm_mod.get()
        results["llm_manager"] = "ok"
    except Exception as e:
        results["llm_manager"] = f"not_initialized: {e}"
        logger.warning(f"Health check LLM: {e}")

    status = "ok" if all(v == "ok" for v in results.values()) else "degraded"
    logger.info(f"System health: {status} — {results}")
    return {"status": status, "services": results}


async def _check_db():
    """Async DB ping used by health_check."""
    from app.core.database import check_db_connection
    ok = await check_db_connection()
    if not ok:
        raise RuntimeError("DB connection check failed")
