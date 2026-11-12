"""Celery application configuration."""

from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from unimonitor.config import get_settings

settings = get_settings()

celery_app = Celery(
    "unimonitor",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "unimonitor.worker.tasks.assessment",
        "unimonitor.worker.tasks.reporting",
        "unimonitor.worker.tasks.notifications",
    ],
)

celery_app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    # Timezone
    timezone="UTC",
    enable_utc=True,
    # Task behaviour
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_always_eager=settings.CELERY_TASK_ALWAYS_EAGER,
    # Result expiry
    result_expires=86400,  # 24 hours
    # Concurrency
    worker_prefetch_multiplier=1,
    # Beat schedule
    beat_schedule={
        "scheduled-assessments-every-15min": {
            "task": "unimonitor.worker.tasks.assessment.run_scheduled_assessments",
            "schedule": crontab(minute="*/15"),
            "options": {"queue": "assessments"},
        },
        "daily-digest-08-00": {
            "task": "unimonitor.worker.tasks.notifications.send_daily_digests",
            "schedule": crontab(hour=8, minute=0),
            "options": {"queue": "notifications"},
        },
        "weekly-digest-monday-08-00": {
            "task": "unimonitor.worker.tasks.notifications.send_weekly_digests",
            "schedule": crontab(day_of_week="monday", hour=8, minute=0),
            "options": {"queue": "notifications"},
        },
        "cleanup-old-runs-daily": {
            "task": "unimonitor.worker.tasks.assessment.cleanup_old_runs",
            "schedule": crontab(hour=2, minute=0),
            "options": {"queue": "maintenance"},
        },
    },
    # Queues
    task_routes={
        "unimonitor.worker.tasks.assessment.*": {"queue": "assessments"},
        "unimonitor.worker.tasks.reporting.*": {"queue": "reports"},
        "unimonitor.worker.tasks.notifications.*": {"queue": "notifications"},
    },
)
