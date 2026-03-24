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
import os
from typing import Optional

from app.tasks.celery_app import celery_app
from celery.signals import worker_process_init, worker_ready

logger = logging.getLogger("mezzofy.tasks.core")


# ── Per-worker-process init (fires in each forked child after fork) ────────────

@worker_process_init.connect
def init_worker_process(**kwargs):
    """
    Initialize singletons in each forked Celery worker process.

    worker_process_init fires inside the child process after fork, so globals
    set here are visible to all tasks running in that child.  worker_ready
    fires in the main process only — changes there are NOT inherited by children.
    """
    from app.core.config import load_config
    config = load_config()

    # Dispose the inherited SQLAlchemy async connection pool.
    # After fork the child inherits the parent's pool connections which are
    # bound to the parent's (now-closed) event loop → "Future attached to a
    # different loop" errors.  dispose() discards those connections so the
    # child creates fresh ones on first use.
    try:
        from app.core.database import engine
        engine.sync_engine.dispose()
        logger.info(f"DB engine pool disposed in worker pid={os.getpid()}")
    except Exception as e:
        logger.warning(f"engine.dispose() in worker init failed (non-fatal): {e}")

    try:
        from app.llm import llm_manager as llm_mod
        llm_mod.init(config)
        logger.info(f"LLMManager initialized in worker pid={os.getpid()}")
    except Exception as e:
        logger.error(f"LLMManager init failed in worker pid={os.getpid()}: {e}")

    try:
        from app.skills import skill_registry as sr_mod
        sr_mod.init(config)
        logger.info(f"Skill registry initialized in worker pid={os.getpid()}")
    except Exception as e:
        logger.error(f"Skill registry init failed in worker pid={os.getpid()}: {e}")


# ── Stale task recovery on worker startup (main process, runs once) ────────────

@worker_ready.connect
def on_worker_ready(**kwargs):
    """Mark abandoned 'running' tasks as failed when the worker (re)starts."""
    # Dispose the engine pool so _recover_stale_tasks() opens fresh connections
    # in its own event loop (avoids "Future attached to a different loop" errors).
    try:
        from app.core.database import engine
        engine.sync_engine.dispose()
    except Exception:
        pass
    try:
        asyncio.run(_recover_stale_tasks())
    except Exception as e:
        logger.error(f"recover_stale_tasks failed: {e}")


async def _recover_stale_tasks():
    """Update agent_tasks rows stuck in 'running' for >15 minutes to 'failed'."""
    from app.core.database import AsyncSessionLocal
    from sqlalchemy import text

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            text(
                """
                UPDATE agent_tasks
                SET status = 'failed',
                    completed_at = NOW(),
                    error = 'Task interrupted due to worker restart'
                WHERE status = 'running'
                  AND started_at < NOW() - INTERVAL '15 minutes'
                RETURNING id, task_ref
                """
            )
        )
        await db.commit()
        rows = result.fetchall()
        if rows:
            refs = [r.task_ref for r in rows]
            logger.info(f"Recovered {len(rows)} stale task(s) on startup: {refs}")


# ── Periodic hung-task cleanup ─────────────────────────────────────────────────

@celery_app.task(name="app.tasks.tasks.cleanup_stuck_tasks")
def cleanup_stuck_tasks():
    """Periodic cleanup: mark tasks stuck in 'running' for >1 hour as failed."""
    try:
        from app.core.database import engine
        engine.sync_engine.dispose()
    except Exception:
        pass
    asyncio.run(_cleanup_stuck_tasks_async())


async def _cleanup_stuck_tasks_async():
    """UPDATE agent_tasks: running AND started_at < NOW() - 1 hour → failed."""
    from app.core.database import AsyncSessionLocal
    from sqlalchemy import text

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            text(
                "UPDATE agent_tasks "
                "SET status = 'failed', "
                "    completed_at = NOW(), "
                "    error = 'Task timed out: exceeded 1-hour execution limit' "
                "WHERE status = 'running' "
                "  AND started_at < NOW() - INTERVAL '1 hour' "
                "RETURNING id, task_ref"
            )
        )
        rows = result.fetchall()
        await db.commit()

    if rows:
        refs = [r.task_ref for r in rows]
        logger.warning(
            f"cleanup_stuck_tasks: marked {len(rows)} hung task(s) as failed — refs: {refs}"
        )
    else:
        logger.debug("cleanup_stuck_tasks: no stuck tasks found")


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
        try:
            from app.core.database import engine
            engine.sync_engine.dispose()
        except Exception:
            pass
        result = asyncio.run(_run_agent_task(task_data))
        logger.info(
            f"process_agent_task completed: agent={task_data.get('agent')!r} "
            f"user={task_data.get('user_id')!r}"
        )
        return result
    except Exception as exc:
        logger.error(f"process_agent_task failed: {exc}", exc_info=True)
        raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))


async def _fetch_user_context(user_id: str) -> tuple:
    """
    Fetch (email, role) for the given user_id from the users table.

    Returns ("", "user") when user_id is empty or the lookup fails.
    Called by Celery task functions to restore user context that is lost
    when tasks cross the process boundary (ContextVars are not propagated).
    """
    if not user_id:
        return ("", "user")
    try:
        from app.core.database import AsyncSessionLocal
        from sqlalchemy import text
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                text("SELECT email, role FROM users WHERE id = :uid"),
                {"uid": user_id},
            )
            row = result.fetchone()
            if row:
                return (row.email or "", row.role or "user")
    except Exception as e:
        logger.warning(f"_fetch_user_context failed for user_id={user_id!r}: {e}")
    return ("", "user")


async def _run_agent_task(task_data: dict) -> dict:
    """Async core for process_agent_task: run agent + deliver results."""
    from app.core.config import get_config
    from app.agents.agent_registry import get_agent_for_task, AGENT_MAP

    config = get_config()
    task_data["_config"] = config

    # Restore user context — ContextVars are not propagated across the Celery
    # process boundary, so get_user_dept() / get_user_email() return defaults
    # ("general" / "") inside Celery workers without this call.
    from app.core.user_context import set_user_context
    _dept = task_data.get("department", "general")
    _uid = task_data.get("user_id", "")
    _email, _role = await _fetch_user_context(_uid)
    set_user_context(dept=_dept, email=_email, role=_role, user_id=_uid)

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

    # Push notification for scheduled job completion
    _uid_push = task_data.get("user_id", "")
    if _uid_push and _uid_push != "system":
        try:
            from app.tools.communication.push_ops import get_user_push_targets, send_push as _send_push
            _targets = await get_user_push_targets(_uid_push)
            if _targets:
                _job_name = (task_data.get("workflow_name")
                             or task_data.get("_job_name")
                             or task_data.get("message", "")[:40])
                _short_id = (job_id or "")[:8].upper() or "TASK"
                for _t in _targets:
                    await _send_push(
                        user_id=_uid_push,
                        device_token=_t["device_token"],
                        platform=_t["platform"],
                        title="Scheduled Task Completed",
                        body=f"Task ID: {_short_id} · {_job_name}",
                        data={"type": "job_complete", "job_id": job_id or "",
                              "job_name": _job_name},
                    )
        except Exception as _e:
            logger.warning(f"Push notification failed for scheduled job: {_e}")

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
        try:
            from app.core.database import engine
            engine.sync_engine.dispose()
        except Exception as _e:
            logger.warning(f"process_chat_task engine.dispose() failed (non-fatal): {_e}")
        result = asyncio.run(_run_chat_task(task_data))
        logger.info(
            f"process_chat_task completed: user={task_data.get('user_id')!r} "
            f"task_id={self.request.id}"
        )
        return result
    except Exception as exc:
        logger.error(f"process_chat_task failed: {exc}", exc_info=True)
        agent_task_id = task_data.get("agent_task_id")
        # Soft time limit — mark failed immediately, do NOT retry
        from celery.exceptions import SoftTimeLimitExceeded
        if isinstance(exc, SoftTimeLimitExceeded):
            logger.warning(f"process_chat_task soft time limit exceeded: {agent_task_id}")
            if agent_task_id:
                # Dispose pool so the new asyncio.run() opens fresh connections
                # (avoids "Future attached to a different loop" from the closed loop)
                try:
                    from app.core.database import engine
                    engine.sync_engine.dispose()
                except Exception:
                    pass
                asyncio.run(_update_agent_task_failed(
                    agent_task_id, "Task exceeded time limit (9 minutes)"
                ))
            raise
        # Strip worker-injected non-serializable keys before Celery re-enqueues the retry
        for _key in ("_progress_callback", "_config", "_celery_task_id"):
            task_data.pop(_key, None)
        try:
            raise self.retry(exc=exc, countdown=10)
        except self.MaxRetriesExceededError:
            if agent_task_id:
                # Dispose pool so the new asyncio.run() opens fresh connections
                try:
                    from app.core.database import engine
                    engine.sync_engine.dispose()
                except Exception:
                    pass
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

    config = get_config()
    task_data["_config"] = config
    task_data.setdefault("source", "mobile")
    task_data.setdefault("input_type", "text")
    task_data.setdefault("permissions", ["all"])
    task_data.setdefault("attachments", [])
    task_data.setdefault("conversation_history", [])

    # Restore user context — ContextVars are not propagated across the Celery
    # process boundary, so get_user_dept() / get_user_email() return defaults
    # ("general" / "") inside Celery workers without this call.
    from app.core.user_context import set_user_context
    _dept = task_data.get("department", "general")
    _uid_ctx = task_data.get("user_id", "")
    _email_ctx, _role_ctx = await _fetch_user_context(_uid_ctx)
    set_user_context(dept=_dept, email=_email_ctx, role=_role_ctx, user_id=_uid_ctx)

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
            # Commit all writes: conversation history, artifacts, agent_task status.
            # Without this commit the session closes and rolls back every write above
            # (autocommit=False), leaving the agent_task stuck in 'running' forever.
            await db.commit()

        # Extract file_url from artifacts if present
        artifacts = response.get("artifacts", [])
        if artifacts:
            file_url = artifacts[0].get("download_url")

        # Publish to Redis for WebSocket delivery
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        import redis.asyncio as aioredis
        async with aioredis.from_url(redis_url) as redis_client:
            summary = (task_data["message"][:60] + "…") if len(task_data["message"]) > 60 else task_data["message"]
            full_response = response.get("response", "")
            notification_payload = json.dumps({
                "type": "task_complete",
                "task_id": agent_task_id or celery_task_id,
                "session_id": str(session["id"]),
                "message": summary,
                "response": full_response,
                "file_url": file_url,
            })
            await redis_client.publish(f"user:{user_id}:notifications", notification_payload)

        # Push via DB-registered tokens (replaces per-request device_token approach)
        try:
            from app.tools.communication.push_ops import get_user_push_targets, send_push as _send_push
            _targets = await get_user_push_targets(user_id)
            if _targets:
                _summary = task_data["message"][:60] + ("…" if len(task_data["message"]) > 60 else "")
                _short_id = (agent_task_id or celery_task_id or "")[:8].upper() or "TASK"
                _push_data = {
                    "type": "task_complete",
                    "task_id": agent_task_id or celery_task_id or "",
                    "session_id": str(session["id"]),
                    "file_url": file_url or "",
                }
                for _t in _targets:
                    await _send_push(
                        user_id=user_id, device_token=_t["device_token"],
                        platform=_t["platform"],
                        title="Task Ready",
                        body=f"Task ID: {_short_id} · {_summary}",
                        data=_push_data,
                    )
        except Exception as _e:
            logger.warning(f"Push notification failed for chat task: {_e}")

        return response

    except Exception as exc:
        try:
            from app.tools.communication.push_ops import get_user_push_targets, send_push as _send_push
            for _t in await get_user_push_targets(user_id):
                await _send_push(
                    user_id=user_id, device_token=_t["device_token"],
                    platform=_t["platform"], title="Task Failed",
                    body="Something went wrong. Please try again.",
                )
        except Exception:
            pass
        raise


async def _update_job_last_run(job_id: str):
    """Update scheduled_jobs.last_run and next_run after successful execution."""
    try:
        from app.core.database import AsyncSessionLocal
        from app.webhooks.scheduler import compute_next_run
        from sqlalchemy import text

        async with AsyncSessionLocal() as db:
            # Fetch the job's cron expression so we can recompute next_run
            result = await db.execute(
                text("SELECT schedule FROM scheduled_jobs WHERE id = :id"),
                {"id": job_id},
            )
            row = result.fetchone()
            if row is None:
                logger.warning(f"Job not found when updating last_run (id={job_id})")
                return
            next_run = compute_next_run(row.schedule)
            await db.execute(
                text(
                    "UPDATE scheduled_jobs SET last_run = NOW(), next_run = :next_run"
                    " WHERE id = :id"
                ),
                {"id": job_id, "next_run": next_run},
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
            # Fetch department + content for the Redis publish
            row = await db.execute(
                text("SELECT department, content FROM agent_tasks WHERE id = :id"),
                {"id": agent_task_id},
            )
            task_row = row.fetchone()
            await db.commit()

        # Publish running status to admin agent-office channel
        try:
            import json as _json
            import redis.asyncio as _aioredis
            _redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
            async with _aioredis.from_url(_redis_url) as _rc:
                await _rc.publish("admin:agent-status", _json.dumps({
                    "type": "agent_status",
                    "department": task_row.department if task_row else "",
                    "status": new_status,
                    "task_title": task_row.content if task_row else "",
                    "agent_task_id": agent_task_id,
                }))
        except Exception as _pub_err:
            logger.warning(f"admin agent-status publish failed in _update_agent_task_status (non-fatal): {_pub_err}")
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
            row = await db.execute(
                text("SELECT department, content FROM agent_tasks WHERE id = :id"),
                {"id": agent_task_id},
            )
            task_row = row.fetchone()
            await db.commit()

        # Publish completed status to admin agent-office channel
        try:
            import redis.asyncio as _aioredis
            _redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
            async with _aioredis.from_url(_redis_url) as _rc:
                await _rc.publish("admin:agent-status", json.dumps({
                    "type": "agent_status",
                    "department": task_row.department if task_row else "",
                    "status": "completed",
                    "task_title": task_row.content if task_row else "",
                    "agent_task_id": agent_task_id,
                }))
        except Exception as _pub_err:
            logger.warning(f"admin agent-status publish failed in _update_agent_task_done (non-fatal): {_pub_err}")
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
            row = await db.execute(
                text("SELECT department, content FROM agent_tasks WHERE id = :id"),
                {"id": agent_task_id},
            )
            task_row = row.fetchone()
            await db.commit()

        # Publish failed status to admin agent-office channel
        try:
            import json as _json
            import redis.asyncio as _aioredis
            _redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
            async with _aioredis.from_url(_redis_url) as _rc:
                await _rc.publish("admin:agent-status", _json.dumps({
                    "type": "agent_status",
                    "department": task_row.department if task_row else "",
                    "status": "failed",
                    "task_title": task_row.content if task_row else "",
                    "agent_task_id": agent_task_id,
                }))
        except Exception as _pub_err:
            logger.warning(f"admin agent-status publish failed in _update_agent_task_failed (non-fatal): {_pub_err}")
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


# ── v2.0: Inter-agent delegation ──────────────────────────────────────────────

# Maps agent_id strings to Python agent classes.
# Used by process_delegated_agent_task and get_agent_by_id().
_AGENT_ID_MAP: dict | None = None  # lazy-initialized


def get_agent_by_id(agent_id: str):
    """
    Map an agent_id string to an instantiated Python agent class.

    AGENT_ID_MAP covers all 10 agents (6 department + 4 special-purpose).
    Raises ValueError if agent_id is not in the map.
    """
    global _AGENT_ID_MAP
    if _AGENT_ID_MAP is None:
        from app.agents.finance_agent import FinanceAgent
        from app.agents.sales_agent import SalesAgent
        from app.agents.marketing_agent import MarketingAgent
        from app.agents.support_agent import SupportAgent
        from app.agents.hr_agent import HRAgent
        from app.agents.management_agent import ManagementAgent
        from app.agents.research_agent import ResearchAgent
        from app.agents.developer_agent import DeveloperAgent
        from app.agents.scheduler_agent import SchedulerAgent
        from app.agents.legal_agent import LegalAgent
        from app.core.config import get_config
        _config = get_config()
        _AGENT_ID_MAP = {
            "agent_finance": FinanceAgent(_config),
            "agent_sales": SalesAgent(_config),
            "agent_marketing": MarketingAgent(_config),
            "agent_support": SupportAgent(_config),
            "agent_hr": HRAgent(_config),
            "agent_management": ManagementAgent(_config),
            "agent_research": ResearchAgent(_config),
            "agent_developer": DeveloperAgent(_config),
            "agent_scheduler": SchedulerAgent(_config),
            "agent_legal": LegalAgent(_config),
        }
    if agent_id not in _AGENT_ID_MAP:
        raise ValueError(
            f"get_agent_by_id: unknown agent_id {agent_id!r}. "
            f"Valid ids: {list(_AGENT_ID_MAP.keys())}"
        )
    return _AGENT_ID_MAP[agent_id]


@celery_app.task(
    bind=True,
    max_retries=3,
    name="app.tasks.tasks.process_delegated_agent_task",
)
def process_delegated_agent_task(
    self,
    task_data: dict,
    agent_id: str,
    parent_task_id: str,
    requested_by_agent_id: str,
):
    """
    Execute a sub-task delegated by another agent (typically ManagementAgent).

    Same mechanics as process_agent_task but:
    - Resolves agent by agent_id (not department)
    - Updates agent_task_log with parent_task_id and requested_by_agent_id
    - On completion: publishes result to Redis pub/sub channel
      key = "agent_result:{parent_task_id}" so await_delegation() can pick it up
    - On failure: retries up to 3 times (30s, 60s, 90s), then logs failed status

    Args:
        task_data:              Standard task dict (same shape as process_agent_task).
        agent_id:               Target agent id string (e.g. "agent_finance").
        parent_task_id:         UUID of the parent agent_task_log row.
        requested_by_agent_id:  ID of the agent that delegated this task.
    """
    # Dispose engine pool (same Celery async pattern as all other tasks)
    try:
        from app.core.database import engine
        engine.sync_engine.dispose()
    except Exception:
        pass

    # Inject delegation context so log_task_start() records the chain
    task_data["_requesting_agent_id"] = requested_by_agent_id
    task_data["_parent_task_id"] = parent_task_id
    task_data["source"] = task_data.get("source", "agent_delegation")

    # agent_task_log row id from delegate_task() (may be pre-inserted as 'queued')
    log_id = task_data.get("_agent_task_log_id", "")

    try:
        result = asyncio.run(
            _run_delegated_agent_task(task_data, agent_id, parent_task_id, log_id)
        )
        logger.info(
            f"process_delegated_agent_task completed: "
            f"agent={agent_id!r} parent={parent_task_id!r}"
        )
        return result
    except Exception as exc:
        logger.error(
            f"process_delegated_agent_task failed: agent={agent_id!r} error={exc}",
            exc_info=True,
        )
        # Update log row to failed before retrying
        try:
            asyncio.run(_update_delegated_task_log(log_id, "failed", error=str(exc)))
        except Exception:
            pass
        raise self.retry(exc=exc, countdown=30 * (self.request.retries + 1))


async def _run_delegated_agent_task(
    task_data: dict,
    agent_id: str,
    parent_task_id: str,
    log_id: str,
) -> dict:
    """Async core for process_delegated_agent_task."""
    import json as _json
    from app.core.config import get_config
    config = get_config()
    task_data["_config"] = config
    # Gap 3 fix: honour the originating user's permissions rather than granting
    # blanket ["all"] to every delegated sub-task. Scheduler/webhook tasks that
    # arrive without an explicit permissions list keep ["all"] (system-level ops).
    source = task_data.get("source", "")
    if "permissions" not in task_data or not task_data.get("permissions"):
        if source in ("scheduler", "webhook"):
            task_data["permissions"] = ["all"]
        else:
            task_data["permissions"] = []  # deny-by-default for user-originated tasks
    task_data.setdefault("attachments", [])
    task_data.setdefault("conversation_history", [])

    # ── v2.5: Uniform agent interface — extract orchestrator contract fields ──
    plan_id = task_data.get("_plan_id", "")
    step_id = task_data.get("_step_id", "")
    context = task_data.get("_context", {})       # prior step outputs (dict)
    instructions = task_data.get("_instructions", "")
    feedback = task_data.get("_feedback", "")     # retry feedback from orchestrator

    # Prepend context block if provided
    if context and isinstance(context, dict):
        context_block = f"Context from prior steps:\n{_json.dumps(context, indent=2)}\n\n"
        task_data["message"] = context_block + task_data.get("message", "")

    # Prepend step-specific instructions if provided
    if instructions:
        task_data["message"] = f"[Instructions]: {instructions}\n\n" + task_data.get("message", "")

    # Prepend retry feedback if provided
    if feedback:
        task_data["message"] = f"[Feedback from prior attempt]: {feedback}\n\n" + task_data.get("message", "")

    # Restore user context
    from app.core.user_context import set_user_context
    _uid = task_data.get("user_id", "")
    _dept = task_data.get("department", "general")
    _email, _role = await _fetch_user_context(_uid)
    set_user_context(dept=_dept, email=_email, role=_role, user_id=_uid)

    # Update log: running
    await _update_delegated_task_log(log_id, "running")

    # Resolve the agent instance
    agent = get_agent_by_id(agent_id)
    import time
    start_time = time.time()

    try:
        result = await agent.execute(task_data)
        duration_ms = int((time.time() - start_time) * 1000)

        # Update log: completed
        await _update_delegated_task_log(
            log_id, "completed",
            result_summary=result.get("content", "")[:2000],
            duration_ms=duration_ms,
        )

        # Publish result to Redis so await_delegation() polling can pick it up
        if parent_task_id:
            try:
                import redis.asyncio as aioredis
                from app.core.config import get_config as _gc
                _cfg = _gc()
                _redis_url = _cfg.get("redis", {}).get("url", "redis://localhost:6379/0")
                _redis = aioredis.from_url(_redis_url)
                await _redis.publish(
                    f"agent_result:{parent_task_id}",
                    _json.dumps({
                        "task_id": log_id,
                        "agent_id": agent_id,
                        "status": "completed",
                        "result_summary": result.get("content", "")[:2000],
                    }),
                )
                await _redis.aclose()
            except Exception as redis_err:
                logger.debug(f"Redis pub/sub publish failed (non-fatal): {redis_err}")

        # ── v2.5: Normalise output to uniform contract ────────────────────────
        normalised = _normalise_agent_output(result)

        # ── v2.5: Notify orchestrator if this task is part of a plan ─────────
        if plan_id and step_id:
            try:
                from app.tasks.orchestrator_tasks import handle_step_completion
                handle_step_completion.delay(plan_id, step_id, normalised)
            except Exception as _oc_err:
                logger.warning(f"handle_step_completion.delay failed (non-fatal): {_oc_err}")

        return result
    except Exception as exc:
        duration_ms = int((time.time() - start_time) * 1000)
        await _update_delegated_task_log(
            log_id, "failed", error=str(exc), duration_ms=duration_ms
        )
        raise


def _normalise_agent_output(result: dict, quality_estimate: float = 0.8) -> dict:
    """Wrap agent result in the uniform output contract used by the orchestrator."""
    return {
        "status": "completed" if result.get("success") else "failed",
        "result": result,
        "summary": result.get("content", "")[:500],
        "deliverable": _extract_deliverable(result.get("artifacts", [])),
        "quality_score": quality_estimate,
        "issues": [] if result.get("success") else [result.get("content", "error")],
    }


def _extract_deliverable(artifacts: list) -> Optional[dict]:
    """Return the first artifact dict from the artifacts list, or None."""
    if not artifacts or not isinstance(artifacts, list):
        return None
    first = artifacts[0] if artifacts else None
    if isinstance(first, dict):
        return first
    return None


async def _update_delegated_task_log(
    log_id: str,
    status: str,
    result_summary: str = "",
    error: str = "",
    duration_ms: int = 0,
) -> None:
    """Update an agent_task_log row for a delegated sub-task."""
    if not log_id:
        return
    try:
        from app.core.database import AsyncSessionLocal
        from sqlalchemy import text
        updates = {"status": status, "id": log_id}
        set_clauses = ["status = :status"]
        if status == "running":
            set_clauses.append("started_at = NOW()")
        if status in ("completed", "failed"):
            set_clauses.append("completed_at = NOW()")
        if result_summary:
            set_clauses.append("result_summary = :result_summary")
            updates["result_summary"] = result_summary
        if error:
            set_clauses.append("error_message = :error")
            updates["error"] = error
        if duration_ms:
            set_clauses.append("duration_ms = :duration_ms")
            updates["duration_ms"] = duration_ms

        async with AsyncSessionLocal() as db:
            await db.execute(
                text(f"UPDATE agent_task_log SET {', '.join(set_clauses)} WHERE id = :id"),
                updates,
            )
            await db.commit()
    except Exception as e:
        logger.warning(f"_update_delegated_task_log failed (log_id={log_id!r}): {e}")


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
        try:
            from app.core.database import engine
            engine.sync_engine.dispose()
        except Exception:
            pass
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
