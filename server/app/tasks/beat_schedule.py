"""
Celery Beat Schedule — recurring job definitions for mz-ai-assistant.

Contains:
  - STATIC_BEAT_SCHEDULE: 5 built-in system jobs (health check + 4 business reports)
  - load_db_jobs(): reads user-created jobs from the scheduled_jobs PostgreSQL table
    and merges them into the beat schedule at Beat startup.
  - DatabaseScheduler: custom Celery Beat scheduler that merges DB jobs at init time.

Beat is started with:
    celery -A app.tasks.celery_app beat --loglevel=info \
           --scheduler app.tasks.beat_schedule:DatabaseScheduler

All schedules use SGT (Asia/Singapore) timezone as configured in celery_app.
"""

import asyncio
import logging

from celery.beat import PersistentScheduler
from celery.schedules import crontab

from app.tasks.celery_app import celery_app

logger = logging.getLogger("mezzofy.tasks.beat")


# ── Static built-in schedules ─────────────────────────────────────────────────

STATIC_BEAT_SCHEDULE = {

    # System health check — every 5 minutes
    "system-health-check": {
        "task": "app.tasks.tasks.health_check",
        "schedule": crontab(minute="*/5"),
        "options": {"expires": 240},  # expire if not consumed in 4 min
    },

    # Weekly KPI report — Monday 9AM SGT (Celery uses UTC internally; UTC+8 → 01:00 UTC)
    "weekly-kpi-report": {
        "task": "app.tasks.tasks.process_agent_task",
        "schedule": crontab(hour=1, minute=0, day_of_week=1),  # 9AM SGT = 01:00 UTC
        "args": [{
            "agent": "management",
            "source": "scheduler",
            "department": "management",
            "user_id": "system",
            "message": "Generate weekly KPI dashboard across all departments for last week",
            "deliver_to": {
                "teams_channel": "management",
                "email": ["ceo@mezzofy.com", "coo@mezzofy.com"],
            },
        }],
    },

    # Monthly financial summary — 1st of month 8AM SGT (00:00 UTC)
    "monthly-financial-summary": {
        "task": "app.tasks.tasks.process_agent_task",
        "schedule": crontab(hour=0, minute=0, day_of_month=1),
        "args": [{
            "agent": "finance",
            "source": "scheduler",
            "department": "finance",
            "user_id": "system",
            "message": "Generate monthly financial summary for the previous month",
            "deliver_to": {
                "teams_channel": "finance",
                "email": ["cfo@mezzofy.com"],
            },
        }],
    },

    # Daily stale lead follow-up — weekdays 10AM SGT (02:00 UTC)
    "daily-lead-followup": {
        "task": "app.tasks.tasks.process_agent_task",
        "schedule": crontab(hour=2, minute=0, day_of_week="mon-fri"),
        "args": [{
            "agent": "sales",
            "source": "scheduler",
            "department": "sales",
            "user_id": "system",
            "message": "Find all leads with follow_up_date = today and send follow-up emails",
            "deliver_to": {"teams_channel": "sales"},
        }],
    },

    # Weekly support ticket summary — Friday 5PM SGT (09:00 UTC)
    "weekly-support-summary": {
        "task": "app.tasks.tasks.process_agent_task",
        "schedule": crontab(hour=9, minute=0, day_of_week=5),
        "args": [{
            "agent": "support",
            "source": "scheduler",
            "department": "support",
            "user_id": "system",
            "message": "Summarize this week's support tickets and flag recurring issues",
            "deliver_to": {
                "teams_channel": "support",
                "email": ["support-manager@mezzofy.com"],
            },
        }],
    },
}


# ── DB job loader ─────────────────────────────────────────────────────────────

def load_db_jobs() -> dict:
    """
    Load user-created jobs from the scheduled_jobs PostgreSQL table.

    Returns a dict in Celery Beat schedule format, ready to be merged with
    STATIC_BEAT_SCHEDULE. Only active jobs (is_active=True) are loaded.
    """
    try:
        return asyncio.run(_load_db_jobs_async())
    except Exception as e:
        logger.error(f"Failed to load DB scheduled jobs: {e}")
        return {}


async def _load_db_jobs_async() -> dict:
    """Async implementation of load_db_jobs."""
    from app.core.database import AsyncSessionLocal
    from sqlalchemy import text

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            text(
                "SELECT id, user_id, name, agent, message, schedule, deliver_to "
                "FROM scheduled_jobs WHERE is_active = TRUE ORDER BY created_at"
            )
        )
        rows = result.fetchall()

    schedule = {}
    for row in rows:
        try:
            schedule_entry = _row_to_beat_entry(row)
            if schedule_entry:
                # Key must be unique; prefix with 'db-' to distinguish from static jobs
                key = f"db-job-{row.id}"
                schedule[key] = schedule_entry
        except Exception as e:
            logger.warning(f"Skipping scheduled job {row.id} (load error: {e})")

    logger.info(f"Loaded {len(schedule)} user-created scheduled jobs from DB")
    return schedule


def _row_to_beat_entry(row) -> dict | None:
    """Convert a scheduled_jobs DB row to a Celery Beat schedule entry."""
    import json

    cron_expr = row.schedule or ""
    parsed_crontab = _parse_cron(cron_expr)
    if parsed_crontab is None:
        logger.warning(f"Invalid cron expression for job {row.id}: {cron_expr!r}")
        return None

    deliver_to = row.deliver_to if isinstance(row.deliver_to, dict) else {}

    return {
        "task": "app.tasks.tasks.process_agent_task",
        "schedule": parsed_crontab,
        "args": [{
            "agent": row.agent,
            "source": "scheduler",
            "department": row.agent,
            "user_id": str(row.user_id),
            "message": row.message,
            "deliver_to": deliver_to,
            "_job_id": str(row.id),
        }],
    }


def _parse_cron(expr: str) -> crontab | None:
    """
    Parse a standard 5-field cron expression into a Celery crontab object.

    Returns None if the expression is invalid.
    """
    if not expr or not expr.strip():
        return None

    parts = expr.strip().split()
    if len(parts) != 5:
        return None

    minute, hour, day_of_month, month_of_year, day_of_week = parts
    try:
        return crontab(
            minute=minute,
            hour=hour,
            day_of_month=day_of_month,
            month_of_year=month_of_year,
            day_of_week=day_of_week,
        )
    except Exception:
        return None


# ── Custom Beat scheduler ─────────────────────────────────────────────────────

class DatabaseScheduler(PersistentScheduler):
    """
    Celery Beat scheduler that merges static built-in jobs with user-created
    jobs from the PostgreSQL scheduled_jobs table.

    At startup:
      1. Loads STATIC_BEAT_SCHEDULE into conf.beat_schedule
      2. Calls load_db_jobs() to read user-created jobs from DB
      3. Merges both into the active schedule

    Usage:
        celery -A app.tasks.celery_app beat --scheduler app.tasks.beat_schedule:DatabaseScheduler
    """

    def setup_schedule(self):
        # Start with static built-in schedule
        static = {**STATIC_BEAT_SCHEDULE}

        # Merge user-created DB jobs
        db_jobs = load_db_jobs()
        merged = {**static, **db_jobs}

        # Inject into Celery app config
        self.app.conf.beat_schedule = merged

        logger.info(
            f"Beat schedule loaded: {len(static)} static + {len(db_jobs)} DB jobs "
            f"= {len(merged)} total"
        )

        # Let PersistentScheduler finish setup with the merged schedule
        super().setup_schedule()
