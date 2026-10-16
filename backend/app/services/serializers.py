"""Model -> schema conversion.

Kept in one place so cards render identically from search, directory, admin and
personalised feeds.  All price maths is done here (never in routes) so display
currency handling stays consistent.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Iterable

from app.core.money import convert, default_currency, format_money, public_currency
from app.models.enums import OfferType, VerificationStatus
from app.models.offer import Offer
from app.models.taxonomy import Brand, Category
from app.schemas.offer import (
    AlternativeOut,
    BrandBrief,
    CategoryBrief,
    EligibilityOut,
    OfferCard,
    OfferDetail,
    PriceOut,
    VerificationOut,
)


def num(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def category_brief(category: Category | None) -> CategoryBrief:
    if category is None:
        return CategoryBrief(
            id="", slug="uncategorised", name="Uncategorised", icon="tag", color="slate"
        )
    return CategoryBrief(
        id=category.id,
        slug=category.slug,
        name=category.name,
        icon=category.icon,
        color=category.color,
        tagline=category.tagline,
        offer_count=getattr(category, "_offer_count", 0) or 0,
        live_offer_count=getattr(category, "_live_offer_count", 0) or 0,
    )


def brand_brief(brand: Brand | None) -> BrandBrief | None:
    if brand is None:
        return None
    return BrandBrief(
        id=brand.id,
        slug=brand.slug,
        name=brand.name,
        domain=brand.domain,
        logo_url=brand.logo_url,
        accent_color=brand.accent_color,
        is_verified=brand.is_verified,
        offer_count=getattr(brand, "_offer_count", 0) or 0,
    )


def _display_prices(offer: Offer, target_currency: str) -> list[PriceOut]:
    """Return the offer's price in the viewer's currency.

    Source of truth is the offer row itself.  We only ever *convert* using the
    FX table — if a pair is unknown we omit the converted figure rather than
    inventing one.
    """
    src = public_currency(offer.currency)
    out: list[PriceOut] = []
    if src == target_currency:
        out.append(
            PriceOut(
                currency=src,
                original_price=num(offer.original_price),
                promo_price=num(offer.promo_price),
                renewal_price=num(offer.renewal_price),
                billing_period=offer.billing_period,
                is_available=True,
                captured_at=offer.last_checked_at,
            )
        )
    else:
        promo = convert(num(offer.promo_price), src, target_currency)
        original = convert(num(offer.original_price), src, target_currency)
        if promo is not None or original is not None:
            out.append(
                PriceOut(
                    currency=target_currency,
                    original_price=original,
                    promo_price=promo,
                    renewal_price=convert(num(offer.renewal_price), src, target_currency),
                    billing_period=offer.billing_period,
                    is_available=True,
                    captured_at=offer.last_checked_at,
                )
            )
    # Any locally captured market prices (e.g. an India-only price) also apply.
    for price in getattr(offer, "prices", []) or []:
        if price.currency == target_currency and (price.country_code is None or not price.is_available):
            out.append(
                PriceOut(
                    currency=price.currency,
                    country_code=price.country_code,
                    original_price=num(price.original_price),
                    promo_price=num(price.promo_price),
                    renewal_price=num(price.renewal_price),
                    billing_period=price.billing_period,
                    is_available=price.is_available,
                    captured_at=price.captured_at,
                )
            )
    return out


def _localised_prices(offer: Offer, currency: str, country_code: str | None) -> tuple[float | None, float | None]:
    """Resolve (original, promo) in the viewer's currency / country."""
    src = public_currency(offer.currency)
    original = num(offer.original_price)
    promo = num(offer.promo_price)

    for price in getattr(offer, "prices", []) or []:
        if price.currency == currency and (price.country_code == country_code or price.country_code is None):
            return num(price.original_price), num(price.promo_price)

    if country_code:
        for link in getattr(offer, "countries", []) or []:
            if link.country_code == country_code and link.is_available is False:
                return original, promo

    if src != currency:
        return convert(original, src, currency), convert(promo, src, currency)
    return original, promo


def serialize_card(
    offer: Offer,
    *,
    currency: str | None = None,
    country_code: str | None = None,
    bookmarked_ids: set[str] | None = None,
    relevance: float | None = None,
    match_reason: str | None = None,
) -> OfferCard:
    currency = public_currency(currency or default_currency())
    original, promo = _localised_prices(offer, currency, country_code)

    savings_percent = offer.savings_percent or 0
    if currency != public_currency(offer.currency) and original and promo is not None:
        savings_percent = int(round((1 - promo / original) * 100)) if original > 0 and promo < original else 0

    country_codes = [link.country_code for link in getattr(offer, "countries", []) or []]

    return OfferCard(
        id=offer.id,
        slug=offer.slug,
        title=offer.title,
        short_description=offer.short_description,
        offer_type=OfferType(offer.offer_type) if offer.offer_type in OfferType._value2member_map_ else OfferType.FREE_TRIAL,
        status=offer.status,
        verification_status=VerificationStatus(offer.verification_status),
        category=category_brief(offer.category),
        brand=brand_brief(offer.brand),
        currency=currency,
        original_price=original,
        promo_price=promo,
        savings_value=num(offer.savings_value) or 0,
        savings_percent=savings_percent,
        billing_period=offer.billing_period,
        trial_days=offer.trial_days,
        credits_amount=num(offer.credits_amount),
        credits_unit=offer.credits_unit,
        is_global=offer.is_global,
        requires_payment_method=offer.requires_payment_method,
        requires_new_user=offer.requires_new_user,
        requires_student_id=offer.requires_student_id,
        requires_auto_renew=offer.requires_auto_renew,
        is_affiliate=bool(offer.affiliate_url),
        eligibility_types=list(offer.eligibility_types or []),
        eligibility_notes=(offer.eligibility_notes or None),
        country_codes=country_codes,
        official_url=offer.official_url,
        redemption_url=offer.redemption_url,
        image_url=offer.image_url,
        is_sponsored=offer.is_sponsored,
        sponsor_name=offer.sponsor_name,
        expires_at=offer.expires_at,
        last_checked_at=offer.last_checked_at,
        published_at=offer.published_at,
        days_remaining=offer.days_remaining,
        hours_remaining=offer.hours_remaining,
        is_expired=offer.is_expired,
        is_verified=offer.is_verified,
        is_featured=offer.is_featured,
        is_handpicked=offer.is_handpicked,
        is_demo_data=offer.is_demo_data,
        is_genuinely_free=offer.is_genuinely_free,
        popularity_score=float(offer.popularity_score or 0),
        bookmark_count=offer.bookmark_count or 0,
        click_count=offer.click_count or 0,
        display_prices=_display_prices(offer, currency),
        relevance=relevance,
        matched_reason=match_reason,
        bookmarked=bool(bookmarked_ids and offer.id in bookmarked_ids),
    )


def serialize_detail(
    offer: Offer,
    *,
    currency: str | None = None,
    country_code: str | None = None,
    bookmarked_ids: set[str] | None = None,
    similar: Iterable[Offer] = (),
    free_alternatives: Iterable[Offer] = (),
) -> OfferDetail:
    card = serialize_card(
        offer, currency=currency, country_code=country_code, bookmarked_ids=bookmarked_ids
    )
    alternatives: list[AlternativeOut] = []
    for alt in getattr(offer, "alternatives", []) or []:
        alternatives.append(
            AlternativeOut(
                id=alt.id,
                label=alt.label,
                relation=alt.relation,
                external_name=alt.external_name,
                external_url=alt.external_url,
                note=alt.note,
            )
        )

    payload = card.model_dump()
    payload.update(
        subtitle=offer.subtitle,
        description=offer.description,
        how_to_redeem=list(offer.how_to_redeem or []),
        fine_print=offer.fine_print,
        features=list(offer.features or []),
        free_alternative_note=offer.free_alternative_note,
        ends_as_paid=offer.ends_as_paid,
        renewal_price=num(offer.renewal_price),
        discount_kind=offer.discount_kind,
        discount_amount=num(offer.discount_amount),
        starts_at=offer.starts_at,
        redemption_deadline=offer.redemption_deadline,
        eligibility_notes=offer.eligibility_notes,
        eligibility=[
            EligibilityOut(
                rule=row.rule,
                label=row.label,
                detail=row.detail,
                blocking=row.blocking,
                source_url=row.source_url,
            )
            for row in getattr(offer, "eligibility", []) or []
        ],
        excluded_countries=list(offer.excluded_countries or []),
        secondary_category_ids=list(offer.secondary_category_ids or []),
        coupon_code=offer.coupon_code,
        is_disputed=offer.status == "disputed",
        discovery_confidence=float(offer.discovery_confidence or 0),
        source_name=getattr(offer.source, "name", None),
        verifications=[
            VerificationOut(
                id=v.id,
                result=v.result,
                http_status=v.http_status,
                final_url=v.final_url,
                checked_at=v.checked_at,
                method=v.method,
                price_found=num(v.price_found),
                original_price_found=num(v.original_price_found),
                message=v.message,
            )
            for v in (getattr(offer, "verifications", []) or [])[:15]
        ],
        alternatives=alternatives,
        similar=[
            serialize_card(s, currency=currency, country_code=country_code) for s in similar
        ],
        free_alternatives=[
            serialize_card(a, currency=currency, country_code=country_code)
            for a in free_alternatives
        ],
    )
    return OfferDetail(**payload)


def price_summary(offer: Offer, currency: str | None = None, country_code: str | None = None) -> str:
    """Human readable one-liner used in cards and structured data."""
    currency = public_currency(currency or default_currency())
    original, promo = _localised_prices(offer, currency, country_code)
    period = {"monthly": "/mo", "yearly": "/yr", "annual": "/yr", "lifetime": ""}.get(
        (offer.billing_period or "").lower(), ""
    )
    if promo is not None and promo > 0:
        return f"{format_money(promo, currency)}{period}"
    if promo == 0:
        return "Free"
    if promo is None and offer.is_genuinely_free:
        return "Free"
    if offer.credits_amount:
        return f"{format_money(num(offer.credits_amount), currency)} {offer.credits_unit or 'credit'}"
    return "Pricing on site"


def label_for_verification(status: str) -> tuple[str, str]:
    mapping = {
        VerificationStatus.VERIFIED.value: ("Verified", "checked"),
        VerificationStatus.NEEDS_MANUAL.value: ("Needs review", "pending"),
        VerificationStatus.UNVERIFIED.value: ("Unverified", "pending"),
        VerificationStatus.FAILED.value: ("Check failed", "error"),
    }
    return mapping.get(status, ("Unverified", "pending"))


def iso_or_none(value: datetime | None) -> str | None:
    return value.isoformat() if value else None
