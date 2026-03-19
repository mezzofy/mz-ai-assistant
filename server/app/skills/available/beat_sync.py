"""
BeatSyncSkill — Live Celery Beat schedule modification without service restart.

Used by SchedulerAgent to add, update, or remove jobs from the running
Celery Beat scheduler without requiring a worker restart.

This skill wraps the custom PersistentScheduler (beat_schedule.py) which
polls the scheduled_jobs DB table every 60 seconds. Writes to the DB are
sufficient to trigger Beat to pick up changes on the next poll cycle.
"""

import logging

logger = logging.getLogger("mezzofy.skills.beat_sync")


class BeatSyncSkill:
    """
    Provides Beat schedule sync utilities.

    The project's PersistentScheduler (beat_schedule.py) already polls
    the DB every 60 seconds, so DB writes automatically propagate to Beat.
    This skill handles explicit sync requests and status checks.
    """

    def __init__(self, config: dict):
        self.config = config

    async def sync_status(self) -> dict:
        """
        Check current Beat sync status — how many jobs are loaded.

        Returns:
            {success, output: {active_jobs: int, last_poll: str, next_poll: str}}
        """
        try:
            from app.core.database import AsyncSessionLocal
            from sqlalchemy import text

            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    text("SELECT COUNT(*) FROM scheduled_jobs WHERE is_active = TRUE")
                )
                active_count = result.scalar() or 0

            return {
                "success": True,
                "output": {
                    "active_jobs_in_db": active_count,
                    "beat_poll_interval_seconds": 60,
                    "note": (
                        "Celery Beat polls the scheduled_jobs table every 60 seconds. "
                        "New/updated jobs are picked up automatically without a restart."
                    ),
                },
            }
        except Exception as e:
            logger.error(f"BeatSyncSkill.sync_status failed: {e}")
            return {"success": False, "error": str(e)}

    async def force_next_run_recalculation(self, job_id: str) -> dict:
        """
        Recompute and update next_run for a specific job.

        Useful after modifying a job's cron schedule outside of SchedulerOps.

        Returns:
            {success, output: {job_id, new_next_run}}
        """
        try:
            from app.core.database import AsyncSessionLocal
            from sqlalchemy import text
            from app.webhooks.scheduler import compute_next_run

            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    text("SELECT schedule FROM scheduled_jobs WHERE id = :id"),
                    {"id": job_id},
                )
                row = result.fetchone()
                if not row:
                    return {"success": False, "error": f"Job {job_id} not found"}

                next_run = compute_next_run(row.schedule)
                await db.execute(
                    text("UPDATE scheduled_jobs SET next_run = :next_run WHERE id = :id"),
                    {"next_run": next_run, "id": job_id},
                )
                await db.commit()

            return {
                "success": True,
                "output": {
                    "job_id": job_id,
                    "new_next_run": next_run.strftime("%Y-%m-%d %H:%M UTC"),
                },
            }
        except Exception as e:
            logger.error(f"BeatSyncSkill.force_next_run_recalculation failed: {e}")
            return {"success": False, "error": str(e)}

    async def get_static_beat_jobs(self) -> dict:
        """
        Return the list of static (non-DB) Celery Beat jobs defined in celery_app.py.

        Returns:
            {success, output: {jobs: [{name, task, schedule}]}}
        """
        try:
            from app.tasks.celery_app import celery_app
            beat_schedule = getattr(celery_app.conf, "beat_schedule", {})
            jobs = [
                {
                    "name": name,
                    "task": cfg.get("task", ""),
                    "schedule": str(cfg.get("schedule", "")),
                }
                for name, cfg in beat_schedule.items()
            ]
            return {
                "success": True,
                "output": {
                    "static_jobs": jobs,
                    "count": len(jobs),
                    "note": "These are built-in Beat jobs defined in celery_app.py. "
                            "They cannot be modified or deleted via the Scheduler Agent.",
                },
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
