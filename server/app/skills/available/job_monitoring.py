"""
JobMonitoringSkill — Health checks, failure detection, run history analysis.

Used by SchedulerAgent to assess the health of scheduled jobs, detect
consecutive failures, and generate health reports.
"""

import logging
from datetime import datetime, timezone, timedelta

logger = logging.getLogger("mezzofy.skills.job_monitoring")

_FAILURE_THRESHOLD = 2   # consecutive failures before flagging as unhealthy
_STALE_THRESHOLD_HOURS = 48  # job not run in 48h is considered stale


class JobMonitoringSkill:
    """
    Monitors scheduled job health and surfaces issues to the SchedulerAgent.
    """

    def __init__(self, config: dict):
        self.config = config

    async def health_report(self, user_id: str) -> dict:
        """
        Generate a health report for all scheduled jobs.

        Returns:
            {success, output: {total, healthy, warning, failed, issues: [...]}}
        """
        try:
            from app.core.database import AsyncSessionLocal
            from sqlalchemy import text

            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    text("""
                        SELECT id, name, agent, schedule, is_active,
                               last_run, next_run, created_at
                        FROM scheduled_jobs
                        WHERE user_id = :user_id AND is_active = TRUE
                        ORDER BY name
                    """),
                    {"user_id": user_id},
                )
                jobs = [dict(row._mapping) for row in result.fetchall()]

            now_utc = datetime.now(timezone.utc)
            healthy, warning_count, failed_count = 0, 0, 0
            issues = []

            for job in jobs:
                job_issues = []
                last_run = job.get("last_run")
                next_run = job.get("next_run")

                # Check if job is overdue
                if next_run and hasattr(next_run, "replace"):
                    next_run_aware = next_run.replace(tzinfo=timezone.utc) if next_run.tzinfo is None else next_run
                    if next_run_aware < now_utc - timedelta(hours=1):
                        job_issues.append("Job appears overdue — next_run is in the past")

                # Check for stale jobs (never run)
                if last_run is None:
                    created_at = job.get("created_at")
                    if created_at:
                        created_aware = created_at.replace(tzinfo=timezone.utc) if created_at.tzinfo is None else created_at
                        if (now_utc - created_aware).total_seconds() > _STALE_THRESHOLD_HOURS * 3600:
                            job_issues.append(f"Job created {_STALE_THRESHOLD_HOURS}+ hours ago but never ran")

                if job_issues:
                    issues.append({
                        "job_name": job["name"],
                        "job_id": str(job["id"]),
                        "agent": job["agent"],
                        "schedule": job["schedule"],
                        "issues": job_issues,
                        "last_run": str(last_run) if last_run else "never",
                        "next_run": str(next_run) if next_run else "unknown",
                    })
                    warning_count += 1
                else:
                    healthy += 1

            return {
                "success": True,
                "output": {
                    "total": len(jobs),
                    "healthy": healthy,
                    "warning": warning_count,
                    "failed": failed_count,
                    "issues": issues,
                    "generated_at": now_utc.strftime("%Y-%m-%d %H:%M UTC"),
                },
            }
        except Exception as e:
            logger.error(f"JobMonitoringSkill.health_report failed: {e}")
            return {"success": False, "error": str(e)}

    async def get_run_history(
        self, user_id: str, job_id: str = "", limit: int = 20
    ) -> dict:
        """
        Return execution history from agent_task_log for scheduled jobs.

        Returns:
            {success, output: {runs: [{run_at, status, duration_ms, summary}]}}
        """
        try:
            from app.core.database import AsyncSessionLocal
            from sqlalchemy import text

            async with AsyncSessionLocal() as db:
                query = """
                    SELECT atl.id, atl.status, atl.queued_at, atl.started_at,
                           atl.completed_at, atl.duration_ms, atl.result_summary,
                           atl.error_message, atl.agent_id
                    FROM agent_task_log atl
                    WHERE atl.source = 'scheduler'
                      AND atl.triggered_by_user_id = :user_id
                """
                params: dict = {"user_id": user_id}
                if job_id:
                    query += " AND atl.task_input::text ILIKE :job_pattern"
                    params["job_pattern"] = f"%{job_id}%"
                query += " ORDER BY atl.queued_at DESC LIMIT :limit"
                params["limit"] = limit

                result = await db.execute(text(query), params)
                rows = result.fetchall()

            runs = [
                {
                    "run_id": str(r.id),
                    "agent": r.agent_id,
                    "status": r.status,
                    "queued_at": str(r.queued_at),
                    "duration_ms": r.duration_ms,
                    "result_summary": (r.result_summary or "")[:200],
                    "error": r.error_message,
                }
                for r in rows
            ]
            return {"success": True, "output": {"runs": runs, "count": len(runs)}}
        except Exception as e:
            logger.error(f"JobMonitoringSkill.get_run_history failed: {e}")
            return {"success": False, "error": str(e)}
