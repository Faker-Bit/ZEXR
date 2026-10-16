"""Search endpoints: autocomplete, full search, intent introspection."""

from __future__ import annotations

import sys
import time
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query, Request, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import CountryDep, CurrencyDep, CurrentUser, SessionDep
from app.core.logging import get_logger
from app.core.money import public_currency
from app.core.ratelimit import limit
from app.models.offer import Offer, OfferCountry
from app.models.taxonomy import Brand, Category, Country
from app.schemas.offer import (
    OfferFilterParams,
    ParsedIntent,
    SearchResponse,
    SearchSuggestion,
    SortOption,
)
from app.services import offers as offer_service
from app.services import search as search_service
from app.services.serializers import serialize_card

log = get_logger("search")
router = APIRouter(tags=["search"])


@router.get("/search/suggest", response_model=list[SearchSuggestion], summary="Autocomplete")
@limit("120/minute")
def suggest(
    request: Request,
    response: Response,
    session: SessionDep,
    q: Annotated[str, Query(max_length=200)],
    limit: int = 8,
) -> list[SearchSuggestion]:
    if len(q.strip()) < 1:
        return []
    return search_service.suggest(session, q, limit=limit)


@router.get("/search/parse", response_model=ParsedIntent, summary="Explain how a query is interpreted")
def parse(session: SessionDep, q: Annotated[str, Query(max_length=300)]) -> ParsedIntent:
    vocab = search_service.get_vocabulary(session)
    return search_service.parse_intent(q, vocab)


@router.get("/search", response_model=SearchResponse, summary="Full search with filters")
@limit("90/minute")
def search(
    request: Request,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
    currency: CurrencyDep,
    country: CountryDep,
    q: Annotated[str, Query(max_length=300)] = "",
    category: Annotated[list[str] | None, Query()] = None,
    brand: Annotated[list[str] | None, Query()] = None,
    type: Annotated[list[str] | None, Query()] = None,
    country_codes: Annotated[list[str] | None, Query()] = None,
    min_savings: Annotated[float | None, Query(ge=0)] = None,
    max_price: Annotated[float | None, Query(ge=0)] = None,
    duration: Annotated[str | None, Query()] = None,
    requires_payment_method: bool | None = None,
    requires_student_id: bool | None = None,
    verified_only: bool | None = None,
    global_only: bool | None = None,
    ending_within_days: Annotated[int | None, Query(ge=0, le=365)] = None,
    sort: SortOption = "relevance",
    page: Annotated[int, Query(ge=1, le=200)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 24,
) -> SearchResponse:
    started = time.perf_counter()

    vocab = search_service.get_vocabulary(session)
    intent = search_service.parse_intent(q, vocab)
    correction: str | None = None
    correction_applied = False
    corrected_query: str | None = None

    filters = OfferFilterParams(
        q=q,
        category=category or [],
        brand=brand or [],
        type=type or [],  # type: ignore[arg-type]
        country=country_codes or [],
        min_savings=min_savings,
        max_price=max_price,
        duration=duration,  # type: ignore[arg-type]
        requires_payment_method=requires_payment_method,
        requires_student_id=requires_student_id,
        verified_only=verified_only,
        global_only=global_only,
        ending_within_days=ending_within_days,
        sort=sort,
        page=page,
        page_size=page_size,
    )
    rows, total = offer_service.run_query(session, filters)

    # Typo tolerance: if the raw query found nothing but a corrected spelling
    # does, serve the corrected results and tell the user what happened.
    if total == 0 and q.strip():
        candidate = search_service.did_you_mean(q, vocab)
        if candidate and candidate.lower() != q.strip().lower():
            retry = filters.model_copy(deep=True)
            retry.q = candidate
            retry_rows, retry_total = offer_service.run_query(session, retry)
            correction = candidate
            if retry_total > 0:
                rows, total = retry_rows, retry_total
                corrected_query = candidate
                correction_applied = True

    cards = [
        serialize_card(o, currency=public_currency(currency), country_code=country)
        for o in rows
    ]

    suggestions = search_service.suggest(session, q, limit=6) if q.strip() else []

    took_ms = round((time.perf_counter() - started) * 1000, 2)

    try:
        search_service.record_search(
            session,
            query=q,
            intent=intent,
            result_count=total,
            took_ms=took_ms,
            user_id=user.id if user else None,
            country_code=country,
            filters=filters.model_dump(mode="json", exclude={"q"}),
        )
        from app.services import analytics

        analytics.record_event(
            session,
            "search",
            path="/search",
            country_code=country,
            value=float(total),
            properties={"query": q[:200], "intent": intent.intent, "took_ms": took_ms},
        )
        session.commit()
    except Exception:
        session.rollback()

    
    return SearchResponse(
        query=corrected_query if correction_applied and corrected_query else q,
        intent=intent,
        results=cards,
        suggestions=suggestions,
        corrections=[correction] if correction else [],
        facets=facet_dicts(session, filters),
        total=total,
        page=page,
        page_size=page_size,
        pages=max(1, (total + page_size - 1) // page_size),
        took_ms=took_ms,
        did_you_mean=correction,

    )


def facet_dicts(session: Session, filters: OfferFilterParams) -> dict[str, dict[str, int]]:
    if not filters.q:
        return {}
    try:
        facets = offer_service.build_facets(session, filters)
    except Exception:
        # Facets are an enhancement — never fail a search because of them.
        log.warning("search.facets_failed", error=str(sys.exc_info()[1]), exc_info=True)
        return {}

    def _to_dict(buckets: Any) -> dict[str, int]:
        return {b.value: b.count for b in buckets}

    return {
        "categories": _to_dict(facets.categories),
        "brands": _to_dict(facets.brands),
        "offer_types": _to_dict(facets.offer_types),
        "countries": _to_dict(facets.countries),
    }


@router.get("/search/trending", summary="Trending searches")
def trending(
    session: SessionDep, limit: Annotated[int, Query(ge=1, le=50)] = 12
) -> list[dict]:
    from datetime import timedelta

    from app.db.base import utcnow
    from app.models.analytics import SearchQueryLog

    since = utcnow() - timedelta(days=7)
    rows = session.execute(
        select(
            SearchQueryLog.query,
            func.count(SearchQueryLog.id),
            func.sum(SearchQueryLog.result_count),
        )
        .where(SearchQueryLog.created_at >= since, SearchQueryLog.result_count > 0)
        .group_by(SearchQueryLog.query)
        .order_by(func.count(SearchQueryLog.id).desc())
        .limit(limit)
    ).all()
    return [
        {"query": query, "searches": int(count), "results": int(results or 0)}
        for query, count, results in rows
    ]


@router.get("/search/related-categories", summary="Categories that match a partial query")
def related_categories(
    session: SessionDep, q: Annotated[str, Query(max_length=120)]
) -> list[dict]:
    if len(q) < 2:
        return []
    like = f"%{q.lower()}%"
    rows = session.execute(
        select(Category, func.count(Offer.id))
        .join(Offer, Offer.category_id == Category.id)
        .where(Category.is_active.is_(True), func.lower(Category.name).like(like))
        .group_by(Category.id)
        .limit(6)
    ).all()
    return [
        {
            "slug": category.slug,
            "name": category.name,
            "icon": category.icon,
            "tagline": category.tagline,
            "offer_count": int(count),
        }
        for category, count in rows
    ]


@router.get("/search/brands", summary="Brand lookup")
def brand_lookup(
    session: SessionDep,
    prefix: Annotated[str, Query(max_length=120)],
    limit: int = 10,
) -> list[dict]:
    like = f"%{prefix.lower()}%"
    rows = session.execute(
        select(Brand, func.count(Offer.id))
        .join(Offer, Offer.brand_id == Brand.id)
        .where(Brand.is_active.is_(True), func.lower(Brand.name).like(like))
        .group_by(Brand.id)
        .order_by(func.count(Offer.id).desc())
        .limit(limit)
    ).all()
    return [
        {
            "slug": brand.slug,
            "name": brand.name,
            "domain": brand.domain,
            "logo_url": brand.logo_url,
            "offer_count": int(count),
        }
        for brand, count in rows
    ]


@router.get("/search/availability", summary="Which countries an offer is available in")
def availability(session: SessionDep, slug: str) -> dict:
    offer = offer_service.get_offer_by_slug(session, slug)
    if offer is None:
        raise HTTPException(status_code=404, detail="Offer not found")
    rows = session.execute(
        select(Country, OfferCountry.is_available)
        .join(OfferCountry, OfferCountry.country_code == Country.code)
        .where(OfferCountry.offer_id == offer.id)
    ).all()
    return {
        "slug": offer.slug,
        "is_global": offer.is_global,
        "excluded_countries": offer.excluded_countries or [],
        "countries": [
            {"code": c.code, "name": c.name, "flag": c.flag_emoji, "available": bool(available)}
            for c, available in rows
        ],
        "eligibility": offer.eligibility_types or [],
        "requires_payment_method": offer.requires_payment_method,
    }