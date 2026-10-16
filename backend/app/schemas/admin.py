"""Admin-facing schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field, HttpUrl, field_validator

from app.models.enums import (
    OfferStatus,
    OfferType,
    SourceHealth,
    SourceType,
    VerificationStatus,
)
from app.schemas.common import ORMModel


class SourceUpsert(ORMModel):
    key: str = Field(min_length=2, max_length=80, pattern=r"^[a-z0-9_\-]+$")
    name: str = Field(min_length=2, max_length=160)
    publisher: str = Field(min_length=2, max_length=160)
    source_type: SourceType = SourceType.RSS
    adapter: str | None = None
    homepage_url: str
    feed_url: str | None = None
    api_docs_url: str | None = None
    api_key_env: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    respect_robots: bool = True
    requires_js: bool = False
    is_paywalled: bool = False
    rate_limit_per_hour: int = Field(default=30, ge=1, le=10_000)
    min_request_interval_seconds: float = Field(default=120.0, ge=0, le=86_400)
    cache_ttl_seconds: int = Field(default=900, ge=0, le=86_400)
    max_items: int = Field(default=50, ge=1, le=500)
    is_active: bool = True
    trust_weight: float = Field(default=0.5, ge=0, le=1)
    license_note: str | None = None
    terms_url: str | None = None

    @field_validator("trust_weight")
    @classmethod
    def _round(cls, v: float) -> float:
        return round(v, 2)


class SourceOut(ORMModel):
    id: str
    key: str
    name: str
    publisher: str
    source_type: SourceType
    adapter: str | None = None
    homepage_url: str
    feed_url: str | None = None
    api_docs_url: str | None = None
    is_active: bool
    respect_robots: bool
    requires_js: bool
    is_paywalled: bool
    rate_limit_per_hour: int
    min_request_interval_seconds: float
    cache_ttl_seconds: int
    max_items: int
    health: SourceHealth
    trust_weight: float
    license_note: str | None = None
    terms_url: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    api_key_configured: bool = False
    last_run_at: datetime | None = None
    last_success_at: datetime | None = None
    consecutive_failures: int = 0
    total_items_seen: int = 0
    total_items_accepted: int = 0
    total_items_duplicate: int = 0
    total_items_rejected: int = 0


class SourceRunOut(ORMModel):
    id: str
    source_id: str
    source_key: str | None = None
    started_at: datetime
    finished_at: datetime | None = None
    status: str
    http_status: int | None = None
    items_seen: int = 0
    items_accepted: int = 0
    items_duplicate: int = 0
    items_rejected: int = 0
    skipped_reason: str | None = None
    error: str | None = None
    duration_ms: int | None = None


class CandidateOut(ORMModel):
    id: str
    source_id: str
    source_key: str | None = None
    source_url: str
    raw_title: str
    raw_description: str | None = None
    status: str
    rejection_reason: str | None = None
    confidence: float = 0
    offer_id: str | None = None
    duplicate_of_id: str | None = None
    reviewed_at: datetime | None = None
    seen_at: datetime
    parsed: dict[str, Any] = Field(default_factory=dict)


class CandidateDecision(ORMModel):
    action: str = Field(pattern="^(approve|reject|duplicate)$")
    reason: str | None = Field(default=None, max_length=240)
    note: str | None = Field(default=None, max_length=2000)


class BulkOfferAction(ORMModel):
    offer_ids: list[str] = Field(min_length=1, max_length=200)
    action: str = Field(pattern="^(publish|reject|expire|feature|unfeature|archive|delete|verify)$")
    reason: str | None = Field(default=None, max_length=500)


class CategoryUpsert(ORMModel):
    slug: str = Field(pattern=r"^[a-z0-9\-]+$", max_length=120)
    name: str = Field(min_length=2, max_length=120)
    tagline: str | None = Field(default=None, max_length=255)
    description: str | None = None
    icon: str = "tag"
    color: str = "lime"
    group_name: str | None = None
    sort_order: int = 100
    is_active: bool = True
    seo_title: str | None = Field(default=None, max_length=180)
    seo_description: str | None = Field(default=None, max_length=320)
    keywords: list[str] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)


class CategoryAdminOut(ORMModel):
    id: str
    slug: str
    name: str
    tagline: str | None = None
    description: str | None = None
    icon: str
    color: str
    group_name: str | None = None
    sort_order: int
    is_active: bool
    seo_title: str | None = None
    seo_description: str | None = None
    keywords: list[str] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)
    offer_count: int = 0


class BrandUpsert(ORMModel):
    name: str = Field(min_length=2, max_length=120)
    domain: str | None = Field(default=None, max_length=190)
    website_url: str | None = None
    logo_url: str | None = None
    accent_color: str | None = None
    description: str | None = None
    aliases: list[str] = Field(default_factory=list)
    category_id: str | None = None
    country_code: str | None = None
    is_verified: bool = False
    is_active: bool = True


class BrandAdminOut(ORMModel):
    id: str
    name: str
    slug: str
    domain: str | None = None
    website_url: str | None = None
    logo_url: str | None = None
    accent_color: str | None = None
    description: str | None = None
    aliases: list[str] = Field(default_factory=list)
    category_id: str | None = None
    country_code: str | None = None
    is_verified: bool
    is_active: bool
    followers_count: int = 0
    offer_count: int = 0


class EligibilityRuleOut(ORMModel):
    rule: str
    label: str
    count: int


class DashboardStats(ORMModel):
    total_offers: int = 0
    live_offers: int = 0
    expired_offers: int = 0
    pending_review: int = 0
    verified_offers: int = 0
    disputed_offers: int = 0
    demo_offers: int = 0
    total_categories: int = 0
    total_brands: int = 0
    total_sources: int = 0
    active_sources: int = 0
    failing_sources: int = 0
    total_users: int = 0
    new_users_7d: int = 0
    total_bookmarks: int = 0
    open_reports: int = 0
    pending_candidates: int = 0
    clicks_7d: int = 0
    views_7d: int = 0
    searches_7d: int = 0
    newsletter_subs: int = 0
    sponsored_offers: int = 0
    avg_savings_percent: float = 0
    generated_at: datetime


class TrendPoint(ORMModel):
    day: str
    value: int | float = 0


class TopRow(ORMModel):
    label: str
    slug: str | None = None
    id: str | None = None
    value: int | float = 0
    extra: dict[str, Any] = Field(default_factory=dict)


class AnalyticsOverview(ORMModel):
    range_days: int = 30
    clicks: list[TrendPoint] = Field(default_factory=list)
    views: list[TrendPoint] = Field(default_factory=list)
    searches: list[TrendPoint] = Field(default_factory=list)
    signups: list[TrendPoint] = Field(default_factory=list)
    top_categories: list[TopRow] = Field(default_factory=list)
    top_offers: list[TopRow] = Field(default_factory=list)
    top_countries: list[TopRow] = Field(default_factory=list)
    top_searches: list[TopRow] = Field(default_factory=list)
    zero_result_searches: list[TopRow] = Field(default_factory=list)
    conversion_rate: float = 0
    click_to_verify_rate: float = 0
    verification_success_rate: float = 0


class VerificationSweepResult(ORMModel):
    checked: int = 0
    ok: int = 0
    changed: int = 0
    broken: int = 0
    expired: int = 0
    failed: int = 0
    skipped: int = 0
    details: list[dict[str, Any]] = Field(default_factory=list)


class DiscoverySweepResult(ORMModel):
    sources_checked: int = 0
    sources_skipped: int = 0
    items_seen: int = 0
    items_created: int = 0
    items_updated: int = 0
    items_duplicate: int = 0
    items_rejected: int = 0
    details: list[dict[str, Any]] = Field(default_factory=list)


class UserAdminOut(ORMModel):
    id: str
    email: str
    display_name: str | None = None
    role: str
    country_code: str | None = None
    preferred_currency: str
    is_active: bool
    is_banned: bool
    created_at: datetime
    last_login_at: datetime | None = None
    bookmark_count: int = 0


class UserRoleChange(ORMModel):
    role: str = Field(pattern="^(user|reviewer|admin)$")
    is_active: bool | None = None
    is_banned: bool | None = None


class SubmissionOut(ORMModel):
    id: str
    title: str
    brand_name: str | None = None
    official_url: str
    category_slug: str | None = None
    offer_type: str | None = None
    notes: str | None = None
    submitter_email: str | None = None
    status: str
    created_at: datetime
    created_offer_id: str | None = None


class ReportAdminOut(ORMModel):
    id: str
    offer_id: str | None = None
    offer_title: str | None = None
    reason: str
    details: str | None = None
    status: str
    reporter_email: str | None = None
    created_at: datetime
    resolved_at: datetime | None = None
    resolution_note: str | None = None


class ReportResolution(ORMModel):
    status: str = Field(pattern="^(open|triaged|resolved|dismissed)$")
    resolution_note: str | None = Field(default=None, max_length=2000)
    mark_offer_disputed: bool = False


class ScheduledJobOut(ORMModel):
    name: str
    schedule: str
    enabled: bool
    last_run_at: datetime | None = None
    next_run_at: datetime | None = None
    description: str = ""


class TrendingQueryOut(ORMModel):
    query: str
    result_count: int
    intent: str | None = None
    created_at: datetime