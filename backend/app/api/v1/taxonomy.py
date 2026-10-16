"""Taxonomy endpoints: categories, brands, countries, interests."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query
from sqlalchemy import and_, func, select

from app.api.deps import CurrencyDep, PaginationDep, SessionDep
from app.api.cache_sync import cache_get, cache_put
from app.core.cache import cache
from app.db.base import utcnow
from app.models.offer import Offer, OfferCountry
from app.models.taxonomy import Brand, Category, Country
from app.schemas.offer import BrandBrief, CategoryBrief, CategoryOut, CountryBrief, OfferCard
from app.services.offers import base_statement, fetch_page
from app.services.recommendations import available_interests
from app.services.serializers import category_brief, serialize_card

router = APIRouter(tags=["taxonomy"])


@router.get("/categories", response_model=list[CategoryOut], summary="All active categories")
def list_categories(session: SessionDep) -> list[CategoryOut]:
    key = cache.make_key("categories", namespace="taxonomy")
    cached = cache_get(key)
    if cached is not None:
        return [CategoryOut(**item) for item in cached]

    now = utcnow()
    # Outer join so brand-new (or temporarily empty) categories still appear —
    # hiding them would make them impossible to populate from the UI.
    rows = session.execute(
        select(Category, func.count(Offer.id))
        .join(Offer, and_(Offer.category_id == Category.id, Offer.status == "published"), isouter=True)
        .where(Category.is_active.is_(True))
        .group_by(Category.id)
        .order_by(Category.sort_order.asc(), Category.name.asc())
    ).all()

    out: list[CategoryOut] = []
    for category, count in rows:
        brief = category_brief(category)
        brief.offer_count = int(count)
        brief.live_offer_count = int(count)
        out.append(
            CategoryOut(
                **brief.model_dump(),
                description=category.description,
                group_name=category.group_name,
                seo_title=category.seo_title,
                seo_description=category.seo_description,
                keywords=list(category.keywords or []),
            )
        )
    cache_put(key, [item.model_dump(mode="json") for item in out], ttl=600)
    return out


@router.get("/categories/{slug}", response_model=CategoryOut, summary="Category detail")
def get_category(session: SessionDep, slug: Annotated[str, Path(max_length=120)]) -> CategoryOut:
    category = session.execute(
        select(Category).where(Category.slug == slug, Category.is_active.is_(True))
    ).scalars().first()
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")

    now = utcnow()
    count = int(
        session.execute(
            select(func.count(Offer.id)).where(
                Offer.category_id == category.id,
                Offer.status == "published",
                (Offer.expires_at.is_(None)) | (Offer.expires_at > now),
            )
        ).scalar()
        or 0
    )
    brief = category_brief(category)
    brief.offer_count = count
    brief.live_offer_count = count
    return CategoryOut(
        **brief.model_dump(),
        description=category.description,
        group_name=category.group_name,
        seo_title=category.seo_title,
        seo_description=category.seo_description,
        keywords=list(category.keywords or []),
    )


@router.get("/categories/{slug}/offers", response_model=list[OfferCard], summary="Offers in a category")
def category_offers(
    session: SessionDep,
    currency: CurrencyDep,
    slug: Annotated[str, Path(max_length=120)],
    pagination: PaginationDep,
    sort: str = "popular",
) -> list[OfferCard]:
    from app.schemas.offer import OfferFilterParams

    filters = OfferFilterParams(
        category=[slug], sort=sort, page=pagination.page, page_size=pagination.page_size  # type: ignore[arg-type]
    )
    rows, _ = _run_category_query(session, filters)
    return [serialize_card(o, currency=currency) for o in rows]


def _run_category_query(session, filters):
    from app.services.offers import run_query

    return run_query(session, filters)


@router.get("/brands", response_model=list[BrandBrief], summary="Brands with live offers")
def list_brands(
    session: SessionDep,
    pagination: PaginationDep,
    q: Annotated[str | None, Query(max_length=100)] = None,
) -> list[BrandBrief]:
    stmt = (
        select(Brand, func.count(Offer.id))
        .join(Offer, Offer.brand_id == Brand.id)
        .where(Brand.is_active.is_(True), Offer.status == "published")
    )
    if q:
        stmt = stmt.where(func.lower(Brand.name).like(f"%{q.lower()}%"))
    stmt = (
        stmt.group_by(Brand.id)
        .order_by(func.count(Offer.id).desc(), Brand.name.asc())
        .offset((pagination.page - 1) * pagination.page_size)
        .limit(pagination.page_size)
    )
    rows = session.execute(stmt).all()
    out: list[BrandBrief] = []
    for brand, count in rows:
        brief = BrandBrief(
            id=brand.id,
            slug=brand.slug,
            name=brand.name,
            domain=brand.domain,
            logo_url=brand.logo_url,
            accent_color=brand.accent_color,
            is_verified=brand.is_verified,
        )
        brief.offer_count = int(count)
        out.append(brief)
    return out


@router.get("/brands/{slug}", summary="Brand detail")
def get_brand(session: SessionDep, slug: Annotated[str, Path(max_length=120)]) -> dict:
    brand = session.execute(
        select(Brand).where(Brand.slug == slug)
    ).scalars().first()
    if brand is None:
        raise HTTPException(status_code=404, detail="Brand not found")
    count = int(
        session.execute(
            select(func.count(Offer.id)).where(Offer.brand_id == brand.id, Offer.status == "published")
        ).scalar()
        or 0
    )
    brief = BrandBrief(
        id=brand.id,
        slug=brand.slug,
        name=brand.name,
        domain=brand.domain,
        logo_url=brand.logo_url,
        accent_color=brand.accent_color,
        is_verified=brand.is_verified,
        offer_count=count,
    )
    return {
        **brief.model_dump(),
        "website_url": brand.website_url,
        "description": brand.description,
        "aliases": brand.aliases or [],
        "category_id": brand.category_id,
        "country_code": brand.country_code,
    }


@router.get("/brands/{slug}/offers", response_model=list[OfferCard], summary="Offers for a brand")
def brand_offers(
    session: SessionDep,
    currency: CurrencyDep,
    slug: Annotated[str, Path(max_length=120)],
    pagination: PaginationDep,
) -> list[OfferCard]:
    from app.schemas.offer import OfferFilterParams
    from app.services.offers import run_query

    filters = OfferFilterParams(
        brand=[slug], sort="popular", page=pagination.page, page_size=pagination.page_size
    )
    rows, _ = run_query(session, filters)
    return [serialize_card(o, currency=currency) for o in rows]


@router.get("/countries", response_model=list[CountryBrief], summary="Supported countries")
def list_countries(session: SessionDep) -> list[CountryBrief]:
    rows = session.execute(
        select(Country, func.count(func.distinct(OfferCountry.offer_id)))
        .join(OfferCountry, OfferCountry.country_code == Country.code)
        .group_by(Country.id)
        .order_by(Country.sort_order.asc(), Country.name.asc())
    ).all()
    return [
        CountryBrief(
            code=country.code,
            name=country.name,
            slug=country.slug,
            flag_emoji=country.flag_emoji,
            currency=country.currency,
            region=country.region,
            offer_count=int(count),
        )
        for country, count in rows
    ]


@router.get("/currencies", summary="Supported display currencies")
def list_currencies() -> dict:
    from app.core.money import USD_RATES, symbol_for

    return {
        "base": "USD",
        "currencies": [
            {"code": code, "symbol": symbol_for(code), "per_usd": rate}
            for code, rate in sorted(USD_RATES.items())
        ],
        "note": "Converted prices are indicative; the official checkout page is authoritative.",
    }


@router.get("/interests", summary="Personalisation interest tags")
def list_interests() -> list[dict]:
    return available_interests()


@router.get("/offer-types", summary="Offer type taxonomy with live counts")
def offer_types(session: SessionDep) -> list[dict]:
    from app.models.enums import OfferType
    from app.services.offers import type_label

    counts = dict(
        session.execute(
            select(Offer.offer_type, func.count(Offer.id))
            .where(Offer.status == "published")
            .group_by(Offer.offer_type)
        ).all()
    )
    return [
        {
            "value": value.value,
            "label": type_label(value.value),
            "count": int(counts.get(value.value, 0)),
        }
        for value in OfferType
    ]