"""Celery application.

Runs in production.  When Redis is unavailable every task can still be executed
in-process via `run_task_sync()` (used by the scheduler and the admin API), so
the platform never depends on a broker to keep offers fresh.
"""

from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger("celery")

celery_app = Celery(
    "zexrdealhub",
    broker=settings.effective_broker_url,
    backend=settings.effective_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=200,
    task_time_limit=600,
    task_soft_time_limit=540,
    task_always_eager=settings.celery_task_always_eager,
    task_eager_propagates=settings.celery_task_always_eager,
    result_expires=3600,
    beat_schedule={
        "verify-offers": {
            "task": "zexrdealhub.verify_offers",
            "schedule": crontab(minute="*/30"),
        },
        "discover-offers": {
            "task": "zexrdealhub.discover_offers",
            "schedule": crontab(minute=7, hour="*/4"),
        },
        "expire-offers": {
            "task": "zexrdealhub.expire_offers",
            "schedule": crontab(minute=0),
        },
        "refresh-trending": {
            "task": "zexrdealhub.refresh_trending",
            "schedule": crontab(minute=15),
        },
        "rollup-analytics": {
            "task": "zexrdealhub.rollup_analytics",
            "schedule": crontab(minute=30, hour=1),
        },
        "purge-verifications": {
            "task": "zexrdealhub.purge_verifications",
            "schedule": crontab(minute=0, hour=4, day_of_week=0),
        },
        "send-expiry-alerts": {
            "task": "zexrdealhub.send_expiry_alerts",
            "schedule": crontab(minute=0, hour=8),
        },
        "newsletter-digest": {
            "task": "zexrdealhub.send_newsletter_digest",
            "schedule": crontab(minute=30, hour=8, day_of_week="mon-fri"),
        },
    },
)

celery_app.autodiscover_tasks(["app.workers"])


def run_task_sync(name: str, *args: object, **kwargs: object) -> dict:
    """Execute a task locally — used when no broker is configured."""
    from app.workers import tasks

    task = getattr(tasks, name)
    return task.run(*args, **kwargs)  # type: ignore[attr-defined]