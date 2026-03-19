"""
ScheduleManagementSkill — CRUD on scheduled_jobs + live Celery Beat sync.

Used by SchedulerAgent to create, update, pause, resume, and delete
scheduled jobs, keeping the DB and live Beat schedule in sync.
"""

import logging
from typing import Optional

logger = logging.getLogger("mezzofy.skills.schedule_management")


class ScheduleManagementSkill:
    """
    Manages the full lifecycle of user-created scheduled jobs.

    Wraps the existing SchedulerOps tool and Beat sync utilities.
    """

    def __init__(self, config: dict):
        self.config = config

    async def create_job(
        self,
        user_id: str,
        name: str,
        agent: str,
        message: str,
        cron_expression: str,
        deliver_to: dict,
        workflow_name: str = "",
    ) -> dict:
        """
        Create a new scheduled job in the DB and add to live Beat schedule.

        Returns:
            {success, output: {job_id, name, schedule, next_run}}
        """
        try:
            from app.tools.scheduler.scheduler_ops import SchedulerOps
            sched = SchedulerOps(self.config)
            result = await sched.execute(
                "create_scheduled_job",
                user_id=user_id,
                name=name,
                agent=agent,
                message=message,
                schedule=cron_expression,
                deliver_to=deliver_to,
                workflow_name=workflow_name,
            )
            logger.info(f"ScheduleManagementSkill.create_job: name={name!r} agent={agent!r}")
            return result
        except Exception as e:
            logger.error(f"ScheduleManagementSkill.create_job failed: {e}")
            return {"success": False, "error": str(e)}

    async def list_jobs(self, user_id: str) -> dict:
        """
        List all active scheduled jobs for a user.

        Returns:
            {success, output: {jobs: [...]}}
        """
        try:
            from app.tools.scheduler.scheduler_ops import SchedulerOps
            sched = SchedulerOps(self.config)
            return await sched.execute("list_scheduled_jobs", user_id=user_id)
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def delete_job(self, job_id: str, user_id: str) -> dict:
        """
        Deactivate and remove a job from the Beat schedule.

        Returns:
            {success, output: {job_id, deleted: bool}}
        """
        try:
            from app.tools.scheduler.scheduler_ops import SchedulerOps
            sched = SchedulerOps(self.config)
            return await sched.execute(
                "delete_scheduled_job", job_id=job_id, user_id=user_id
            )
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def trigger_now(self, job_id: str, user_id: str) -> dict:
        """
        Immediately fire a scheduled job outside its cron schedule.

        Returns:
            {success, output: {task_id, message}}
        """
        try:
            from app.tools.scheduler.scheduler_ops import SchedulerOps
            sched = SchedulerOps(self.config)
            return await sched.execute(
                "run_job_now", job_id=job_id, user_id=user_id
            )
        except Exception as e:
            return {"success": False, "error": str(e)}
