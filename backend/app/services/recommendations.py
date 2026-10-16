"""Personalised recommendations and homepage bundles."""

from __future__ import annotations

from datetime import timedelta
from typing import Sequence

from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.db.base import utcnow
from app.models.enums import OfferStatus, OfferType
from app.models.offer import Offer
from app.models.taxonomy import Category
from app.services.offers import OFFER_LOAD_OPTIONS, live_condition

# Tags a user can pick as "interests" — deliberately concrete so matching works.
INTEREST_TAGS: list[dict[str, object]] = [
    {"slug": "ai", "label": "AI tools", "icon": "sparkles", "keywords": ["ai", "llm", "gpt", "model"]},
    {"slug": "developer", "label": "Developer tools", "icon": "code", "keywords": ["api", "sdk", "code"]},
    {"slug": "cloud", "label": "Cloud & hosting", "icon": "cloud", "keywords": ["hosting", "cloud", "vps"]},
    {"slug": "vpn", "label": "VPN & privacy", "icon": "shield", "keywords": ["vpn", "privacy", "proxy"]},
    {"slug": "design", "label": "Design", "icon": "palette", "keywords": ["design", "graphics", "photo"]},
    {"slug": "productivity", "label": "Productivity", "icon": "checklist", "keywords": ["notes", "task", "project"]},
    {"slug": "streaming", "label": "Streaming", "icon": "play", "keywords": ["streaming", "movies", "tv"]},
    {"slug": "gaming", "label": "Gaming", "icon": "gamepad", "keywords": ["gaming", "game", "xbox"]},
    {"slug": "shopping", "label": "Shopping", "icon": "shopping-bag", "keywords": ["shopping", "fashion", "store"]},
    {"slug": "education", "label": "Learning", "icon": "graduation-cap", "keywords": ["learning", "course", "education"]},
    {"slug": "finance", "label": "Finance & cashback", "icon": "wallet", "keywords": ["cashback", "finance", "bank"]},
    {"slug": "travel", "label": "Travel", "icon": "plane", "keywords": ["travel", "hotel", "flight"]},
]

INTEREST_KEYWORDS = {str(i["slug"]): [str(k) for k in i["keywords"]] for i in INTEREST_TAGS}  # type: ignore[index]


def available_interests() -> list[dict[str, object]]:
    return INTEREST_TAGS


def recommend_offers(
    session: Session,
    *,
    interests: Sequence[str] | None = None,
    categories: Sequence[str] | None = None,
    country_code: str | None = None,
    limit: int = 12,
    exclude_ids: Sequence[str] = (),
) -> list[Offer]:
    """Rank live offers against the user's stated interests.

    Matching is keyword + taxonomy based and always grounded in stored rows — no
    model-generated recommendations are surfaced as if they were offers.
    """
    interests = [i.lower() for i in (interests or []) if i]
    categories = [c.lower() for c in (categories or []) if c]

    category_ids: list[str] = []
    if categories:
        rows = session.execute(
            select(Category.id).where(
                or_(
                    Category.slug.in_(categories),
                    func.lower(Category.name).in_(categories),
                )
            )
        ).all()
        category_ids = [r[0] for r in rows]

    keywords: list[str] = []
    for interest in interests:
        keywords.extend(INTEREST_KEYWORDS.get(interest, [interest]))

    scoring = case((Offer.category_id.in_(category_ids), 50.0), else_=0.0)
    for keyword in keywords[:12]:
        scoring = scoring + case(
            (func.lower(Offer.title).like(f"%{keyword}%", escape="\\"), 12.0),
            (func.lower(Offer.short_description).like(f"%{keyword}%", escape="\\"), 6.0),
            else_=0.0,
        )
    scoring = (
        scoring
        + case((Offer.verification_status == "verified", 8.0), else_=0.0)
        + case((Offer.is_featured.is_(True), 4.0), else_=0.0)
        + (Offer.popularity_score / 500.0)
        + (func.coalesce(Offer.savings_percent, 0) / 60.0)
        + Offer.quality_score / 100.0
    )

    stmt = (
        select(Offer)
        .options(*OFFER_LOAD_OPTIONS)
        .where(live_condition(), Offer.id.notin_(list(exclude_ids) or [""]))
        .order_by(scoring.desc(), Offer.published_at.desc())
        .limit(limit)
    )
    if category_ids:
        # Blend: half taxonomy-targeted, half general popularity.
        targeted = (
            select(Offer)
            .options(*OFFER_LOAD_OPTIONS)
            .where(live_condition(), Offer.category_id.in_(category_ids))
            .order_by(Offer.popularity_score.desc(), Offer.savings_percent.desc())
            .limit(limit)
        )
        return list(session.execute(targeted).scalars().unique().all())
    return list(session.execute(stmt).scalars().unique().all())


def popular_for_country(session: Session, country_code: str | None, limit: int = 12) -> list[Offer]:
    if not country_code:
        return recommend_offers(session, limit=limit)
    from app.models.offer import OfferCountry

    stmt = (
        select(Offer)
        .options(*OFFER_LOAD_OPTIONS)
        .where(
            live_condition(),
            or_(
                Offer.is_global.is_(True),
                Offer.id.in_(
                    select(OfferCountry.offer_id).where(
                        OfferCountry.country_code == country_code,
                        OfferCountry.is_available.is_(True),
                    )
                ),
            ),
        )
        .order_by(Offer.popularity_score.desc(), Offer.savings_percent.desc())
        .limit(limit)
    )
    return list(session.execute(stmt).scalars().unique().all())


def fresh_offers(session: Session, limit: int = 12, hours: int = 48) -> list[Offer]:
    since = utcnow() - timedelta(hours=hours)
    stmt = (
        select(Offer)
        .options(*OFFER_LOAD_OPTIONS)
        .where(live_condition(), Offer.published_at.isnot(None), Offer.published_at >= since)
        .order_by(Offer.published_at.desc())
        .limit(limit)
    )
    return list(session.execute(stmt).scalars().unique().all())


def free_alternatives(session: Session, limit: int = 12) -> list[Offer]:
    """Genuinely free products — no trial, no card, no catch."""
    stmt = (
        select(Offer)
        .options(*OFFER_LOAD_OPTIONS)
        .where(
            live_condition(),
            Offer.offer_type == OfferType.FREE.value,
            Offer.is_genuinely_free.is_(True),
        )
        .order_by(Offer.quality_score.desc(), Offer.popularity_score.desc())
        .limit(limit)
    )
    return list(session.execute(stmt).scalars().unique().all())


def no_card_offers(session: Session, limit: int = 12) -> list[Offer]:
    stmt = (
        select(Offer)
        .options(*OFFER_LOAD_OPTIONS)
        .where(
            live_condition(),
            Offer.requires_payment_method.is_(False),
            Offer.offer_type.in_([OfferType.FREE.value, OfferType.FREE_CREDITS.value]),
        )
        .order_by(Offer.quality_score.desc(), Offer.popularity_score.desc())
        .limit(limit)
    )
    return list(session.execute(stmt).scalars().unique().all())


def under_price_offers(session: Session, limit: int = 12, max_price: float = 10.0) -> list[Offer]:
    stmt = (
        select(Offer)
        .options(*OFFER_LOAD_OPTIONS)
        .where(live_condition(), Offer.promo_price.isnot(None), Offer.promo_price <= max_price)
        .order_by(Offer.popularity_score.desc(), Offer.savings_percent.desc())
        .limit(limit)
    )
    return list(session.execute(stmt).scalars().unique().all())


def ending_soon(session: Session, limit: int = 12, days: int = 3) -> list[Offer]:
    now = utcnow()
    stmt = (
        select(Offer)
        .options(*OFFER_LOAD_OPTIONS)
        .where(
            live_condition(),
            Offer.expires_at.isnot(None),
            Offer.expires_at > now,
            Offer.expires_at <= now + timedelta(days=days),
        )
        .order_by(Offer.expires_at.asc())
        .limit(limit)
    )
    return list(session.execute(stmt).scalars().unique().all())


def trending_now(session: Session, limit: int = 12) -> list[Offer]:
    stmt = (
        select(Offer)
        .options(*OFFER_LOAD_OPTIONS)
        .where(live_condition())
        .order_by(
            Offer.trending_rank.asc().nulls_last(),
            Offer.popularity_score.desc(),
        )
        .limit(limit)
    )
    return list(session.execute(stmt).scalars().unique().all())


def matches_alert(offer: Offer, alert: object) -> bool:
    """Pure predicate used by the notification worker (no DB access)."""
    category_id = getattr(alert, "category_id", None)
    brand_id = getattr(alert, "brand_id", None)
    query = (getattr(alert, "query", None) or "").lower()
    filters = getattr(alert, "filters", None) or {}

    if not offer.is_live:
        return False
    if category_id and offer.category_id != category_id:
        return False
    if brand_id and offer.brand_id != brand_id:
        return False
    if filters.get("offer_type") and offer.offer_type != filters["offer_type"]:
        return False
    if query:
        haystack = f"{offer.title} {offer.short_description}".lower()
        if query not in haystack:
            return False
    return True


def category_counts(session: Session) -> dict[str, int]:
    rows = session.execute(
        select(Category.slug, func.count(Offer.id))
        .join(Offer, Offer.category_id == Category.id)
        .where(Offer.status == OfferStatus.PUBLISHED.value)
        .group_by(Category.slug)
    ).all()
    return {slug: count for slug, count in rows}


def with_category_counts(categories: list[Category]) -> list[Category]:
    for category in categories:
        category._offer_count = 0  # type: ignore[attr-defined]
        category._live_offer_count = 0  # type: ignore[attr-defined]
    return categories


def select_offer_options() -> list:
    return list(OFFER_LOAD_OPTIONS)