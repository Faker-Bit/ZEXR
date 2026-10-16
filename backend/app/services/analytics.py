"""Analytics: event recording, click tracking and dashboard aggregates."""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any, Iterable
from urllib.parse import urlparse

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.base import utcnow
from app.models.analytics import DailyStat, Event, SearchQueryLog
from app.models.enums import EventType
from app.models.offer import Offer
from app.models.taxonomy import Brand, Category
from app.schemas.admin import AnalyticsOverview, DashboardStats, TopRow, TrendPoint

log = get_logger("analytics")

BATCH_SIZE = 25


def record_event(
    session: Session,
    event_type: EventType | str,
    *,
    entity_type: str | None = None,
    entity_id: str | None = None,
    user_id: str | None = None,
    session_id: str | None = None,
    path: str | None = None,
    referrer: str | None = None,
    country_code: str | None = None,
    currency: str | None = None,
    value: float | None = None,
    properties: dict[str, Any] | None = None,
    flush: bool = True,
) -> Event:
    event = Event(
        event_type=event_type.value if isinstance(event_type, EventType) else str(event_type),
        entity_type=entity_type,
        entity_id=entity_id,
        user_id=user_id,
        session_id=session_id,
        path=(path or "")[:500] or None,
        referrer=(referrer or "")[:500] or None,
        referrer_domain=(urlparse(referrer).netloc if referrer else None),
        country_code=country_code,
        currency=currency,
        value=value,
        properties=properties,
    )
    session.add(event)
    if flush:
        session.flush()
    return event


def record_offer_click(
    session: Session,
    offer: Offer,
    *,
    user_id: str | None = None,
    session_id: str | None = None,
    referrer: str | None = None,
    country_code: str | None = None,
) -> None:
    offer.click_count = (offer.click_count or 0) + 1
    offer.popularity_score = _popularity(offer)
    record_event(
        session,
        EventType.OFFER_CLICK,
        entity_type="offer",
        entity_id=offer.id,
        user_id=user_id,
        session_id=session_id,
        path=f"/offers/{offer.slug}",
        referrer=referrer,
        country_code=country_code,
        value=float(offer.promo_price) if offer.promo_price is not None else None,
    )


def record_offer_view(
    session: Session,
    offer: Offer,
    *,
    user_id: str | None = None,
    session_id: str | None = None,
    country_code: str | None = None,
) -> None:
    offer.view_count = (offer.view_count or 0) + 1
    record_event(
        session,
        EventType.OFFER_VIEW,
        entity_type="offer",
        entity_id=offer.id,
        user_id=user_id,
        session_id=session_id,
        path=f"/offers/{offer.slug}",
        country_code=country_code,
    )


def _popularity(offer: Offer) -> float:
    age_days = max(1.0, (utcnow() - (offer.published_at or utcnow())).total_seconds() / 86400)
    raw = (
        (offer.click_count or 0) * 3
        + (offer.bookmark_count or 0) * 6
        + (offer.view_count or 0) * 0.4
    )
    return round(raw / (age_days ** 0.5), 4)


def recompute_popularity(session: Session, offer: Offer) -> float:
    score = _popularity(offer)
    offer.popularity_score = score
    return score


def recompute_quality(session: Session, offer: Offer) -> float:
    """A 0-100 trust/quality score used for handpicking and ranking."""
    score = 30.0
    if offer.verification_status == "verified":
        score += 25
    elif offer.verification_status == "needs_manual":
        score -= 5
    if offer.description and len(offer.description) > 200:
        score += 10
    if offer.how_to_redeem and len(offer.how_to_redeem) >= 3:
        score += 10
    if offer.fine_print:
        score += 5
    if and_offer_valid(offer):
        score += 10
    if offer.eligibility:
        score += 5
    if offer.official_url:
        score += 5
    if offer.is_demo_data:
        score -= 40
    if offer.is_global:
        score += 5
    if offer.description and re_scammy(offer.description):
        score -= 30
    score = max(0.0, min(100.0, score))
    offer.quality_score = round(score, 2)
    return score


def and_offer_valid(offer: Offer) -> bool:
    return not offer.is_expired


SCRAMMY_PATTERNS = (
    "100% off", "100% free", "guaranteed profit", "double your money",
    "act now or lose", "unlimited money", "risk free investment",
    "click here to claim your prize", "wire transfer",
)


def re_scammy(text: str) -> bool:
    lowered = (text or "").lower()
    return any(pattern in lowered for pattern in SCRAMMY_PATTERNS)


# ------------------------------------------------------------------ rollups
def _day_keys(days: int) -> list[date]:
    today = utcnow().date()
    return [today - timedelta(days=i) for i in range(days - 1, -1, -1)]


def _series(session: Session, metric: str, days: int) -> list[TrendPoint]:
    since = utcnow().date() - timedelta(days=days - 1)
    rows = session.execute(
        select(func.date(Event.created_at), func.count(Event.id))
        .where(Event.event_type == metric, func.date(Event.created_at) >= since)
        .group_by(func.date(Event.created_at))
    ).all()
    found = {str(row[0]): int(row[1]) for row in rows}
    return [TrendPoint(day=d.isoformat(), value=found.get(d.isoformat(), 0)) for d in _day_keys(days)]


def dashboard_stats(session: Session) -> DashboardStats:
    now = utcnow()
    week_ago = now - timedelta(days=7)

    def count_stmt(model: Any, *conditions: Any) -> int:  # type: ignore[name-defined]
        stmt = select(func.count(model.id))
        if conditions:
            stmt = stmt.where(*conditions)
        return int(session.execute(stmt).scalar() or 0)

    from app.models.offer import OfferCountry
    from app.models.source import DiscoveryCandidate
    from app.models.user import Bookmark, NewsletterSubscriber, Report, User

    def offer_count(*conditions: Any) -> int:
        stmt = select(func.count(Offer.id))
        if conditions:
            stmt = stmt.where(*conditions)
        return int(session.execute(stmt).scalar() or 0)

    live = offer_count(
        Offer.status == "published",
        or_(Offer.expires_at.is_(None), Offer.expires_at > now),
    )

    return DashboardStats(
        total_offers=offer_count(),
        live_offers=live,
        expired_offers=offer_count(Offer.status == "expired"),
        pending_review=offer_count(Offer.status == "pending_review"),
        verified_offers=offer_count(Offer.verification_status == "verified"),
        disputed_offers=offer_count(Offer.status == "disputed"),
        demo_offers=offer_count(Offer.is_demo_data.is_(True)),
        total_categories=int(session.execute(select(func.count(Category.id))).scalar() or 0),
        total_brands=int(session.execute(select(func.count(Brand.id))).scalar() or 0),
        total_sources=_count_table(session, "sources"),
        active_sources=_count_where(session, "sources", is_active=True),
        failing_sources=_count_where(session, "sources", health="failing"),
        total_users=count_stmt(User),
        new_users_7d=count_stmt(User, User.created_at >= week_ago),
        total_bookmarks=count_stmt(Bookmark),
        open_reports=int(
            session.execute(
                select(func.count(Report.id)).where(Report.status.in_(["open", "triaged"]))
            ).scalar()
            or 0
        ),
        pending_candidates=int(
            session.execute(
                select(func.count(DiscoveryCandidate.id)).where(
                    DiscoveryCandidate.status == "pending"
                )
            ).scalar()
            or 0
        ),
        clicks_7d=int(
            session.execute(
                select(func.count(Event.id)).where(
                    Event.event_type == EventType.OFFER_CLICK.value, Event.created_at >= week_ago
                )
            ).scalar()
            or 0
        ),
        views_7d=int(
            session.execute(
                select(func.count(Event.id)).where(
                    Event.event_type.in_([EventType.OFFER_VIEW.value, EventType.PAGE_VIEW.value]),
                    Event.created_at >= week_ago,
                )
            ).scalar()
            or 0
        ),
        searches_7d=int(
            session.execute(
                select(func.count(Event.id)).where(
                    Event.event_type == EventType.SEARCH.value, Event.created_at >= week_ago
                )
            ).scalar()
            or 0
        ),
        newsletter_subs=int(
            session.execute(
                select(func.count(NewsletterSubscriber.id)).where(
                    NewsletterSubscriber.is_active.is_(True)
                )
            ).scalar()
            or 0
        ),
        sponsored_offers=offer_count(Offer.is_sponsored.is_(True), Offer.status == "published"),
        avg_savings_percent=float(
            session.execute(
                select(func.avg(Offer.savings_percent)).where(Offer.status == "published")
            ).scalar()
            or 0
        ),
        generated_at=now,
    )


def _count_table(session: Session, table_name: str) -> int:
    from app.models import Base

    table = Base.metadata.tables[table_name]
    return int(session.execute(select(func.count()).select_from(table)).scalar() or 0)


def _count_where(session: Session, table_name: str, **conditions: Any) -> int:
    from app.models import Base

    table = Base.metadata.tables[table_name]
    stmt = select(func.count()).select_from(table)
    for key, value in conditions.items():
        stmt = stmt.where(table.c[key] == value)
    return int(session.execute(stmt).scalar() or 0)


def analytics_overview(session: Session, days: int = 30) -> AnalyticsOverview:
    days = max(1, min(days, 180))
    since = utcnow() - timedelta(days=days)

    top_categories = [
        TopRow(label=name, slug=slug, id=cid, value=count)
        for cid, slug, name, count in session.execute(
            select(Category.id, Category.slug, Category.name, func.count(Offer.id))
            .join(Offer, Offer.category_id == Category.id)
            .where(Offer.status == "published", Offer.created_at >= since)
            .group_by(Category.id, Category.slug, Category.name)
            .order_by(func.count(Offer.id).desc())
            .limit(12)
        ).all()
    ]

    top_offers = [
        TopRow(label=title, slug=slug, id=oid, value=count)
        for oid, slug, title, count in session.execute(
            select(Offer.id, Offer.slug, Offer.title, func.count(Event.id))
            .join(Event, Event.entity_id == Offer.id)
            .where(
                Event.event_type == EventType.OFFER_CLICK.value, Event.created_at >= since
            )
            .group_by(Offer.id, Offer.slug, Offer.title)
            .order_by(func.count(Event.id).desc())
            .limit(12)
        ).all()
    ]

    top_countries = [
        TopRow(label=code or "Unknown", value=count)
        for code, count in session.execute(
            select(Event.country_code, func.count(Event.id))
            .where(Event.created_at >= since, Event.country_code.isnot(None))
            .group_by(Event.country_code)
            .order_by(func.count(Event.id).desc())
            .limit(12)
        ).all()
    ]

    search_rows = session.execute(
        select(
            SearchQueryLog.query,
            func.count(SearchQueryLog.id),
            func.sum(SearchQueryLog.result_count),
        )
        .where(SearchQueryLog.created_at >= since)
        .group_by(SearchQueryLog.query)
        .order_by(func.count(SearchQueryLog.id).desc())
        .limit(20)
    ).all()

    top_searches = [
        TopRow(label=query, value=count, extra={"total_results": int(results or 0)})
        for query, count, results in search_rows
    ]

    zero_rows = session.execute(
        select(SearchQueryLog.query, func.count(SearchQueryLog.id))
        .where(SearchQueryLog.zero_results.is_(True), SearchQueryLog.created_at >= since)
        .group_by(SearchQueryLog.query)
        .order_by(func.count(SearchQueryLog.id).desc())
        .limit(15)
    ).all()

    clicks = sum(p.value for p in _series(session, EventType.OFFER_CLICK.value, days))
    views = sum(
        p.value
        for p in _series(session, EventType.OFFER_VIEW.value, days)
    )
    signups_series = _signups_series(session, days)

    verified_clicks = int(
        session.execute(
            select(func.count(Event.id))
            .join(Offer, Event.entity_id == Offer.id)
            .where(
                Event.event_type == EventType.OFFER_CLICK.value,
                Event.created_at >= since,
                Offer.verification_status == "verified",
            )
        ).scalar()
        or 0
    )

    ok_checks = int(
        session.execute(
            select(func.count()).select_from(_verification_table()).where(
                _verification_table().c.result.in_(["ok", "redirected"])
            )
        ).scalar()
        or 0
    )
    total_checks = int(
        session.execute(select(func.count()).select_from(_verification_table())).scalar() or 0
    )

    return AnalyticsOverview(
        range_days=days,
        clicks=_series(session, EventType.OFFER_CLICK.value, days),
        views=_series(session, EventType.OFFER_VIEW.value, days),
        searches=_series(session, EventType.SEARCH.value, days),
        signups=signups_series,
        top_categories=top_categories,
        top_offers=top_offers,
        top_countries=top_countries,
        top_searches=top_searches,
        zero_result_searches=[
            TopRow(label=query, value=count) for query, count in zero_rows
        ],
        conversion_rate=round(clicks / views, 4) if views else 0.0,
        click_to_verify_rate=round(verified_clicks / clicks, 4) if clicks else 0.0,
        verification_success_rate=round(ok_checks / total_checks, 4) if total_checks else 0.0,
    )


def _verification_table() -> Any:
    from app.models import Base

    return Base.metadata.tables["offer_verifications"]


def _signups_series(session: Session, days: int) -> list[TrendPoint]:
    from app.models.user import User

    since = utcnow().date() - timedelta(days=days - 1)
    rows = session.execute(
        select(func.date(User.created_at), func.count(User.id))
        .where(func.date(User.created_at) >= since)
        .group_by(func.date(User.created_at))
    ).all()
    found = {str(row[0]): int(row[1]) for row in rows}
    return [TrendPoint(day=d.isoformat(), value=found.get(d.isoformat(), 0)) for d in _day_keys(days)]


def trending_queries(session: Session, limit: int = 20, days: int = 7) -> list[SearchQueryLog]:
    since = utcnow() - timedelta(days=days)
    return list(
        session.execute(
            select(SearchQueryLog)
            .where(SearchQueryLog.created_at >= since)
            .order_by(SearchQueryLog.created_at.desc())
            .limit(limit * 4)
        )
        .scalars()
        .all()
    )[:limit]


def bump_trending(session: Session, limit: int = 50) -> None:
    """Recompute `trending_rank` from the last 7 days of click events."""
    since = utcnow() - timedelta(days=7)
    rows = session.execute(
        select(Event.entity_id, func.count(Event.id))
        .where(Event.event_type == EventType.OFFER_CLICK.value, Event.created_at >= since)
        .group_by(Event.entity_id)
        .order_by(func.count(Event.id).desc())
        .limit(limit)
    ).all()
    session.query(Offer).filter(Offer.trending_rank.isnot(None)).update(
        {Offer.trending_rank: None}, synchronize_session=False
    )
    for rank, (offer_id, _count) in enumerate(rows, start=1):
        session.execute(
            Offer.__table__.update()
            .where(Offer.id == offer_id)
            .values(trending_rank=rank)
        )


def upsert_daily_stat(
    session: Session,
    day: date,
    metric: str,
    value: float,
    dimension: str | None = None,
    dimension_key: str | None = None,
    increment: bool = True,
) -> DailyStat:
    existing = session.execute(
        select(DailyStat).where(
            DailyStat.day == day,
            DailyStat.metric == metric,
            DailyStat.dimension == dimension,
            DailyStat.dimension_key == dimension_key,
        )
    ).scalar_one_or_none()
    if existing:
        existing.value = (existing.value or 0) + value if increment else value
        return existing
    stat = DailyStat(
        day=day, metric=metric, dimension=dimension, dimension_key=dimension_key, value=value
    )
    session.add(stat)
    return stat


def rollup_events(session: Session, days: int = 1) -> int:
    """Move raw events older than N days into DailyStat counters."""
    cutoff = utcnow() - timedelta(days=days)
    events = list(
        session.execute(select(Event).where(Event.created_at < cutoff).limit(5000)).scalars().all()
    )
    if not events:
        return 0
    buckets: dict[tuple[str, str | None, str | None], float] = defaultdict(float)
    for event in events:
        buckets[(event.event_type, event.country_code, None)] += 1
        if event.entity_type == "offer" and event.entity_id:
            buckets[("clicks:offer", None, event.entity_id)] += 1
    today = utcnow().date()
    for (metric, dimension, dim_key), value in buckets.items():
        upsert_daily_stat(session, today, metric, value, dimension, dim_key)
    for event in events:
        session.delete(event)
    session.flush()
    return len(events)


def country_from_headers(headers: Any) -> str | None:
    for header in ("x-vercel-ip-country", "cf-ipcountry", "x-country-code", "x-geo-country"):
        value = headers.get(header)
        if value and value not in ("XX", "T1", ""):
            return value.upper()[:2]
    return None


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def safe_rate(numerator: float, denominator: float) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def average(values: Iterable[float]) -> float:
    items = list(values)
    return round(math.fsum(items) / len(items), 4) if items else 0.0


def last_n(days: int) -> datetime:
    return utcnow() - timedelta(days=days)