"""Public visitor statistics for the header counter.

Deliberately narrow and cheap:

* One day, one query, cached for a couple of minutes so the header does not
  add a database round trip to every page render.
* Distinct first-party session ids only. No IP, no user agent, no fingerprint.
  This is the same identifier the privacy page already describes.
* Read-only and unauthenticated, so it is safe to expose, but it returns two
  integers and nothing else: no per-path breakdown, no referrers, no timeline.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.base import utcnow
from app.models.analytics import Event
from app.models.enums import EventType

#: Cache window for the header counter.
_STATS_CACHE_TTL_SECONDS = 120

_cache: dict[str, object] = {"expires": 0.0, "value": None}


def _empty() -> dict[str, int]:
    return {"page_views_today": 0, "visitors_today": 0}


def today_stats(session: Session) -> dict[str, int]:
    """Page views and distinct visitors since midnight UTC.

    Cached in-process. Behind more than one worker each keeps its own cache,
    which is fine: the numbers are identical, only the refresh interval differs.
    """
    now = utcnow().timestamp()
    if _cache["value"] is not None and float(_cache["expires"]) > now:
        return dict(_cache["value"])  # type: ignore[arg-type]

    since = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    views = int(
        session.execute(
            select(func.count(Event.id)).where(
                Event.event_type == EventType.PAGE_VIEW.value,
                Event.created_at >= since,
            )
        ).scalar()
        or 0
    )
    visitors = int(
        session.execute(
            select(func.count(func.distinct(Event.session_id))).where(
                Event.event_type == EventType.PAGE_VIEW.value,
                Event.created_at >= since,
                Event.session_id.isnot(None),
            )
        ).scalar()
        or 0
    )

    value = {"page_views_today": views, "visitors_today": visitors}
    _cache["value"] = value
    _cache["expires"] = now + _STATS_CACHE_TTL_SECONDS
    return dict(value)


def clear_cache() -> None:
    """Drop the cache. Used by tests and after an explicit refresh."""
    _cache["value"] = None
    _cache["expires"] = 0.0