"""Public offer endpoints: directory, detail, collections, homepage bundle."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Path, Query, Request, status
from sqlalchemy import func, select

from app.api.cache_sync import _sync_cache_get, _sync_cache_put
from app.api.deps import (
    CountryDep,
    CurrencyDep,
    CurrentUser,
    PaginationDep,
    SessionDep,
    bookmarked_offer_ids,
)
from app.core.cache import cache
from app.core.money import public_currency
from app.db.base import utcnow
from app.models.enums import OfferStatus, OfferType, VerificationStatus
from app.models.offer import Offer, OfferVerification
from app.models.taxonomy import Category
from app.schemas.common import Page
from app.schemas.offer import FacetResponse, OfferCard, OfferDetail, OfferFilterParams, SortOption
from app.services import offers as offer_service
from app.services import recommendations
from app.services.serializers import serialize_card, serialize_detail

router = APIRouter(tags=["offers"])


def _viewer(
    session,
    user,
    currency: str,
    country: str | None,
    offers: list[Offer],
    relevance: dict[str, float] | None = None,
) -> list[OfferCard]:
    ids = bookmarked_offer_ids(session, user, [o.id for o in offers])
    cards: list[OfferCard] = []
    for offer in offers:
        score = (relevance or {}).get(offer.id)
        cards.append(
            serialize_card(
                offer,
                currency=public_currency(currency),
                country_code=country,
                bookmarked_ids=ids,
                relevance=score,
            )
        )
    return cards


# ------------------------------------------------------------- directory
@router.get("/offers", response_model=Page[OfferCard], summary="Browse the offers directory")
def list_offers(
    session: SessionDep,
    pagination: PaginationDep,
    user: CurrentUser,
    country: CountryDep,
    currency: CurrencyDep,
    q: Annotated[str | None, Query(max_length=200)] = None,
    category: Annotated[list[str] | None, Query()] = None,
    brand: Annotated[list[str] | None, Query()] = None,
    type: Annotated[list[OfferType] | None, Query()] = None,
    countries: Annotated[list[str] | None, Query(alias="country_codes")] = None,
    currency_filter: Annotated[list[str] | None, Query(alias="currencies")] = None,
    min_savings: Annotated[float | None, Query(ge=0)] = None,
    max_price: Annotated[float | None, Query(ge=0)] = None,
    min_trial_days: Annotated[int | None, Query(ge=0, le=3650)] = None,
    duration: Annotated[str | None, Query()] = None,
    requires_payment_method: bool | None = None,
    requires_student_id: bool | None = None,
    new_users_only: bool | None = None,
    verified_only: bool | None = None,
    global_only: bool | None = None,
    ending_within_days: Annotated[int | None, Query(ge=0, le=365)] = None,
    sort: SortOption = "newest",
) -> Page[OfferCard]:
    filters = OfferFilterParams(
        q=q,
        category=category or [],
        brand=brand or [],
        type=type or [],
        country=countries or ([] if not country else [country]),
        currency=currency_filter or [],
        min_savings=min_savings,
        max_price=max_price,
        min_trial_days=min_trial_days,
        duration=duration,  # type: ignore[arg-type]
        requires_payment_method=requires_payment_method,
        requires_student_id=requires_student_id,
        new_users_only=new_users_only,
        verified_only=verified_only,
        global_only=global_only,
        ending_within_days=ending_within_days,
        sort=sort,
        page=pagination.page,
        page_size=pagination.page_size,
    )
    rows, total = offer_service.run_query(session, filters)
    cards = _viewer(session, user, currency, country, rows)
    return Page.build(cards, total, pagination.page, pagination.page_size)


@router.get("/offers/facets", response_model=FacetResponse, summary="Filter facets for the current query")
def offer_facets(
    session: SessionDep,
    q: Annotated[str | None, Query(max_length=200)] = None,
    category: Annotated[list[str] | None, Query()] = None,
    brand: Annotated[list[str] | None, Query()] = None,
    type: Annotated[list[OfferType] | None, Query()] = None,
    sort: SortOption = "newest",
) -> FacetResponse:
    filters = OfferFilterParams(
        q=q,
        category=category or [],
        brand=brand or [],
        type=type or [],
        sort=sort,
    )
    return offer_service.build_facets(session, filters)


@router.get("/offers/{slug}", response_model=OfferDetail, summary="Offer detail page")
def get_offer(
    session: SessionDep,
    user: CurrentUser,
    currency: CurrencyDep,
    country: CountryDep,
    slug: Annotated[str, Path(max_length=200)],
    request: Request = None,  # type: ignore[assignment]
) -> OfferDetail:
    offer = offer_service.get_offer_by_slug(session, slug)
    if offer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Offer not found")
    if offer.status not in (
        OfferStatus.PUBLISHED.value,
        OfferStatus.EXPIRED.value,
        OfferStatus.DISPUTED.value,
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Offer not found")

    similar = offer_service.related_offers(session, offer, limit=8)
    alternatives = offer_service.free_alternatives_for(session, offer, limit=4)
    detail = serialize_detail(
        offer,
        currency=public_currency(currency),
        country_code=country,
        bookmarked_ids=bookmarked_offer_ids(session, user, [offer.id]),
        similar=similar,
        free_alternatives=alternatives,
    )

    from app.services import analytics

    try:
        analytics.record_offer_view(
            session, offer, user_id=user.id if user else None, country_code=country
        )
        if user is not None:
            _track_recent_view(session, user, offer)
        session.commit()
    except Exception:  # analytics must never break a page render
        session.rollback()
    return detail


def _track_recent_view(session, user, offer: Offer) -> None:
    from app.models.user import RecentView

    row = session.execute(
        select(RecentView).where(RecentView.user_id == user.id, RecentView.offer_id == offer.id)
    ).scalar_one_or_none()
    if row:
        row.viewed_at = utcnow()
        row.view_count = (row.view_count or 1) + 1
    else:
        session.add(RecentView(user_id=user.id, offer_id=offer.id))
    # keep only the most recent 50
    from app.models.user import RecentView as RV

    old = session.execute(
        select(RV.id)
        .where(RV.user_id == user.id)
        .order_by(RV.viewed_at.desc())
        .offset(50)
    ).all()
    if old:
        session.query(RV).filter(RV.id.in_([r[0] for r in old])).delete(synchronize_session=False)


@router.get("/offers/{slug}/verification", summary="Verification history for an offer")
def offer_verification_history(
    session: SessionDep,
    slug: Annotated[str, Path(max_length=200)],
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
) -> dict:
    offer = offer_service.get_offer_by_slug(session, slug)
    if offer is None:
        raise HTTPException(status_code=404, detail="Offer not found")
    rows = session.execute(
        select(OfferVerification)
        .where(OfferVerification.offer_id == offer.id)
        .order_by(OfferVerification.checked_at.desc())
        .limit(limit)
    ).scalars().all()
    return {
        "offer_slug": offer.slug,
        "verification_status": offer.verification_status,
        "last_checked_at": offer.last_checked_at,
        "consecutive_failures": offer.consecutive_failures,
        "history": [
            {
                "id": row.id,
                "result": row.result,
                "http_status": row.http_status,
                "final_url": row.final_url,
                "checked_at": row.checked_at,
                "method": row.method,
                "price_found": float(row.price_found) if row.price_found is not None else None,
                "message": row.message,
            }
            for row in rows
        ],
    }


# ------------------------------------------------------------ collections
@router.get("/home", summary="Homepage bundle in a single request")
def home_bundle(
    session: SessionDep,
    user: CurrentUser,
    country: CountryDep,
    currency: CurrencyDep,
    limit: Annotated[int, Query(ge=1, le=24)] = 8,
) -> dict:
    cur = public_currency(currency)
    cache_key = cache.make_key("home", limit, country or "any", cur, namespace="offers")

    def build() -> dict:
        cards = lambda rows: [  # noqa: E731 - concise local mapper
            serialize_card(o, currency=cur, country_code=country) for o in rows
        ]
        return {
            "trending": cards(offer_service.trending_offers(session, limit)),
            "fresh": cards(offer_service.recently_added(session, limit)),
            "ending_soon": cards(offer_service.ending_soon(session, limit)),
            "featured": cards(offer_service.featured_offers(session, limit)),
            "handpicked": cards(offer_service.handpicked_offers(session, limit)),
            "highest_value": cards(offer_service.highest_value_offers(session, limit)),
            "free_tools": cards(recommendations.free_alternatives(session, limit)),
            "no_card": cards(recommendations.no_card_offers(session, limit)),
            "popular": cards(recommendations.popular_for_country(session, country, limit)),
            "stats": platform_stats(session),
        }

    payload = _sync_cache_get(cache_key)
    if payload is None:
        payload = build()
        _sync_cache_put(cache_key, payload, ttl=90)
    return payload


@router.get("/collections/{name}", response_model=list[OfferCard], summary="Curated collections")
def collection(
    session: SessionDep,
    user: CurrentUser,
    currency: CurrencyDep,
    country: CountryDep,
    name: str,
    limit: Annotated[int, Query(ge=1, le=48)] = 12,
) -> list[OfferCard]:
    cur = public_currency(currency)
    name = name.strip().lower()

    if name == "trending":
        rows = recommendations.trending_now(session, limit)
    elif name == "new":
        rows = recommendations.fresh_offers(session, limit)
    elif name == "ending-soon":
        rows = recommendations.ending_soon(session, limit)
    elif name == "free":
        rows = recommendations.free_alternatives(session, limit)
    elif name == "free-trial":
        rows = _by_type(session, OfferType.FREE_TRIAL, limit)
    elif name == "free-credits":
        rows = _by_type(session, OfferType.FREE_CREDITS, limit)
    elif name == "discounts":
        rows = _by_type(session, OfferType.DISCOUNT, limit)
    elif name == "coupons":
        rows = _by_type(session, OfferType.COUPON, limit)
    elif name == "cashback":
        rows = _by_type(session, OfferType.CASHBACK, limit)
    elif name == "no-card":
        rows = recommendations.no_card_offers(session, limit)
    elif name == "under-10":
        rows = recommendations.under_price_offers(session, limit, 10.0)
    elif name == "verified":
        stmt = (
            offer_service.base_statement()
            .where(Offer.verification_status == VerificationStatus.VERIFIED.value)
            .order_by(Offer.popularity_score.desc())
            .limit(limit)
        )
        rows = list(session.execute(stmt).scalars().unique().all())
    elif name == "student":
        rows = _by_flag(session, "requires_student_id", limit)
    elif name == "india":
        rows = _for_country(session, "IN", limit)
    else:
        raise HTTPException(status_code=404, detail=f"Unknown collection '{name}'")

    return _viewer(session, user, cur, country, rows)


def _by_type(session, offer_type: OfferType, limit: int) -> list[Offer]:
    stmt = (
        offer_service.base_statement()
        .where(Offer.offer_type == offer_type.value)
        .order_by(Offer.popularity_score.desc(), Offer.savings_percent.desc())
        .limit(limit)
    )
    return list(session.execute(stmt).scalars().unique().all())


def _by_flag(session, flag: str, limit: int) -> list[Offer]:
    column = getattr(Offer, flag)
    stmt = (
        offer_service.base_statement()
        .where(column.is_(True))
        .order_by(Offer.popularity_score.desc())
        .limit(limit)
    )
    return list(session.execute(stmt).scalars().unique().all())


def _for_country(session, code: str, limit: int) -> list[Offer]:
    from app.models.offer import OfferCountry

    stmt = (
        offer_service.base_statement()
        .where(
            Offer.id.in_(
                select(OfferCountry.offer_id).where(
                    OfferCountry.country_code == code, OfferCountry.is_available.is_(True)
                )
            )
            | Offer.is_global.is_(True)
        )
        .order_by(Offer.popularity_score.desc())
        .limit(limit)
    )
    return list(session.execute(stmt).scalars().unique().all())


@router.get("/expired", response_model=Page[OfferCard], summary="Recently expired offers")
def expired_offers(
    session: SessionDep,
    user: CurrentUser,
    currency: CurrencyDep,
    country: CountryDep,
    pagination: PaginationDep,
) -> Page[OfferCard]:
    stmt = offer_service.base_statement(expired=True).order_by(Offer.expires_at.desc())
    rows, total = offer_service.fetch_page(session, stmt, pagination.page, pagination.page_size)
    return Page.build(
        _viewer(session, user, public_currency(currency), country, rows),
        total,
        pagination.page,
        pagination.page_size,
    )


@router.get("/platform/stats", summary="Public platform statistics")
def platform_stats(session: SessionDep) -> dict:
    now = utcnow()
    live_stmt = offer_service.live_condition(now)
    total_offers = int(session.execute(select(func.count(Offer.id))).scalar() or 0)
    live = int(session.execute(select(func.count(Offer.id)).where(live_stmt)).scalar() or 0)
    verified = int(
        session.execute(
            select(func.count(Offer.id)).where(
                live_stmt, Offer.verification_status == VerificationStatus.VERIFIED.value
            )
        ).scalar()
        or 0
    )
    free_count = int(
        session.execute(
            select(func.count(Offer.id)).where(live_stmt, Offer.offer_type == OfferType.FREE.value)
        ).scalar()
        or 0
    )
    categories = int(
        session.execute(
            select(func.count(Category.id)).where(Category.is_active.is_(True))
        ).scalar()
        or 0
    )
    total_savings = session.execute(
        select(func.coalesce(func.sum(Offer.savings_value), 0)).where(live_stmt)
    ).scalar()
    ending_soon = int(
        session.execute(
            select(func.count(Offer.id)).where(
                live_stmt,
                Offer.expires_at.isnot(None),
                Offer.expires_at > now,
                Offer.expires_at <= now.replace(microsecond=0),
            )
        ).scalar()
        or 0
    )
    return {
        "total_offers": total_offers,
        "live_offers": live,
        "verified_offers": verified,
        "free_offers": free_count,
        "categories": categories,
        "total_savings": float(total_savings or 0),
        "generated_at": now,
    }
