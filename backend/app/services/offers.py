"""Offer querying: filters, sorting, pagination, facets, related offers."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Sequence

from sqlalchemy import Select, and_, case, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.logging import get_logger
from app.db.base import utcnow
from app.models.enums import OfferStatus, OfferType, VerificationStatus
from app.models.offer import Offer
from app.models.taxonomy import Brand, Category, Country
from app.schemas.offer import FacetBucket, FacetResponse, OfferFilterParams

log = get_logger("offers")

LIVE_STATES = (OfferStatus.PUBLISHED.value,)

DURATION_RANGES: dict[str, tuple[int | None, int | None]] = {
    "instant": (0, 0),
    "week": (1, 7),
    "month": (8, 31),
    "quarter": (32, 92),
    "year": (93, 365),
}

SORT_COLUMNS = {
    "newest": Offer.published_at.desc(),
    "popular": Offer.popularity_score.desc(),
    "savings": Offer.savings_value.desc(),
    "value": (Offer.savings_value / func.nullif(Offer.original_price, 0)).desc(),
    "trending": Offer.trending_rank.asc(),
    "price_asc": Offer.promo_price.asc().nullslast(),
    "price_desc": Offer.promo_price.desc().nullslast(),
    "ending_soon": Offer.expires_at.asc().nulls_last(),
    "relevance": Offer.popularity_score.desc(),
}

OFFER_LOAD_OPTIONS = (
    selectinload(Offer.category),
    selectinload(Offer.brand),
    selectinload(Offer.countries),
    selectinload(Offer.prices),
)


def _truthy(value: Any) -> bool:
    if isinstance(value, str):
        return value.lower() in ("1", "true", "yes", "on")
    return bool(value)


# ------------------------------------------------------------------ queries
def live_condition(now: datetime | None = None) -> Any:
    now = now or utcnow()
    return and_(
        Offer.status.in_(LIVE_STATES),
        or_(Offer.expires_at.is_(None), Offer.expires_at > now),
        Offer.duplicate_of_id.is_(None),
    )


def expired_condition(now: datetime | None = None) -> Any:
    now = now or utcnow()
    return or_(
        Offer.status == OfferStatus.EXPIRED.value,
        and_(Offer.status.in_(LIVE_STATES), Offer.expires_at.isnot(None), Offer.expires_at <= now),
    )


def _slug_in(values: Sequence[str] | None) -> list[str]:
    if not values:
        return []
    if isinstance(values, str):
        values = [values]
    return [str(v).strip() for v in values if str(v).strip()]


def apply_filters(
    stmt: Select,
    filters: OfferFilterParams,
    *,
    now: datetime | None = None,
) -> Select:
    """Apply every non-textual filter to a select statement."""
    now = now or utcnow()

    category_slugs = _slug_in(filters.category)
    if category_slugs:
        # Subquery instead of a JOIN: the text-relevance query already joins
        # `categories`, and a second join would make column references ambiguous.
        stmt = stmt.where(
            Offer.category_id.in_(
                select(Category.id).where(Category.slug.in_(category_slugs))
            )
        )

    brand_slugs = _slug_in(filters.brand)
    if brand_slugs:
        stmt = stmt.where(
            Offer.brand_id.in_(select(Brand.id).where(Brand.slug.in_(brand_slugs)))
        )

    types = [t.value if isinstance(t, OfferType) else str(t) for t in (filters.type or [])]
    if types:
        stmt = stmt.where(Offer.offer_type.in_(types))

    currencies = [c.upper() for c in _slug_in(filters.currency)]
    if currencies:
        stmt = stmt.where(func.upper(Offer.currency).in_(currencies))

    countries = [c.upper() for c in _slug_in(filters.country)]
    if countries:
        from app.models.offer import OfferCountry

        stmt = stmt.where(
            or_(
                Offer.is_global.is_(True),
                Offer.id.in_(
                    select(OfferCountry.offer_id).where(
                        OfferCountry.country_code.in_(countries),
                        OfferCountry.is_available.is_(True),
                    )
                ),
            )
        )
        stmt = stmt.where(
            func.coalesce(Offer.excluded_countries, "[]").not_like(f'%"{countries[0]}"%')
        )

    if filters.min_savings is not None:
        stmt = stmt.where(Offer.savings_value >= filters.min_savings)

    if filters.max_price is not None:
        stmt = stmt.where(
            or_(Offer.promo_price.is_(None), Offer.promo_price <= filters.max_price)
        )

    if filters.min_trial_days is not None:
        stmt = stmt.where(
            or_(
                Offer.trial_days.is_(None),
                Offer.trial_days >= filters.min_trial_days,
                Offer.offer_type.in_([OfferType.FREE.value, OfferType.FREE_CREDITS.value]),
            )
        )

    if filters.max_trial_days is not None:
        stmt = stmt.where(Offer.trial_days <= filters.max_trial_days)

    if filters.duration:
        if filters.duration in DURATION_RANGES:
            low, high = DURATION_RANGES[filters.duration]
            stmt = stmt.where(Offer.trial_days.isnot(None), Offer.trial_days >= low, Offer.trial_days <= high)
        elif filters.duration == "lifetime":
            stmt = stmt.where(
                or_(Offer.billing_period == "lifetime", Offer.expires_at.is_(None))
            )

    if filters.requires_payment_method is not None:
        stmt = stmt.where(Offer.requires_payment_method.is_(filters.requires_payment_method))
    if filters.requires_student_id is not None:
        stmt = stmt.where(Offer.requires_student_id.is_(filters.requires_student_id))
    if filters.new_users_only is not None:
        stmt = stmt.where(Offer.requires_new_user.is_(filters.new_users_only))
    if filters.global_only:
        stmt = stmt.where(Offer.is_global.is_(True))
    if filters.verified_only:
        stmt = stmt.where(
            Offer.verification_status == VerificationStatus.VERIFIED.value
        )

    if filters.ending_within_days is not None:
        stmt = stmt.where(
            Offer.expires_at.isnot(None),
            Offer.expires_at > now,
            Offer.expires_at <= now + timedelta(days=filters.ending_within_days),
        )
    if filters.ending_within_hours is not None:
        stmt = stmt.where(
            Offer.expires_at.isnot(None),
            Offer.expires_at > now,
            Offer.expires_at <= now + timedelta(hours=filters.ending_within_hours),
        )

    if filters.category and stmt is not None:
        stmt = stmt.options(selectinload(Offer.category))

    return stmt


def apply_sort(stmt: Select, sort: str, relevance: Any | None = None) -> Select:
    if sort == "relevance" and relevance is not None:
        return stmt.order_by(relevance.desc(), Offer.published_at.desc())
    order = SORT_COLUMNS.get(sort, Offer.published_at.desc())
    return stmt.order_by(order, Offer.published_at.desc(), Offer.id.desc())


def fetch_page(
    session: Session,
    stmt: Select,
    page: int,
    page_size: int,
) -> tuple[list[Offer], int]:
    sub = stmt.order_by(None).subquery()
    total = int(session.execute(select(func.count()).select_from(sub)).scalar() or 0)
    rows = (
        session.execute(stmt.offset(max(0, (page - 1) * page_size)).limit(page_size))
        .scalars()
        .unique()
        .all()
    )
    return list(rows), total


def run_query(
    session: Session,
    filters: OfferFilterParams,
    *,
    expired: bool = False,
    page_size: int | None = None,
) -> tuple[list[Offer], int]:
    """The single entry point used by the directory, category pages and search.

    Combines the structured filters with (optional) full-text relevance and
    returns hydrated rows plus the unpaginated total.
    """
    page_size = page_size or filters.page_size
    relevance = None
    stmt = base_statement(expired=expired)

    query = (filters.q or "").strip()
    if query:
        from app.services import search as search_service

        vocab = search_service.get_vocabulary(session)
        intent = search_service.parse_intent(query, vocab)
        search_service.merge_intent_into_filters(filters, intent)

        tokens, required = _query_tokens(query, intent, vocab)
        relevance, _ = search_service.build_relevance(tokens, required=required)
        stmt = stmt.outerjoin(Brand, Offer.brand_id == Brand.id).outerjoin(
            Category, Offer.category_id == Category.id
        )
        stmt = search_service.apply_relevance_filter(stmt, relevance, required)

    stmt = apply_filters(stmt, filters)
    stmt = apply_sort(stmt, filters.sort, relevance)
    return fetch_page(session, stmt, filters.page, page_size)


def _query_tokens(query: str, intent: Any, vocab: Any) -> tuple[list[str], list[str]]:
    """Return (scoring tokens, required tokens).

    Scoring uses everything — the user's words, synonyms and the taxonomy terms
    the interpreter resolved.  Only the user's own meaningful words (plus the
    brand they named) are *required*, so expansion can never empty the result
    set on its own.
    """
    from app.services import search as search_service

    tokens = [t for t in search_service.normalise(query).split() if len(t) > 1]
    expanded: list[str] = []
    for token in tokens:
        expanded.extend(search_service._expand_synonyms([token]))

    for slug in intent.category_slugs:
        expanded.extend(_slug_tokens(slug))
        name = getattr(vocab, "category_names", {}).get(slug)
        if name:
            expanded.extend(t.lower() for t in _slug_tokens(name))
    for slug in intent.brand_slugs:
        name = getattr(vocab, "brand_names", {}).get(slug)
        expanded.extend(t.lower() for t in _slug_tokens(name or slug))

    required = [
        t for t in tokens
        if t not in search_service.STOPWORDS
        and t not in search_service.TYPE_WORDS
        and t not in search_service.DURATION_WORDS
        and t not in search_service.COUNTRY_ALIASES
        and t not in search_service.GENERIC_TAXONOMY_TOKENS
        and not t.isdigit()
    ]
    # A named brand is a hard requirement even when the query never spelled it,
    # and a resolved category contributes its own unambiguous slug words.
    for slug in intent.brand_slugs:
        name = getattr(vocab, "brand_names", {}).get(slug)
        if name:
            required.extend(t.lower() for t in _slug_tokens(name))
    for slug in intent.category_slugs:
        required.extend(
            t for t in _slug_tokens(slug) if t not in search_service.GENERIC_TAXONOMY_TOKENS
        )
    if not required:
        required = [
            t for t in tokens
            if t not in search_service.STOPWORDS and t not in search_service.COUNTRY_ALIASES
        ] or list(tokens)

    seen: set[str] = set()
    ordered: list[str] = []
    for token in expanded + required:
        if token not in seen:
            seen.add(token)
            ordered.append(token)
    return ordered[:14], list(dict.fromkeys(required))[:6]


def _slug_tokens(value: str) -> list[str]:
    import re

    return [t for t in re.split(r"[^a-z0-9]+", (value or "").lower()) if t]


def base_statement(*, expired: bool = False) -> Select:
    stmt = select(Offer).options(*OFFER_LOAD_OPTIONS)
    return stmt.where(expired_condition() if expired else live_condition())


def get_offer_by_slug(session: Session, slug: str) -> Offer | None:
    stmt = (
        select(Offer)
        .options(
            selectinload(Offer.category),
            selectinload(Offer.brand),
            selectinload(Offer.countries),
            selectinload(Offer.prices),
            selectinload(Offer.eligibility),
            selectinload(Offer.alternatives),
            selectinload(Offer.verifications),
            selectinload(Offer.source),
        )
        .where(Offer.slug == slug)
    )
    return session.execute(stmt).scalar_one_or_none()


def get_offer_by_id(session: Session, offer_id: str) -> Offer | None:
    stmt = select(Offer).options(*OFFER_LOAD_OPTIONS).where(Offer.id == offer_id)
    return session.execute(stmt).scalar_one_or_none()


# -------------------------------------------------------------- collections
def trending_offers(session: Session, limit: int = 12, *, type_filter: list[str] | None = None) -> list[Offer]:
    stmt = base_statement()
    if type_filter:
        stmt = stmt.where(Offer.offer_type.in_(type_filter))
    stmt = (
        stmt.order_by(Offer.trending_rank.asc().nulls_last())
        .order_by(
            # recency-weighted popularity
            (
                Offer.click_count * 3
                + Offer.bookmark_count * 5
                + Offer.view_count
            ).desc()
        )
        .limit(limit)
    )
    return list(session.execute(stmt).scalars().unique().all())


def ending_soon(session: Session, limit: int = 12, days: int = 3) -> list[Offer]:
    now = utcnow()
    stmt = (
        base_statement()
        .where(Offer.expires_at.isnot(None), Offer.expires_at > now, Offer.expires_at <= now + timedelta(days=days))
        .order_by(Offer.expires_at.asc())
        .limit(limit)
    )
    return list(session.execute(stmt).scalars().unique().all())


def recently_added(session: Session, limit: int = 12) -> list[Offer]:
    stmt = base_statement().order_by(Offer.published_at.desc()).limit(limit)
    return list(session.execute(stmt).scalars().unique().all())


def featured_offers(session: Session, limit: int = 8) -> list[Offer]:
    stmt = (
        base_statement()
        .where(Offer.is_featured.is_(True))
        .order_by(Offer.quality_score.desc(), Offer.published_at.desc())
        .limit(limit)
    )
    return list(session.execute(stmt).scalars().unique().all())


def handpicked_offers(session: Session, limit: int = 8) -> list[Offer]:
    stmt = (
        base_statement()
        .where(Offer.is_handpicked.is_(True))
        .order_by(Offer.quality_score.desc())
        .limit(limit)
    )
    return list(session.execute(stmt).scalars().unique().all())


def highest_value_offers(session: Session, limit: int = 8) -> list[Offer]:
    stmt = (
        base_statement()
        .where(
            or_(
                Offer.savings_value >= 50,
                Offer.credits_amount.isnot(None),
                and_(Offer.promo_price.isnot(None), Offer.promo_price <= 0),
                Offer.is_genuinely_free.is_(True),
            )
        )
        .order_by(Offer.savings_value.desc(), Offer.quality_score.desc())
        .limit(limit)
    )
    return list(session.execute(stmt).scalars().unique().all())


def recently_expired(session: Session, limit: int = 12) -> list[Offer]:
    now = utcnow()
    stmt = (
        select(Offer)
        .options(*OFFER_LOAD_OPTIONS)
        .where(
            or_(
                Offer.status == OfferStatus.EXPIRED.value,
                and_(
                    Offer.expires_at.isnot(None),
                    Offer.expires_at <= now,
                    Offer.published_at.isnot(None),
                ),
            )
        )
        .order_by(Offer.expires_at.desc())
        .limit(limit)
    )
    return list(session.execute(stmt).scalars().unique().all())


def related_offers(
    session: Session,
    offer: Offer,
    limit: int = 8,
    *,
    offer_type: str | None = None,
    exclude_ids: Sequence[str] = (),
) -> list[Offer]:
    """Same brand first, then same category, then comparable savings."""
    clauses = [Offer.id != offer.id, Offer.id.notin_(list(exclude_ids) or [offer.id])]
    filters = [Offer.status == OfferStatus.PUBLISHED.value, *clauses]
    if offer.expires_at:
        filters.append(or_(Offer.expires_at.is_(None), Offer.expires_at > utcnow()))

    scoring = case(
        (Offer.brand_id == offer.brand_id, 60.0),
        (Offer.category_id == offer.category_id, 40.0),
        else_=10.0,
    )
    if offer_type:
        scoring = case((Offer.offer_type == offer_type, 80.0), else_=scoring)
    scoring = scoring + (Offer.savings_percent / 100.0) + Offer.popularity_score / 1000.0

    stmt = (
        select(Offer)
        .options(*OFFER_LOAD_OPTIONS)
        .where(and_(*filters))
        .order_by(scoring.desc(), Offer.savings_value.desc())
        .limit(limit)
    )
    return list(session.execute(stmt).scalars().unique().all())


def free_alternatives_for(session: Session, offer: Offer, limit: int = 4) -> list[Offer]:
    """Genuinely free options in the same category (offer.offer_type = FREE)."""
    stmt = (
        select(Offer)
        .options(*OFFER_LOAD_OPTIONS)
        .where(
            live_condition(),
            Offer.category_id == offer.category_id,
            Offer.id != offer.id,
            Offer.offer_type == OfferType.FREE.value,
        )
        .order_by(Offer.quality_score.desc(), Offer.popularity_score.desc())
        .limit(limit)
    )
    return list(session.execute(stmt).scalars().unique().all())


# ------------------------------------------------------------------ facets
def build_facets(session: Session, filters: OfferFilterParams) -> FacetResponse:
    """Counts for the filter sidebar, computed against the *other* filters."""
    now = utcnow()

    type_counts = dict(
        session.execute(
            select(Offer.offer_type, func.count(Offer.id))
            .where(*_sub_conditions(filters, now, skip="type"))
            .group_by(Offer.offer_type)
        ).all()
    )
    cat_stmt = (
        select(Category.slug, Category.name, func.count(Offer.id))
        .join(Offer, Offer.category_id == Category.id)
        .where(*_sub_conditions(filters, now, skip="category"))
        .group_by(Category.slug, Category.name)
        .order_by(func.count(Offer.id).desc())
        .limit(24)
    )
    categories = [
        FacetBucket(value=slug, label=name, count=count)
        for slug, name, count in session.execute(cat_stmt).all()
    ]

    brand_stmt = (
        select(Brand.slug, Brand.name, func.count(Offer.id))
        .join(Offer, Offer.brand_id == Brand.id)
        .where(*_sub_conditions(filters, now, skip="brand"))
        .group_by(Brand.slug, Brand.name)
        .order_by(func.count(Offer.id).desc())
        .limit(24)
    )
    brands = [
        FacetBucket(value=slug, label=name, count=count)
        for slug, name, count in session.execute(brand_stmt).all()
    ]

    from app.models.offer import OfferCountry

    country_stmt = (
        select(Country.code, Country.name, func.count(func.distinct(OfferCountry.offer_id)))
        .join(OfferCountry, OfferCountry.country_code == Country.code)
        .join(Offer, Offer.id == OfferCountry.offer_id)
        .where(Offer.status == OfferStatus.PUBLISHED.value, OfferCountry.is_available.is_(True))
        .group_by(Country.code, Country.name)
        .order_by(func.count(func.distinct(OfferCountry.offer_id)).desc())
        .limit(24)
    )
    countries = [
        FacetBucket(value=code, label=name, count=count, extra={"flag": flag})
        for code, name, count, flag in session.execute(
            country_stmt.add_columns(Country.flag_emoji)
        ).all()
    ]

    max_row = session.execute(
        select(func.max(Offer.savings_value), func.min(Offer.promo_price)).where(
            live_condition(now)
        )
    ).one()

    return FacetResponse(
        categories=categories,
        brands=brands,
        offer_types=[
            FacetBucket(value=t.value, label=_TYPE_LABELS.get(t.value, t.value.title().replace("_", " ")),
                        count=int(type_counts.get(t.value, 0)))
            for t in OfferType
            if type_counts.get(t.value)
        ],
        countries=countries,
        durations=[
            FacetBucket(value="instant", label="Instant / ongoing", count=_duration_count(session, "instant", filters, now)),
            FacetBucket(value="week", label="Up to 1 week", count=_duration_count(session, "week", filters, now)),
            FacetBucket(value="month", label="1 month", count=_duration_count(session, "month", filters, now)),
            FacetBucket(value="quarter", label="3 months", count=_duration_count(session, "quarter", filters, now)),
            FacetBucket(value="year", label="12 months", count=_duration_count(session, "year", filters, now)),
            FacetBucket(
                value="lifetime",
                label="Ongoing / lifetime",
                count=int(
                    session.execute(
                        select(func.count(Offer.id)).where(*_sub_conditions(filters, now, skip="duration"))
                    ).scalar()
                    or 0
                ),
            ),
        ],
        max_savings=float(max_row[0] or 0),
        max_price=float(max_row[1]) if max_row[1] is not None else None,
    )


def _duration_count(
    session: Session, bucket: str, filters: OfferFilterParams, now: datetime
) -> int:
    low, high = DURATION_RANGES[bucket]
    return int(
        session.execute(
            select(func.count(Offer.id)).where(
                *_sub_conditions(filters, now, skip="duration"),
                Offer.trial_days.isnot(None),
                Offer.trial_days >= low,
                Offer.trial_days <= high,
            )
        ).scalar()
        or 0
    )


def _sub_conditions(filters: OfferFilterParams, now: datetime, *, skip: str) -> list[Any]:
    """Conditions for facet counting — all filters except the faceted dimension."""
    clone = filters.model_copy(deep=True)
    if skip == "category":
        clone.category = []
    elif skip == "brand":
        clone.brand = []
    elif skip == "type":
        clone.type = []
    elif skip == "duration":
        clone.duration = None
    tmp = OfferFilterParams(**clone.model_dump(exclude={"q", "sort", "page", "page_size"}))
    stmt = apply_filters(select(Offer.id), tmp, now=now)
    # Always scope facets to live offers, even when no other filter is set.
    conditions: list[Any] = [live_condition(now)]
    whereclause = stmt.whereclause
    if whereclause is not None:
        # `whereclause` is a BooleanClauseList only when several conditions
        # were combined; a single filter produces a bare expression.
        conditions.extend(getattr(whereclause, "clauses", [whereclause]))
    return conditions


_TYPE_LABELS = {
    "free": "Free",
    "free_trial": "Free trial",
    "freemium": "Freemium",
    "free_credits": "Free credits",
    "discount": "Discount",
    "coupon": "Coupon code",
    "cashback": "Cashback",
    "free_alternative": "Free alternative",
}


def type_label(value: str) -> str:
    return _TYPE_LABELS.get(value, value.replace("_", " ").title())


def slugify_offer(title: str, brand: str | None, offer_type: str) -> str:
    from app.core.security import slugify

    base = f"{brand}-{title}" if brand else title
    suffix = {"free_trial": "free-trial", "free_credits": "free-credits"}.get(offer_type, "")
    slug = slugify(f"{base} {suffix}".strip(), max_length=150)
    return re_sub_dashes(slug)


def re_sub_dashes(value: str) -> str:
    while "--" in value:
        value = value.replace("--", "-")
    return value.strip("-")


def unique_slug(session: Session, base: str) -> str:
    from app.core.security import slugify

    slug = re_sub_dashes(slugify(base, max_length=150))
    if not slug:
        slug = f"offer-{utcnow().timestamp():.0f}"
    candidate = slug
    suffix = 2
    while session.execute(select(Offer.id).where(Offer.slug == candidate)).first():
        candidate = f"{slug}-{suffix}"
        suffix += 1
    return candidate


def compute_savings(offer: Offer) -> tuple[float, int]:
    """(absolute savings, percentage) — authoritative for both paths."""
    from app.core.money import savings_percent

    original = float(offer.original_price) if offer.original_price is not None else None
    promo = float(offer.promo_price) if offer.promo_price is not None else None
    if promo == 0 and offer.offer_type in (OfferType.FREE.value, OfferType.FREE_CREDITS.value):
        original = original or 0
    if promo is None:
        if offer.offer_type == OfferType.FREE.value and offer.credits_amount is None:
            promo = 0.0
            original = original or 0.0
        else:
            return float(offer.savings_value or 0), int(offer.savings_percent or 0)
    percent = savings_percent(original, promo) or 0
    if original is not None and promo is not None and promo <= original:
        value = round(original - promo, 2)
    else:
        value = float(offer.savings_value or 0)
    return value, percent