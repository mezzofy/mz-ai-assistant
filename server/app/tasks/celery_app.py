"""
Celery Application — task queue configuration for mz-ai-assistant.

Broker: Redis (REDIS_URL env var, default redis://localhost:6379/0)
Backend: Redis (REDIS_RESULT_BACKEND env var, default redis://localhost:6379/1)

Workers are started separately from the FastAPI server:
    celery -A app.tasks.celery_app worker --loglevel=info --concurrency=4

Beat (scheduled jobs) is started separately:
    celery -A app.tasks.celery_app beat --loglevel=info --scheduler app.tasks.beat_schedule:DatabaseScheduler
"""

import os
from celery import Celery
from celery.signals import worker_process_init

# ── App init ──────────────────────────────────────────────────────────────────

celery_app = Celery(
    "mezzofy_ai",
    broker=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    backend=os.getenv("REDIS_RESULT_BACKEND", "redis://localhost:6379/1"),
    # Task modules auto-discovered; explicit list avoids scanning all app/
    include=[
        "app.tasks.tasks",
        "app.tasks.webhook_tasks",
        "app.tasks.sales_lead_tasks",
    ],
)

# ── Configuration ─────────────────────────────────────────────────────────────

celery_app.conf.update(
    # Serialisation
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],

    # Timezone: UTC (cron expressions are stored and evaluated in UTC)
    # Conversion examples: 9AM SGT = 01:00 UTC, 10AM SGT = 02:00 UTC, 5PM SGT = 09:00 UTC
    timezone="UTC",
    enable_utc=True,

    # Task tracking
    task_track_started=True,

    # Time limits (16 min hard / 15 min soft — covers Leo contract + DOCX + web research)
    task_time_limit=960,        # 16 min hard — covers Leo contract + DOCX + web research
    task_soft_time_limit=900,   # 15 min soft

    # Worker
    worker_concurrency=int(os.getenv("CELERY_CONCURRENCY", "4")),
    worker_prefetch_multiplier=1,  # Fair task distribution across workers

    # Result expiry — keep results for 24 hours
    result_expires=86400,

    # Retry config
    task_acks_late=True,
    task_reject_on_worker_lost=True,
)

# ── Queue routing (added for fast/slow separation) ────────────────────────────
# NOTE (operator action required — do NOT apply automatically):
# To split fast/slow queues, update mezzofy-celery.service ExecStart to:
#   celery -A app.tasks.celery_app worker -Q fast,default --concurrency=2 -n fast@%h
# Then create /etc/systemd/system/mezzofy-celery-slow.service for -Q slow:
#   celery -A app.tasks.celery_app worker -Q slow --concurrency=1 -n slow@%h
# Then: sudo systemctl daemon-reload && sudo systemctl restart mezzofy-celery
celery_app.conf.task_routes = {
    "app.tasks.tasks.process_agent_task":          {"queue": "default"},
    "app.tasks.tasks.health_check":                {"queue": "default"},
    "sales.ingest_leads_from_email":               {"queue": "sales"},
    "sales.ingest_leads_from_tickets":             {"queue": "sales"},
    "sales.research_new_leads":                    {"queue": "sales"},
    "sales.daily_crm_digest":                      {"queue": "sales"},
}


# ── Event loop safety (Bug B fix) ─────────────────────────────────────────────
# AsyncSessionLocal and the SQLAlchemy engine are module-level singletons bound
# to the event loop that was active when the Celery worker forked from the parent
# process.  asyncio.run() creates and closes a new event loop per task call, so
# on the second call the engine's asyncpg connections point at the closed parent
# loop → "Future attached to a different loop".
# Disposing the sync-engine's connection pool at worker-process-init ensures
# each asyncio.run() call starts with fresh connections on the current loop.
@worker_process_init.connect
def reset_db_pool(**kwargs):
    from app.core.database import engine
    engine.sync_engine.dispose(close=False)
