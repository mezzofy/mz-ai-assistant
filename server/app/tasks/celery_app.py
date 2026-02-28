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

# ── App init ──────────────────────────────────────────────────────────────────

celery_app = Celery(
    "mezzofy_ai",
    broker=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    backend=os.getenv("REDIS_RESULT_BACKEND", "redis://localhost:6379/1"),
    # Task modules auto-discovered; explicit list avoids scanning all app/
    include=[
        "app.tasks.tasks",
        "app.tasks.webhook_tasks",
    ],
)

# ── Configuration ─────────────────────────────────────────────────────────────

celery_app.conf.update(
    # Serialisation
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],

    # Timezone (all scheduled times in SGT)
    timezone="Asia/Singapore",
    enable_utc=True,

    # Task tracking
    task_track_started=True,

    # Time limits (10 min hard / 9 min soft — prevents runaway LLM calls)
    task_time_limit=600,
    task_soft_time_limit=540,

    # Worker
    worker_concurrency=int(os.getenv("CELERY_CONCURRENCY", "4")),
    worker_prefetch_multiplier=1,  # Fair task distribution across workers

    # Result expiry — keep results for 24 hours
    result_expires=86400,

    # Retry config
    task_acks_late=True,
    task_reject_on_worker_lost=True,
)
