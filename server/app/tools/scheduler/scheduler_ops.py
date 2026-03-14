"""
SchedulerOps — LLM-callable tools for scheduled job CRUD.

Exposes create / list / delete / run_now as tool methods so the
SchedulerAgent can call them via the standard ToolExecutor flow.

Uses the same raw-SQL pattern as app/webhooks/scheduler.py.
Gets user_id from user_context.get_user_id() (set per-request by router.py).
"""

import json
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import text

from app.tools.base_tool import BaseTool

logger = logging.getLogger("mezzofy.tools.scheduler")

_VALID_AGENTS = {"sales", "marketing", "finance", "support", "management"}
_MAX_JOBS_PER_USER = 10


class SchedulerOps(BaseTool):
    """Tool collection for scheduled job management (chat-based)."""

    def get_tools(self) -> list[dict]:
        return [
            {
                "name": "create_scheduled_job",
                "description": (
                    "Create a new scheduled job that runs an AI agent on a recurring schedule. "
                    "The agent will automatically generate a report or perform a task at the "
                    "specified cron time. "
                    "Valid agents: sales, marketing, finance, support, management. "
                    "Cron format: 5 fields — minute hour day-of-month month day-of-week. "
                    "Server runs UTC — 9AM SGT = cron '0 1 * * *'. "
                    "Minimum interval: 15 minutes. Maximum 10 active jobs per user."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Short descriptive name for the job (max 100 chars)",
                        },
                        "agent": {
                            "type": "string",
                            "enum": ["sales", "marketing", "finance", "support", "management"],
                            "description": "Which AI agent will run the job",
                        },
                        "message": {
                            "type": "string",
                            "description": "The prompt/instruction the agent will receive each run",
                        },
                        "cron": {
                            "type": "string",
                            "description": (
                                "5-field cron expression in UTC "
                                "(e.g. '0 1 * * *' for 9AM SGT daily)"
                            ),
                        },
                        "deliver_to_channel": {
                            "type": "string",
                            "description": (
                                "Optional: Teams channel name to post results to. "
                                "Leave empty if no delivery needed."
                            ),
                        },
                    },
                    "required": ["name", "agent", "message", "cron"],
                },
                "handler": self._create_scheduled_job,
            },
            {
                "name": "list_scheduled_jobs",
                "description": "List all active scheduled jobs for the current user.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
                "handler": self._list_scheduled_jobs,
            },
            {
                "name": "delete_scheduled_job",
                "description": (
                    "Deactivate a scheduled job by ID. "
                    "The user can only delete their own jobs."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "job_id": {
                            "type": "string",
                            "description": "The UUID of the job to delete",
                        },
                    },
                    "required": ["job_id"],
                },
                "handler": self._delete_scheduled_job,
            },
            {
                "name": "run_job_now",
                "description": (
                    "Immediately trigger a scheduled job, running it once right now "
                    "in addition to its normal schedule."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "job_id": {
                            "type": "string",
                            "description": "The UUID of the job to trigger immediately",
                        },
                    },
                    "required": ["job_id"],
                },
                "handler": self._run_job_now,
            },
        ]

    # ── Handlers ──────────────────────────────────────────────────────────────

    async def _create_scheduled_job(
        self,
        name: str,
        agent: str,
        message: str,
        cron: str,
        deliver_to_channel: str = "",
    ) -> dict:
        from app.core.user_context import get_user_id
        from app.core.database import AsyncSessionLocal

        user_id = get_user_id()
        if not user_id:
            return self._err("Could not determine current user. Please log in again.")

        if agent not in _VALID_AGENTS:
            return self._err(
                f"Invalid agent '{agent}'. Must be one of: {', '.join(sorted(_VALID_AGENTS))}"
            )

        name = name.strip()
        if not name or len(name) > 100:
            return self._err("Job name must be 1–100 characters.")

        message = message.strip()
        if not message or len(message) > 2000:
            return self._err("Message must be 1–2000 characters.")

        cron = cron.strip()
        if len(cron.split()) != 5:
            return self._err(
                "Invalid cron expression. Must have exactly 5 fields: "
                "minute hour day-of-month month day-of-week"
            )

        deliver_to = {}
        if deliver_to_channel and deliver_to_channel.strip():
            deliver_to["teams_channel"] = deliver_to_channel.strip()

        job_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        async with AsyncSessionLocal() as db:
            # Enforce job limit
            count_result = await db.execute(
                text(
                    "SELECT COUNT(*) FROM scheduled_jobs "
                    "WHERE user_id = :uid AND is_active = TRUE"
                ),
                {"uid": user_id},
            )
            active_count = count_result.scalar() or 0
            if active_count >= _MAX_JOBS_PER_USER:
                return self._err(
                    f"You already have {_MAX_JOBS_PER_USER} active scheduled jobs "
                    "(the maximum). Please delete one before creating another."
                )

            await db.execute(
                text(
                    "INSERT INTO scheduled_jobs "
                    "(id, user_id, name, agent, message, schedule, deliver_to, is_active, created_at) "
                    "VALUES (:id, :uid, :name, :agent, :message, :schedule, :deliver_to, TRUE, :now)"
                ),
                {
                    "id": job_id,
                    "uid": user_id,
                    "name": name,
                    "agent": agent,
                    "message": message,
                    "schedule": cron,
                    "deliver_to": json.dumps(deliver_to),
                    "now": now,
                },
            )
            await db.commit()

        logger.info(
            f"SchedulerOps: user {user_id} created job {job_id} "
            f"(name={name!r}, agent={agent}, cron={cron!r})"
        )
        return self._ok({
            "job_id": job_id,
            "name": name,
            "agent": agent,
            "schedule": cron,
            "message": (
                f"Scheduled job **{name}** created successfully. "
                f"It will run the {agent} agent on schedule: `{cron}` (UTC)."
            ),
        })

    async def _list_scheduled_jobs(self) -> dict:
        from app.core.user_context import get_user_id
        from app.core.database import AsyncSessionLocal

        user_id = get_user_id()
        if not user_id:
            return self._err("Could not determine current user. Please log in again.")

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                text(
                    "SELECT id, name, agent, schedule, is_active, last_run, next_run "
                    "FROM scheduled_jobs "
                    "WHERE user_id = :uid AND is_active = TRUE "
                    "ORDER BY created_at DESC"
                ),
                {"uid": user_id},
            )
            rows = result.fetchall()

        if not rows:
            return self._ok({"jobs": [], "message": "You have no active scheduled jobs."})

        jobs = [
            {
                "id": str(row.id),
                "name": row.name,
                "agent": row.agent,
                "schedule": row.schedule,
                "last_run": row.last_run.isoformat() if row.last_run else None,
                "next_run": row.next_run.isoformat() if row.next_run else None,
            }
            for row in rows
        ]
        return self._ok({"jobs": jobs, "count": len(jobs)})

    async def _delete_scheduled_job(self, job_id: str) -> dict:
        from app.core.user_context import get_user_id
        from app.core.database import AsyncSessionLocal

        user_id = get_user_id()
        if not user_id:
            return self._err("Could not determine current user. Please log in again.")

        async with AsyncSessionLocal() as db:
            # Ownership check
            result = await db.execute(
                text(
                    "SELECT id, name, user_id FROM scheduled_jobs WHERE id = :id"
                ),
                {"id": job_id},
            )
            row = result.fetchone()

            if row is None:
                return self._err(f"No scheduled job found with ID: {job_id}")

            if str(row.user_id) != user_id:
                return self._err("Access denied — you can only delete your own jobs.")

            await db.execute(
                text("UPDATE scheduled_jobs SET is_active = FALSE WHERE id = :id"),
                {"id": job_id},
            )
            await db.commit()

        job_name = row.name
        logger.info(f"SchedulerOps: user {user_id} deleted job {job_id} ({job_name!r})")
        return self._ok({
            "job_id": job_id,
            "message": f"Scheduled job **{job_name}** has been cancelled.",
        })

    async def _run_job_now(self, job_id: str) -> dict:
        from app.core.user_context import get_user_id
        from app.core.database import AsyncSessionLocal

        user_id = get_user_id()
        if not user_id:
            return self._err("Could not determine current user. Please log in again.")

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                text(
                    "SELECT id, name, agent, message, user_id, deliver_to "
                    "FROM scheduled_jobs WHERE id = :id"
                ),
                {"id": job_id},
            )
            row = result.fetchone()

            if row is None:
                return self._err(f"No scheduled job found with ID: {job_id}")

            if str(row.user_id) != user_id:
                return self._err("Access denied — you can only trigger your own jobs.")

            deliver_to = row.deliver_to if isinstance(row.deliver_to, dict) else {}

            task_data = {
                "agent": row.agent,
                "source": "scheduler",
                "department": row.agent,
                "user_id": user_id,
                "message": row.message,
                "deliver_to": deliver_to,
                "_job_id": job_id,
                "input_type": "text",
                "permissions": ["all"],
                "attachments": [],
                "conversation_history": [],
            }

            from app.tasks.tasks import process_agent_task
            celery_task = process_agent_task.delay(task_data)

            await db.execute(
                text("UPDATE scheduled_jobs SET last_run = NOW() WHERE id = :id"),
                {"id": job_id},
            )
            await db.commit()

        job_name = row.name
        logger.info(
            f"SchedulerOps: user {user_id} triggered job {job_id} ({job_name!r}) "
            f"→ Celery task {celery_task.id}"
        )
        return self._ok({
            "job_id": job_id,
            "task_id": celery_task.id,
            "message": (
                f"Job **{job_name}** is now running. "
                "Results will be delivered per the job's delivery configuration."
            ),
        })
