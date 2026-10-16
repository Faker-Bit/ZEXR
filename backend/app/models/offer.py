"""The core Offer aggregate plus its child records."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utcnow
from app.models.enums import (
    DiscountKind,
    OfferStatus,
    OfferType,
    VerificationStatus,
)


class Offer(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "offers"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_offers_slug"),
        Index("ix_offers_status_published", "status", "published_at"),
        Index("ix_offers_status_expiry", "status", "expires_at"),
        Index("ix_offers_category_status", "category_id", "status"),
        Index("ix_offers_brand_status", "brand_id", "status"),
        Index("ix_offers_type_status", "offer_type", "status"),
        Index("ix_offers_savings", "savings_value", "status"),
        Index("ix_offers_verification", "verification_status", "last_checked_at"),
    )

    slug: Mapped[str] = mapped_column(String(200), index=True)
    title: Mapped[str] = mapped_column(String(240))
    subtitle: Mapped[str | None] = mapped_column(String(320))
    description: Mapped[str] = mapped_column(Text)
    short_description: Mapped[str] = mapped_column(String(400))

    # taxonomy
    category_id: Mapped[str] = mapped_column(ForeignKey("categories.id"), index=True)
    brand_id: Mapped[str | None] = mapped_column(ForeignKey("brands.id"), index=True)
    secondary_category_ids: Mapped[list | None] = mapped_column(JSON, default=list)

    # classification
    offer_type: Mapped[str] = mapped_column(String(32), default=OfferType.FREE_TRIAL.value, index=True)
    tags: Mapped[list | None] = mapped_column(JSON, default=list)

    # commercial terms
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    original_price: Mapped[float | None] = mapped_column(Numeric(12, 2))
    promo_price: Mapped[float | None] = mapped_column(Numeric(12, 2))
    savings_value: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    savings_percent: Mapped[int] = mapped_column(Integer, default=0)
    billing_period: Mapped[str | None] = mapped_column(String(24))
    renewal_price: Mapped[float | None] = mapped_column(Numeric(12, 2))
    discount_kind: Mapped[str | None] = mapped_column(String(24), default=DiscountKind.PERCENT.value)
    discount_amount: Mapped[float | None] = mapped_column(Numeric(12, 2))
    credits_amount: Mapped[float | None] = mapped_column(Numeric(12, 2))
    credits_unit: Mapped[str | None] = mapped_column(String(40))
    trial_days: Mapped[int | None] = mapped_column(Integer)

    # validity window
    starts_at: Mapped[datetime | None] = mapped_column(DateTime)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    redemption_deadline: Mapped[date | None] = mapped_column(Date)

    # eligibility
    is_global: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    excluded_countries: Mapped[list | None] = mapped_column(JSON, default=list)
    requires_new_user: Mapped[bool] = mapped_column(Boolean, default=True)
    requires_student_id: Mapped[bool] = mapped_column(Boolean, default=False)
    minimum_age: Mapped[int | None] = mapped_column(Integer)
    requires_payment_method: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_auto_renew: Mapped[bool] = mapped_column(Boolean, default=False)
    eligibility_notes: Mapped[str | None] = mapped_column(Text)
    eligibility_types: Mapped[list | None] = mapped_column(JSON, default=list)

    # content
    how_to_redeem: Mapped[list | None] = mapped_column(JSON, default=list)
    fine_print: Mapped[str | None] = mapped_column(Text)
    features: Mapped[list | None] = mapped_column(JSON, default=list)
    free_alternative_note: Mapped[str | None] = mapped_column(Text)
    is_genuinely_free: Mapped[bool] = mapped_column(Boolean, default=False)
    ends_as_paid: Mapped[bool] = mapped_column(Boolean, default=True)

    # links / monetisation
    official_url: Mapped[str] = mapped_column(String(700))
    affiliate_url: Mapped[str | None] = mapped_column(String(700))
    coupon_code: Mapped[str | None] = mapped_column(String(80))
    image_url: Mapped[str | None] = mapped_column(String(500))
    is_sponsored: Mapped[bool] = mapped_column(Boolean, default=False)
    sponsor_name: Mapped[str | None] = mapped_column(String(120))

    # trust / lifecycle
    status: Mapped[str] = mapped_column(String(32), default=OfferStatus.PENDING_REVIEW.value, index=True)
    verification_status: Mapped[str] = mapped_column(
        String(24), default=VerificationStatus.UNVERIFIED.value, index=True
    )
    verified_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
    source_id: Mapped[str | None] = mapped_column(ForeignKey("sources.id"), index=True)
    discovery_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    duplicate_of_id: Mapped[str | None] = mapped_column(ForeignKey("offers.id"))
    is_demo_data: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    internal_notes: Mapped[str | None] = mapped_column(Text)

    # ranking signals
    popularity_score: Mapped[float] = mapped_column(Float, default=0.0, index=True)
    quality_score: Mapped[float] = mapped_column(Float, default=0.0)
    click_count: Mapped[int] = mapped_column(Integer, default=0)
    view_count: Mapped[int] = mapped_column(Integer, default=0)
    bookmark_count: Mapped[int] = mapped_column(Integer, default=0)
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_handpicked: Mapped[bool] = mapped_column(Boolean, default=False)
    trending_rank: Mapped[int | None] = mapped_column(Integer, index=True)

    published_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime)

    # relations
    category: Mapped["Category"] = relationship(back_populates="offers")  # noqa: F821
    brand: Mapped["Brand | None"] = relationship(back_populates="offers")  # noqa: F821
    prices: Mapped[list["OfferPrice"]] = relationship(
        back_populates="offer", cascade="all, delete-orphan"
    )
    countries: Mapped[list["OfferCountry"]] = relationship(
        back_populates="offer", cascade="all, delete-orphan"
    )
    eligibility: Mapped[list["OfferEligibility"]] = relationship(
        back_populates="offer", cascade="all, delete-orphan"
    )
    verifications: Mapped[list["OfferVerification"]] = relationship(
        back_populates="offer",
        cascade="all, delete-orphan",
        order_by="OfferVerification.checked_at.desc()",
    )
    alternatives: Mapped[list["OfferAlternative"]] = relationship(
        back_populates="offer",
        cascade="all, delete-orphan",
        foreign_keys="OfferAlternative.offer_id",
    )
    source: Mapped["Source | None"] = relationship(back_populates="offers")  # noqa: F821

# ------------------------------------------------------------------ flags
    @property
    def is_expired(self) -> bool:
        """True once the offer's own validity window has closed.

        Attributes are read defensively: a row that was just inserted has
        columns that were never assigned, and SQLAlchemy will not populate them
        from the database until the object is refreshed.
        """
        if getattr(self, "status", None) == OfferStatus.EXPIRED.value:
            return True
        expires_at = getattr(self, "expires_at", None)
        if expires_at and expires_at < utcnow():
            return True
        deadline = getattr(self, "redemption_deadline", None)
        if deadline and deadline < utcnow().date():
            return True
        return False

    @property
    def is_live(self) -> bool:
        return getattr(self, "status", None) == OfferStatus.PUBLISHED.value and not self.is_expired

    @property
    def is_verified(self) -> bool:
        return getattr(self, "verification_status", None) == VerificationStatus.VERIFIED.value

    @property
    def days_remaining(self) -> int | None:
        expires_at = getattr(self, "expires_at", None)
        if not expires_at:
            return None
        return max(0, (expires_at - utcnow()).days)

    @property
    def hours_remaining(self) -> float | None:
        expires_at = getattr(self, "expires_at", None)
        if not expires_at:
            return None
        return max(0.0, (expires_at - utcnow()).total_seconds() / 3600)

    @property
    def redemption_url(self) -> str:
        return getattr(self, "affiliate_url", None) or self.official_url

    def to_search_document(self) -> str:
        parts = [
            self.title,
            self.short_description,
            self.subtitle or "",
            getattr(self.brand, "name", "") or "",
            getattr(self.category, "name", "") or "",
            " ".join(self.tags or []),
        ]
        return " ".join(p for p in parts if p)


class OfferPrice(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Per-market price snapshots so users see their own currency."""

    __tablename__ = "offer_prices"
    __table_args__ = (
        UniqueConstraint("offer_id", "currency", name="uq_offer_prices_offer_currency"),
    )

    offer_id: Mapped[str] = mapped_column(ForeignKey("offers.id", ondelete="CASCADE"), index=True)
    currency: Mapped[str] = mapped_column(String(3), index=True)
    country_code: Mapped[str | None] = mapped_column(String(2))
    original_price: Mapped[float | None] = mapped_column(Numeric(12, 2))
    promo_price: Mapped[float | None] = mapped_column(Numeric(12, 2))
    renewal_price: Mapped[float | None] = mapped_column(Numeric(12, 2))
    billing_period: Mapped[str | None] = mapped_column(String(24))
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    source_note: Mapped[str | None] = mapped_column(String(240))

    offer: Mapped["Offer"] = relationship(back_populates="prices")


class OfferCountry(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "offer_countries"
    __table_args__ = (
        UniqueConstraint("offer_id", "country_code", name="uq_offer_countries_offer_country"),
    )

    offer_id: Mapped[str] = mapped_column(ForeignKey("offers.id", ondelete="CASCADE"), index=True)
    country_code: Mapped[str] = mapped_column(
        String(2), ForeignKey("countries.code", ondelete="CASCADE"), index=True
    )
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime)
    note: Mapped[str | None] = mapped_column(String(240))

    offer: Mapped["Offer"] = relationship(back_populates="countries")
    country: Mapped["Country | None"] = relationship()  # noqa: F821


class OfferEligibility(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "offer_eligibility"
    __table_args__ = (
        UniqueConstraint("offer_id", "rule", name="uq_offer_eligibility_offer_rule"),
    )

    offer_id: Mapped[str] = mapped_column(ForeignKey("offers.id", ondelete="CASCADE"), index=True)
    rule: Mapped[str] = mapped_column(String(48), index=True)
    label: Mapped[str] = mapped_column(String(160))
    detail: Mapped[str | None] = mapped_column(String(400))
    blocking: Mapped[bool] = mapped_column(Boolean, default=False)
    source_url: Mapped[str | None] = mapped_column(String(700))

    offer: Mapped["Offer"] = relationship(back_populates="eligibility")


class OfferVerification(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "offer_verifications"
    __table_args__ = (Index("ix_offer_verifications_offer_checked", "offer_id", "checked_at"),)

    offer_id: Mapped[str] = mapped_column(ForeignKey("offers.id", ondelete="CASCADE"), index=True)
    result: Mapped[str] = mapped_column(String(32))
    http_status: Mapped[int | None] = mapped_column(Integer)
    final_url: Mapped[str | None] = mapped_column(String(700))
    checked_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    method: Mapped[str] = mapped_column(String(32), default="http")
    price_found: Mapped[float | None] = mapped_column(Numeric(12, 2))
    original_price_found: Mapped[float | None] = mapped_column(Numeric(12, 2))
    content_hash: Mapped[str | None] = mapped_column(String(64))
    message: Mapped[str | None] = mapped_column(String(500))
    details: Mapped[dict | None] = mapped_column(JSON)

    offer: Mapped["Offer"] = relationship(back_populates="verifications")


class OfferAlternative(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Link to related offers / free alternatives."""

    __tablename__ = "offer_alternatives"
    __table_args__ = (
        UniqueConstraint("offer_id", "related_offer_id", name="uq_offer_alternatives_pair"),
    )

    offer_id: Mapped[str] = mapped_column(ForeignKey("offers.id", ondelete="CASCADE"), index=True)
    related_offer_id: Mapped[str | None] = mapped_column(ForeignKey("offers.id", ondelete="CASCADE"))
    label: Mapped[str] = mapped_column(String(120), default="Alternative")
    external_name: Mapped[str | None] = mapped_column(String(160))
    external_url: Mapped[str | None] = mapped_column(String(700))
    note: Mapped[str | None] = mapped_column(String(400))
    relation: Mapped[str] = mapped_column(String(32), default="alternative")
    sort_order: Mapped[int] = mapped_column(Integer, default=100)

    offer: Mapped["Offer"] = relationship(back_populates="alternatives", foreign_keys=[offer_id])