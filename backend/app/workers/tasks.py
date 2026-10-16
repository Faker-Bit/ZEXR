"""Background tasks: discovery, verification, expiry, analytics, notifications."""

from __future__ import annotations

from datetime import timedelta

from celery import shared_task

from app.core.logging import get_logger
from app.db.base import utcnow
from app.db.session import session_scope
from app.workers.celery_app import celery_app

log = get_logger("tasks")


@celery_app.task(name="zexrdealhub.discover_offers")
def discover_offers(force: bool = False, max_sources: int = 10) -> dict:
    """Poll configured sources and stage new offers for review."""
    from app.discovery.runner import run_sweep
    from app.services import search as search_service

    with session_scope() as session:
        result = run_sweep(session, force=force, max_sources=max_sources)
        search_service.invalidate_vocabulary_cache()
        payload = result.model_dump(mode="json")
    log.info("task.discover", **payload)
    return payload


@celery_app.task(name="zexrdealhub.verify_offers")
def verify_offers(limit: int = 50, all_offers: bool = False) -> dict:
    """Re-check published offers against their official pages."""
    from app.services import verification

    with session_scope() as session:
        result = verification.run_verification_sweep(session, limit=limit, only_stale=not all_offers)
        verification.expire_finished_offers(session)
        payload = result.model_dump(mode="json")
    log.info("task.verify", checked=payload["checked"], ok=payload["ok"], broken=payload["broken"])
    return payload


@celery_app.task(name="zexrdealhub.verify_offer")
def verify_offer_by_id(offer_id: str) -> dict:
    from app.services import verification

    with session_scope() as session:
        result = verification.run_verification_sweep(session, offer_ids=[offer_id], only_stale=False)
        payload = result.model_dump(mode="json")
    return payload


@celery_app.task(name="zexrdealhub.expire_offers")
def expire_offers() -> dict:
    from app.services import verification

    with session_scope() as session:
        count = verification.expire_finished_offers(session)
    log.info("task.expire", expired=count)
    return {"expired": count}


@celery_app.task(name="zexrdealhub.refresh_trending")
def refresh_trending() -> dict:
    from app.services import analytics

    with session_scope() as session:
        analytics.bump_trending(session)
    return {"ok": True}


@celery_app.task(name="zexrdealhub.rollup_analytics")
def rollup_analytics(days: int = 1) -> dict:
    from app.services import analytics

    with session_scope() as session:
        moved = analytics.rollup_events(session, days=days)
    return {"events_rolled_up": moved}


@celery_app.task(name="zexrdealhub.purge_verifications")
def purge_verifications(keep_days: int = 120) -> dict:
    from app.services import verification

    with session_scope() as session:
        removed = verification.purge_old_verifications(session, keep_days=keep_days)
    return {"removed": removed}


@celery_app.task(name="zexrdealhub.recompute_quality")
def recompute_quality(batch: int = 500) -> dict:
    from sqlalchemy import select

    from app.models.offer import Offer
    from app.services import analytics

    with session_scope() as session:
        rows = list(session.execute(select(Offer).limit(batch)).scalars().unique().all())
        for offer in rows:
            analytics.recompute_quality(session, offer)
    return {"updated": len(rows)}


@celery_app.task(name="zexrdealhub.send_expiry_alerts")
def send_expiry_alerts(days: int = 3) -> dict:
    """Notify users whose saved offers are about to expire."""
    from app.services.notifications import notify_expiring_bookmarks

    with session_scope() as session:
        sent = notify_expiring_bookmarks(session, days=days)
    return {"sent": sent}


@celery_app.task(name="zexrdealhub.send_newsletter_digest")
def send_newsletter_digest() -> dict:
    from app.services.notifications import send_weekly_digest

    with session_scope() as session:
        sent = send_weekly_digest(session)
    return {"sent": sent}


@celery_app.task(name="zexrdealhub.process_alerts")
def process_alerts() -> dict:
    from app.services.notifications import dispatch_alerts

    with session_scope() as session:
        result = dispatch_alerts(session)
    return result


@celery_app.task(name="zexrdealhub.warm_cache")
def warm_cache() -> dict:
    """Pre-compute the homepage + category payloads after a deploy."""
    from app.api.cache_sync import cache_put
    from app.api.v1.offers import home_bundle
    from app.core.cache import cache
    from app.db.session import SessionLocal

    session = SessionLocal()
    try:
        payload = home_bundle.__wrapped__(  # type: ignore[attr-defined]
            session, None, None, "USD", 8
        ) if hasattr(home_bundle, "__wrapped__") else home_bundle(session, None, None, "USD", 8)
        cache_put(cache.make_key("home", 8, "any", "USD", namespace="offers"), payload, ttl=300)
    except Exception as exc:  # pragma: no cover
        log.warning("task.warm_cache_failed", error=str(exc))
        return {"ok": False}
    finally:
        session.close()
    return {"ok": True, "at": utcnow().isoformat()}


@celery_app.task(name="zexrdealhub.healthcheck")
def healthcheck() -> dict:
    from sqlalchemy import text

    with session_scope() as session:
        session.execute(text("SELECT 1"))
    return {"ok": True, "at": utcnow().isoformat(), "lookback_hours": timedelta(hours=12).total_seconds()}