"""Offer-related API schemas."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator

from app.models.enums import (
    DiscountKind,
    EligibilityType,
    OfferStatus,
    OfferType,
    VerificationStatus,
)
from app.schemas.common import ORMModel, QuotaMeta

SortOption = Literal[
    "relevance",
    "newest",
    "popular",
    "savings",
    "ending_soon",
    "value",
    "trending",
    "price_asc",
    "price_desc",
]


# --------------------------------------------------------------- taxonomy
class CategoryBrief(ORMModel):
    id: str
    slug: str
    name: str
    icon: str
    color: str
    tagline: str | None = None
    offer_count: int = 0
    live_offer_count: int = 0


class CategoryOut(CategoryBrief):
    description: str | None = None
    group_name: str | None = None
    seo_title: str | None = None
    seo_description: str | None = None
    keywords: list[str] = Field(default_factory=list)


class BrandBrief(ORMModel):
    id: str
    slug: str
    name: str
    domain: str | None = None
    logo_url: str | None = None
    accent_color: str | None = None
    is_verified: bool = False
    offer_count: int = 0


class CountryBrief(ORMModel):
    code: str
    name: str
    slug: str
    flag_emoji: str | None = None
    currency: str = "USD"
    region: str | None = None
    offer_count: int = 0


# ---------------------------------------------------------------- prices
class PriceOut(ORMModel):
    currency: str
    country_code: str | None = None
    original_price: float | None = None
    promo_price: float | None = None
    renewal_price: float | None = None
    billing_period: str | None = None
    is_available: bool = True
    captured_at: datetime | None = None


class EligibilityOut(ORMModel):
    rule: EligibilityType | str
    label: str
    detail: str | None = None
    blocking: bool = False
    source_url: str | None = None


class VerificationOut(ORMModel):
    id: str
    result: str
    http_status: int | None = None
    final_url: str | None = None
    checked_at: datetime
    method: str = "http"
    price_found: float | None = None
    original_price_found: float | None = None
    message: str | None = None


class AlternativeOut(ORMModel):
    id: str
    label: str
    relation: str = "alternative"
    external_name: str | None = None
    external_url: str | None = None
    note: str | None = None
    related_offer: "OfferCard | None" = None


# ---------------------------------------------------------------- offers
class OfferCard(ORMModel):
    """Compact representation used by grids, search results and carousels."""

    id: str
    slug: str
    title: str
    short_description: str
    offer_type: OfferType
    status: OfferStatus
    verification_status: VerificationStatus

    category: CategoryBrief
    brand: BrandBrief | None = None

    currency: str = "USD"
    original_price: float | None = None
    promo_price: float | None = None
    savings_value: float = 0
    savings_percent: int = 0
    billing_period: str | None = None
    trial_days: int | None = None
    credits_amount: float | None = None
    credits_unit: str | None = None

    is_global: bool = True
    requires_payment_method: bool = False
    requires_new_user: bool = True
    requires_student_id: bool = False
    requires_auto_renew: bool = False
    is_affiliate: bool = False
    eligibility_types: list[str] = Field(default_factory=list)
    #: Short human-readable caveat, e.g. a provider's reported free-tier terms.
    eligibility_notes: str | None = None
    country_codes: list[str] = Field(default_factory=list)

    official_url: str
    redemption_url: str = ""
    image_url: str | None = None
    is_sponsored: bool = False
    sponsor_name: str | None = None

    expires_at: datetime | None = None
    last_checked_at: datetime | None = None
    published_at: datetime | None = None
    days_remaining: int | None = None
    hours_remaining: float | None = None
    is_expired: bool = False
    is_verified: bool = False
    is_featured: bool = False
    is_handpicked: bool = False
    is_demo_data: bool = False
    is_genuinely_free: bool = False

    popularity_score: float = 0
    bookmark_count: int = 0
    click_count: int = 0

    display_prices: list[PriceOut] = Field(default_factory=list)
    relevance: float | None = None
    matched_reason: str | None = None
    bookmarked: bool = False


class OfferDetail(OfferCard):
    subtitle: str | None = None
    description: str
    how_to_redeem: list[str] = Field(default_factory=list)
    fine_print: str | None = None
    features: list[str] = Field(default_factory=list)
    free_alternative_note: str | None = None
    ends_as_paid: bool = True
    renewal_price: float | None = None
    discount_kind: DiscountKind | None = None
    discount_amount: float | None = None
    starts_at: datetime | None = None
    redemption_deadline: date | None = None
    eligibility_notes: str | None = None
    eligibility: list[EligibilityOut] = Field(default_factory=list)
    excluded_countries: list[str] = Field(default_factory=list)
    secondary_category_ids: list[str] = Field(default_factory=list)
    coupon_code: str | None = None
    is_disputed: bool = False
    discovery_confidence: float = 0
    source_name: str | None = None
    verifications: list[VerificationOut] = Field(default_factory=list)
    alternatives: list[AlternativeOut] = Field(default_factory=list)
    similar: list[OfferCard] = Field(default_factory=list)
    free_alternatives: list[OfferCard] = Field(default_factory=list)


AlternativeOut.model_rebuild()


class OfferUpsert(ORMModel):
    """Admin create/update payload."""

    title: str = Field(min_length=4, max_length=240)
    slug: str | None = Field(default=None, max_length=200, pattern=r"^[a-z0-9\-]+$")
    subtitle: str | None = Field(default=None, max_length=320)
    short_description: str = Field(min_length=10, max_length=400)
    description: str = Field(min_length=20)
    category_id: str
    brand_id: str | None = None
    secondary_category_ids: list[str] = Field(default_factory=list)

    offer_type: OfferType = OfferType.FREE_TRIAL
    tags: list[str] = Field(default_factory=list)

    currency: str = Field(default="USD", min_length=3, max_length=3)
    original_price: float | None = Field(default=None, ge=0, le=10_000_000)
    promo_price: float | None = Field(default=None, ge=0, le=10_000_000)
    billing_period: str | None = None
    renewal_price: float | None = Field(default=None, ge=0, le=10_000_000)
    discount_kind: DiscountKind | None = None
    discount_amount: float | None = Field(default=None, ge=0)
    credits_amount: float | None = Field(default=None, ge=0)
    credits_unit: str | None = None
    trial_days: int | None = Field(default=None, ge=0, le=3650)

    starts_at: datetime | None = None
    expires_at: datetime | None = None
    redemption_deadline: date | None = None

    is_global: bool = True
    country_codes: list[str] = Field(default_factory=list)
    excluded_countries: list[str] = Field(default_factory=list)
    requires_new_user: bool = True
    requires_student_id: bool = False
    minimum_age: int | None = Field(default=None, ge=0, le=120)
    requires_payment_method: bool = False
    requires_auto_renew: bool = False
    eligibility_notes: str | None = None
    eligibility_types: list[EligibilityType] = Field(default_factory=list)

    how_to_redeem: list[str] = Field(default_factory=list)
    fine_print: str | None = None
    features: list[str] = Field(default_factory=list)
    is_genuinely_free: bool = False
    ends_as_paid: bool = True

    official_url: HttpUrl
    affiliate_url: HttpUrl | None = None
    coupon_code: str | None = Field(default=None, max_length=80)
    image_url: str | None = None
    is_sponsored: bool = False
    sponsor_name: str | None = None

    status: OfferStatus = OfferStatus.PENDING_REVIEW
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED
    is_featured: bool = False
    is_handpicked: bool = False
    is_demo_data: bool = False
    internal_notes: str | None = None
    published_at: datetime | None = None

    @field_validator("currency")
    @classmethod
    def _upper_currency(cls, v: str) -> str:
        return v.upper()

    @model_validator(mode="after")
    def _check_prices(self) -> "OfferUpsert":
        if (
            self.original_price is not None
            and self.promo_price is not None
            and self.original_price > 0
            and self.promo_price > self.original_price
        ):
            raise ValueError("promo_price cannot be greater than original_price")
        return self

    @model_validator(mode="after")
    def _check_window(self) -> "OfferUpsert":
        if self.starts_at and self.expires_at and self.expires_at <= self.starts_at:
            raise ValueError("expires_at must be after starts_at")
        return self


class OfferStatusChange(ORMModel):
    status: OfferStatus
    verification_status: VerificationStatus | None = None
    reason: str | None = Field(default=None, max_length=500)
    is_featured: bool | None = None
    is_handpicked: bool | None = None


class OfferFilterParams(ORMModel):
    q: str | None = None
    category: list[str] = Field(default_factory=list)
    brand: list[str] = Field(default_factory=list)
    type: list[OfferType] = Field(default_factory=list)
    country: list[str] = Field(default_factory=list)
    currency: list[str] = Field(default_factory=list)
    min_savings: float | None = None
    max_price: float | None = None
    min_trial_days: int | None = None
    max_trial_days: int | None = None
    duration: Literal["any", "instant", "week", "month", "quarter", "year", "lifetime"] | None = None
    requires_payment_method: bool | None = None
    requires_student_id: bool | None = None
    new_users_only: bool | None = None
    verified_only: bool | None = None
    global_only: bool | None = None
    ending_within_days: int | None = None
    ending_within_hours: int | None = None
    sort: SortOption = "relevance"
    page: int = Field(default=1, ge=1, le=500)
    page_size: int = Field(default=24, ge=1, le=100)


# ---------------------------------------------------------------- search
class SearchSuggestion(BaseModel):
    type: Literal["offer", "brand", "category", "query"]
    id: str
    label: str
    sublabel: str | None = None
    slug: str | None = None
    logo_url: str | None = None
    icon: str | None = None
    offer_type: OfferType | None = None
    score: float = 0.0


class ParsedIntent(BaseModel):
    """Interpreted meaning of a raw search string."""

    raw: str
    normalised: str
    intent: Literal["browse", "offer_type", "duration", "price", "category", "brand", "mixed"]
    offer_types: list[OfferType] = Field(default_factory=list)
    category_slugs: list[str] = Field(default_factory=list)
    brand_slugs: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    min_trial_days: int | None = None
    max_trial_days: int | None = None
    max_price: float | None = None
    min_price: float | None = None
    country_codes: list[str] = Field(default_factory=list)
    requires_payment_method: bool | None = None
    ending_within_days: int | None = None
    explanation: str = ""


class SearchResponse(BaseModel):
    query: str
    intent: ParsedIntent
    results: list[OfferCard]
    suggestions: list[SearchSuggestion] = Field(default_factory=list)
    corrections: list[str] = Field(default_factory=list)
    facets: dict[str, dict[str, int]] = Field(default_factory=dict)
    total: int
    page: int
    page_size: int
    pages: int
    took_ms: float
    did_you_mean: str | None = None
    #: Free-tier truncation details, mirroring the directory listing.
    meta: QuotaMeta | None = None


class FacetBucket(BaseModel):
    value: str
    label: str
    count: int
    extra: dict[str, Any] = Field(default_factory=dict)


class FacetResponse(BaseModel):
    categories: list[FacetBucket] = Field(default_factory=list)
    brands: list[FacetBucket] = Field(default_factory=list)
    offer_types: list[FacetBucket] = Field(default_factory=list)
    countries: list[FacetBucket] = Field(default_factory=list)
    durations: list[FacetBucket] = Field(default_factory=list)
    max_savings: float = 0
    max_price: float | None = None


# ------------------------------------------------------------- discovery
class DiscoveredItem(BaseModel):
    """Normalised output of a source adapter before persistence."""

    external_id: str | None = None
    title: str
    description: str | None = None
    url: str
    offer_type: OfferType | None = None
    brand_name: str | None = None
    category_slug: str | None = None
    original_price: float | None = None
    promo_price: float | None = None
    currency: str = "USD"
    trial_days: int | None = None
    expires_at: datetime | None = None
    coupon_code: str | None = None
    country_codes: list[str] = Field(default_factory=list)
    eligibility_types: list[EligibilityType] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    published_at: datetime | None = None
    raw: dict[str, Any] = Field(default_factory=dict)
