"""In-process scheduler.

Runs alongside the API so a single container keeps offers fresh in development
and in small deployments.  In production you can disable it and rely purely on
Celery beat (set ``SCHEDULER_ENABLED=false``).
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger("scheduler")

_scheduler: BackgroundScheduler | None = None
_lock = threading.Lock()
_last_run: dict[str, datetime] = {}


@dataclass
class JobSpec:
    name: str
    interval_minutes: int
    func: Callable[[], dict]
    description: str
    enabled: bool = True
    next_run: datetime | None = field(default=None, repr=False)


def _job_discover() -> dict:
    from app.discovery.runner import run_sweep
    from app.db.session import session_scope
    from app.services import search as search_service

    with session_scope() as session:
        result = run_sweep(session, max_sources=8)
        search_service.invalidate_vocabulary_cache()
        return {
            "sources_checked": result.sources_checked,
            "created": result.items_created,
            "duplicate": result.items_duplicate,
            "rejected": result.items_rejected,
        }


def _job_verify() -> dict:
    from app.db.session import session_scope
    from app.services import verification

    with session_scope() as session:
        result = verification.run_verification_sweep(session, limit=40)
        expired = verification.expire_finished_offers(session)
        return {"checked": result.checked, "ok": result.ok, "broken": result.broken, "expired": expired}


def _job_expiry() -> dict:
    from app.db.session import session_scope
    from app.services import verification

    with session_scope() as session:
        return {"expired": verification.expire_finished_offers(session)}


def _job_trending() -> dict:
    from app.db.session import session_scope
    from app.services import analytics

    with session_scope() as session:
        analytics.bump_trending(session)
    return {"ok": True}


def _job_rollup() -> dict:
    from app.db.session import session_scope
    from app.services import analytics

    with session_scope() as session:
        return {"events": analytics.rollup_events(session, days=1)}


def _job_alerts() -> dict:
    from app.db.session import session_scope
    from app.services.notifications import dispatch_alerts, notify_expiring_bookmarks

    with session_scope() as session:
        return {
            "expiring": notify_expiring_bookmarks(session),
            **dispatch_alerts(session),
        }


def _job_digest() -> dict:
    from app.db.session import session_scope
    from app.services.notifications import send_weekly_digest

    with session_scope() as session:
        return {"sent": send_weekly_digest(session)}


JOBS: list[JobSpec] = [
    JobSpec("verify", 60, _job_verify, "Re-check offer pages and flag broken links", enabled=settings.verify_enabled),
    JobSpec("discover", 240, _job_discover, "Poll data sources for new offers", enabled=settings.discovery_enabled),
    JobSpec("expiry", 15, _job_expiry, "Move offers past their deadline to expired", enabled=True),
    JobSpec("trending", 30, _job_trending, "Recompute trending rankings", enabled=True),
    JobSpec("rollup", 720, _job_rollup, "Aggregate raw events into daily stats", enabled=True),
    JobSpec("alerts", 180, _job_alerts, "Send saved-offer expiry alerts", enabled=True),
    JobSpec("digest", 720, _job_digest, "Weekly newsletter digest", enabled=True),
]


def _wrap(spec: JobSpec) -> Callable[[], None]:
    def _inner() -> None:
        if not spec.enabled:
            return
        started = datetime.utcnow()
        try:
            result = spec.func()
            _last_run[spec.name] = started
            log.info("scheduler.job_done", job=spec.name, ms=int((datetime.utcnow() - started).total_seconds() * 1000), **result)
        except Exception as exc:
            log.exception("scheduler.job_failed", job=spec.name, error=str(exc))

    return _inner


def start_scheduler() -> BackgroundScheduler | None:
    global _scheduler
    if not settings.scheduler_enabled:
        log.info("scheduler.disabled")
        return None
    with _lock:
        if _scheduler is not None:
            return _scheduler
        scheduler = BackgroundScheduler(timezone="UTC", job_defaults={"coalesce": True, "max_instances": 1})
        for spec in JOBS:
            if not spec.enabled:
                continue
            scheduler.add_job(
                _wrap(spec),
                trigger=IntervalTrigger(minutes=spec.interval_minutes),
                id=spec.name,
                name=spec.name,
                replace_existing=True,
                next_run_time=datetime.utcnow() + timedelta(minutes=2),
                max_instances=1,
                coalesce=True,
            )
        scheduler.start()
        _scheduler = scheduler
        log.info("scheduler.started", jobs=[s.name for s in JOBS if s.enabled])
        return scheduler


def stop_scheduler() -> None:
    global _scheduler
    with _lock:
        if _scheduler is not None:
            _scheduler.shutdown(wait=False)
            _scheduler = None


def run_now(name: str) -> dict:
    """Manual trigger used by the admin panel and tests."""
    spec = next((s for s in JOBS if s.name == name), None)
    if spec is None:
        raise KeyError(name)
    return spec.func()


def describe_jobs() -> list:
    from app.schemas.admin import ScheduledJobOut

    return [
        ScheduledJobOut(
            name=spec.name,
            schedule=f"every {spec.interval_minutes} min",
            enabled=spec.enabled,
            last_run_at=_last_run.get(spec.name),
            next_run_at=(
                _last_run.get(spec.name) + timedelta(minutes=spec.interval_minutes)
                if _last_run.get(spec.name)
                else None
            ),
            description=spec.description,
        )
        for spec in JOBS
    ]