"""
SchedulerAgent — Chat-based scheduled job management.

Handles natural language requests to create, list, delete, and trigger
scheduled jobs. Runs synchronously (no Celery) since scheduler CRUD ops
are fast DB operations.

Routing:
    Dispatched when chat.py detects scheduler keywords and sets
    task["agent"] = "scheduler".

    can_handle: task["agent"] == "scheduler"
    execute:    calls llm.execute_with_tools() with a scheduler-focused
                system prompt; LLM selects the correct SchedulerOps tool.
"""

import logging

from app.agents.base_agent import BaseAgent

logger = logging.getLogger("mezzofy.agents.scheduler")

_SYSTEM_PROMPT = """You are the Scheduler Assistant for Mezzofy's AI system.
Your sole job is to help users manage their scheduled AI jobs using the provided tools.

## Available scheduler tools
- create_scheduled_job — Create a recurring job for an AI agent
- list_scheduled_jobs — Show the user's active scheduled jobs
- delete_scheduled_job — Cancel/deactivate a scheduled job (requires job_id)
- run_job_now — Immediately trigger a scheduled job once (requires job_id)

## Rules for create_scheduled_job
- Valid agents: sales, marketing, finance, support, management
- Cron format: 5 fields (minute hour day-of-month month day-of-week), all UTC
- Timezone conversions: 9AM SGT = 01:00 UTC → cron "0 1 * * *"
                        8AM MYT = 00:00 UTC → cron "0 0 * * *"
                        9AM SGT Mon–Fri     → cron "0 1 * * 1-5"
- Minimum interval: 15 minutes. Maximum: 10 active jobs per user.
- Pick the agent that best matches the report topic if the user doesn't specify.

## Rules for delete_scheduled_job and run_job_now
- You need the job_id UUID. If the user refers to a job by name, call
  list_scheduled_jobs first to find the matching ID, then delete/run it.

## Response style
- After calling a tool, summarise the result in plain, friendly language.
- When listing jobs, present them as a readable list (name, agent, schedule).
- Never invent job_ids — always fetch them via list_scheduled_jobs first.
- Do NOT use Outlook, Teams, or any other tools — only scheduler tools.
"""


class SchedulerAgent(BaseAgent):
    """
    Scheduled job management agent.

    can_handle: task["agent"] == "scheduler"
    execute:    LLM tool-use loop via execute_with_tools()
    """

    def can_handle(self, task: dict) -> bool:
        return task.get("agent") == "scheduler"

    async def execute(self, task: dict) -> dict:
        config = task.get("_config", {})

        logger.info(
            f"SchedulerAgent.execute: user_id={task.get('user_id')} "
            f"message={task.get('message', '')[:80]!r}"
        )

        try:
            from app.llm.llm_manager import LLMManager

            llm = LLMManager(config)
            task_with_prompt = dict(task)
            task_with_prompt["system_prompt"] = _SYSTEM_PROMPT

            result = await llm.execute_with_tools(task_with_prompt)
        except Exception as exc:
            logger.error(f"SchedulerAgent.execute failed: {exc}", exc_info=True)
            return self._err(f"Scheduler error: {exc}")

        result.setdefault("agent_used", "scheduler")
        return result
