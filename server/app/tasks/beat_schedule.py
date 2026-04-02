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

All schedules use UTC timezone. Conversion: 9AM SGT = 01:00 UTC, 10AM SGT = 02:00 UTC.
"""

import asyncio
import logging
import time

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

    # Hung task cleanup — every 10 minutes
    "stuck-task-cleanup": {
        "task": "app.tasks.tasks.cleanup_stuck_tasks",
        "schedule": crontab(minute="*/10"),
        "options": {"queue": "default"},
    },

    # Stuck Redis plan cleanup — every 15 minutes
    "cleanup-stuck-plans": {
        "task": "app.tasks.tasks.cleanup_stuck_plans",
        "schedule": crontab(minute="*/15"),
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

    # Weekly HR summary — Friday 5PM SGT (09:00 UTC)
    "weekly-hr-summary": {
        "task": "app.tasks.tasks.process_agent_task",
        "schedule": crontab(hour=9, minute=0, day_of_week=5),  # 5PM SGT = 09:00 UTC
        "args": [{
            "agent": "hr",
            "source": "scheduler",
            "department": "hr",
            "user_id": "system",
            "event": "weekly_hr_summary",
            "message": "Generate weekly HR summary covering headcount, leave, recruitment, and payroll",
            "deliver_to": {
                "teams_channel": "hr",
            },
        }],
    },

    # Monthly headcount report — 1st of month 9AM SGT (01:00 UTC)
    "monthly-headcount": {
        "task": "app.tasks.tasks.process_agent_task",
        "schedule": crontab(hour=1, minute=0, day_of_month=1),  # 9AM SGT = 01:00 UTC
        "args": [{
            "agent": "hr",
            "source": "scheduler",
            "department": "hr",
            "user_id": "system",
            "event": "monthly_headcount",
            "message": "Generate monthly headcount report with department breakdown and attrition analysis",
            "deliver_to": {
                "teams_channel": "hr",
            },
        }],
    },

    # ── Sales Lead Automation ─────────────────────────────────────────────────

    # Email lead ingestion — daily 09:00 HKT (01:00 UTC)
    "sales-email-lead-ingestion": {
        "task": "sales.ingest_leads_from_email",
        "schedule": crontab(hour=1, minute=0),          # 09:00 HKT daily
        "options": {"queue": "sales"},
    },

    # Ticket lead ingestion — daily 09:10 HKT (01:10 UTC, after email task)
    "sales-ticket-lead-ingestion": {
        "task": "sales.ingest_leads_from_tickets",
        "schedule": crontab(hour=1, minute=10),         # 09:10 HKT daily
        "options": {"queue": "sales"},
    },

    # Weekly lead research — Monday 09:00 HKT (01:00 UTC)
    "sales-weekly-lead-research": {
        "task": "sales.research_new_leads",
        "schedule": crontab(hour=1, minute=0, day_of_week=1),  # Monday 09:00 HKT
        "options": {"queue": "sales"},
    },

    # Daily CRM digest — daily 09:30 HKT (01:30 UTC, after ingestion completes)
    "sales-daily-crm-digest": {
        "task": "sales.daily_crm_digest",
        "schedule": crontab(hour=1, minute=30),         # 09:30 HKT daily
        "options": {"queue": "sales"},
    },

    # ── Finance Scheduled Tasks ───────────────────────────────────────────────

    # Daily overdue invoice check — 8:30AM SGT (00:30 UTC)
    "daily-overdue-invoice-check": {
        "task": "app.tasks.finance_tasks.check_overdue_invoices",
        "schedule": crontab(hour=0, minute=30),         # 8:30AM SGT = 00:30 UTC
    },

    # Weekly AR/AP summary — Monday 9AM SGT (01:00 UTC)
    "weekly-ar-ap-summary": {
        "task": "app.tasks.finance_tasks.ar_ap_weekly_summary",
        "schedule": crontab(day_of_week=1, hour=1, minute=0),  # Monday 9AM SGT = 01:00 UTC
    },

    # Monthly financial close reminder — 25th of month 9AM SGT (01:00 UTC)
    "monthly-financial-close-reminder": {
        "task": "app.tasks.finance_tasks.month_close_reminder",
        "schedule": crontab(day_of_month=25, hour=1, minute=0),  # 9AM SGT = 01:00 UTC
    },

    # Quarterly GST reminder — 15th of Jan, Apr, Jul, Oct at 9AM SGT (01:00 UTC)
    "quarterly-gst-reminder": {
        "task": "app.tasks.finance_tasks.gst_filing_reminder",
        "schedule": crontab(month_of_year="1,4,7,10", day_of_month=15, hour=1, minute=0),
    },

    # Monthly financial statements — 2nd of month 9:30AM SGT (01:30 UTC)
    "monthly-financial-statements": {
        "task": "app.tasks.finance_tasks.generate_monthly_statements",
        "schedule": crontab(day_of_month=2, hour=1, minute=30),  # 9:30AM SGT = 01:30 UTC
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
                "SELECT id, user_id, name, agent, message, workflow_name, schedule, deliver_to "
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
            "workflow_name": row.workflow_name,
            "_job_name": row.name,
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

    Every 60 seconds during normal operation, tick() calls _reload_db_jobs()
    to pick up any jobs created (or deactivated) since Beat last started —
    eliminating the need to restart Beat after creating a new scheduled job.

    Usage:
        celery -A app.tasks.celery_app beat --scheduler app.tasks.beat_schedule:DatabaseScheduler
    """

    _DB_RELOAD_INTERVAL = 60   # seconds between DB polls
    _last_db_reload: float = 0.0

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

        # Record startup time so first reload fires after full interval
        self._last_db_reload = time.monotonic()

    def tick(self, *args, **kwargs):
        """Override tick() to periodically reload DB jobs into the live schedule."""
        now = time.monotonic()
        if now - self._last_db_reload >= self._DB_RELOAD_INTERVAL:
            self._reload_db_jobs()
            self._last_db_reload = now
        return super().tick(*args, **kwargs)

    def _reload_db_jobs(self):
        """
        Reconcile the live Beat schedule against the current DB state.

        Adds newly created active jobs; removes jobs that have been
        deactivated or deleted since the last reload.
        """
        try:
            db_jobs = load_db_jobs()
            existing = {k for k in self.schedule if k.startswith("db-job-")}
            current = set(db_jobs.keys())

            added = current - existing
            removed = existing - current

            if added:
                self.update_from_dict({k: db_jobs[k] for k in added})
                logger.info(f"Beat reload: +{len(added)} new job(s) added: {added}")

            for key in removed:
                self.schedule.pop(key, None)
                self.app.conf.beat_schedule.pop(key, None)
            if removed:
                logger.info(f"Beat reload: -{len(removed)} job(s) removed: {removed}")

            if added or removed:
                self.sync()

        except Exception as exc:
            logger.error(f"Beat DB reload failed: {exc}")
