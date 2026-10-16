"""Health + readiness probes."""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from app.api.deps import SessionDep
from app.core.config import settings
from app.db.base import utcnow
from app.schemas.common import HealthStatus

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthStatus, summary="Liveness + dependency check")
def health(session: SessionDep) -> HealthStatus:
    database = "ok"
    try:
        session.execute(text("SELECT 1"))
    except Exception as exc:  # pragma: no cover
        database = f"error: {type(exc).__name__}"

    cache_state = "ok" if settings.cache_enabled else "disabled"
    scheduler = "enabled" if settings.scheduler_enabled else "disabled"

    overall = "ok" if database == "ok" else "degraded"
    return HealthStatus(
        status=overall,
        version=settings.app_version,
        environment=settings.environment,
        database=database,
        cache=cache_state,
        scheduler=scheduler,
        checked_at=utcnow(),
    )


@router.get("/version", summary="Build metadata")
def version() -> dict:
    return {
        "name": settings.app_name,
        "slug": settings.app_slug,
        "version": settings.app_version,
        "environment": settings.environment,
        "site_url": settings.site_url,
    }


@router.get("/config", summary="Public runtime configuration for the frontend")
def public_config() -> dict:
    return {
        "features": {
            "registration": True,
            "oauth": {
                "google": bool(settings.google_client_id),
                "github": bool(settings.github_client_id),
            },
            "newsletter": True,
            "reports": True,
            "submissions": True,
            "affiliate_disclosure": True,
        },
        "limits": {
            "search_page_size": 100,
            "offers_page_size": 24,
            "suggestions": 8,
        },
        "disclosure": {
            "affiliate": (
                "Some links are affiliate links. We may earn a commission at no extra cost to you. "
                "Affiliate status is always labelled on the offer."
            ),
            "verification": (
                "Prices and availability are verified automatically against official pages where "
                "technically possible. Always confirm on the official page before purchasing."
            ),
        },
    }