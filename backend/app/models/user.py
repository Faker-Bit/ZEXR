"""User accounts, personalisation and community signals."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utcnow
from app.models.enums import AlertKind, AuthProvider, ReportReason, ReportStatus, UserRole


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    hashed_password: Mapped[str | None] = mapped_column(String(255))
    display_name: Mapped[str | None] = mapped_column(String(120))
    avatar_url: Mapped[str | None] = mapped_column(String(500))
    role: Mapped[str] = mapped_column(String(24), default=UserRole.USER.value, index=True)

    country_code: Mapped[str | None] = mapped_column(String(2), ForeignKey("countries.code"))
    preferred_currency: Mapped[str] = mapped_column(String(3), default="USD")
    locale: Mapped[str] = mapped_column(String(12), default="en")
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")

    interests: Mapped[list | None] = mapped_column(JSON, default=list)
    interested_categories: Mapped[list | None] = mapped_column(JSON, default=list)

    email_notifications: Mapped[bool] = mapped_column(Boolean, default=True)
    newsletter_subscribed: Mapped[bool] = mapped_column(Boolean, default=False)
    marketing_opt_in: Mapped[bool] = mapped_column(Boolean, default=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime)

    # admin extras
    two_factor_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text)

    bookmarks: Mapped[list["Bookmark"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    alerts: Mapped[list["Alert"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    reports: Mapped[list["Report"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", foreign_keys="Report.user_id"
    )

    @property
    def is_admin(self) -> bool:
        return self.role in (UserRole.ADMIN.value,)


class OAuthAccount(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "oauth_accounts"
    __table_args__ = (
        UniqueConstraint("provider", "provider_account_id", name="uq_oauth_provider_account"),
    )

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(24), default=AuthProvider.GOOGLE.value, index=True)
    provider_account_id: Mapped[str] = mapped_column(String(190))
    email: Mapped[str | None] = mapped_column(String(320))
    access_token: Mapped[str | None] = mapped_column(Text)
    refresh_token: Mapped[str | None] = mapped_column(Text)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime)
    raw_profile: Mapped[dict | None] = mapped_column(JSON)

    user: Mapped["User"] = relationship()


class Bookmark(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "bookmarks"
    __table_args__ = (
        UniqueConstraint("user_id", "offer_id", name="uq_bookmarks_user_offer"),
        Index("ix_bookmarks_user_created", "user_id", "created_at"),
    )

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    offer_id: Mapped[str] = mapped_column(ForeignKey("offers.id", ondelete="CASCADE"), index=True)
    note: Mapped[str | None] = mapped_column(String(500))
    notify_on_expiry: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_on_price_drop: Mapped[bool] = mapped_column(Boolean, default=True)

    user: Mapped["User"] = relationship(back_populates="bookmarks")
    offer: Mapped["Offer"] = relationship()  # noqa: F821


class RecentView(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "recent_views"
    __table_args__ = (Index("ix_recent_views_user_created", "user_id", "created_at"),)

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    offer_id: Mapped[str] = mapped_column(ForeignKey("offers.id", ondelete="CASCADE"), index=True)
    viewed_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    view_count: Mapped[int] = mapped_column(Integer, default=1)

    user: Mapped["User"] = relationship()
    offer: Mapped["Offer"] = relationship()  # noqa: F821


class Alert(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "alerts"
    __table_args__ = (Index("ix_alerts_user_active", "user_id", "is_active"),)

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(32), default=AlertKind.CATEGORY.value, index=True)
    label: Mapped[str] = mapped_column(String(160))
    query: Mapped[str | None] = mapped_column(String(240))
    category_id: Mapped[str | None] = mapped_column(ForeignKey("categories.id"), index=True)
    brand_id: Mapped[str | None] = mapped_column(ForeignKey("brands.id"), index=True)
    filters: Mapped[dict | None] = mapped_column(JSON, default=dict)
    frequency: Mapped[str] = mapped_column(String(20), default="instant")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_triggered_at: Mapped[datetime | None] = mapped_column(DateTime)

    user: Mapped["User"] = relationship(back_populates="alerts")


class NewsletterSubscriber(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "newsletter_subscribers"

    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    country_code: Mapped[str | None] = mapped_column(String(2))
    interests: Mapped[list | None] = mapped_column(JSON, default=list)
    frequency: Mapped[str] = mapped_column(String(20), default="weekly")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime)
    unsubscribed_at: Mapped[datetime | None] = mapped_column(DateTime)
    token: Mapped[str] = mapped_column(String(64), index=True)


class Report(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "reports"
    __table_args__ = (Index("ix_reports_status_created", "status", "created_at"),)

    offer_id: Mapped[str | None] = mapped_column(ForeignKey("offers.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    reporter_email: Mapped[str | None] = mapped_column(String(320))
    reason: Mapped[str] = mapped_column(String(32), default=ReportReason.OTHER.value, index=True)
    details: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default=ReportStatus.OPEN.value, index=True)
    resolution_note: Mapped[str | None] = mapped_column(Text)
    resolved_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime)

    offer: Mapped["Offer | None"] = relationship()  # noqa: F821
    user: Mapped["User | None"] = relationship(
        back_populates="reports", foreign_keys=[user_id]
    )


class Submission(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """User / partner submitted offers awaiting review."""

    __tablename__ = "submissions"

    submitted_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    submitter_email: Mapped[str | None] = mapped_column(String(320))
    title: Mapped[str] = mapped_column(String(240))
    brand_name: Mapped[str | None] = mapped_column(String(160))
    official_url: Mapped[str] = mapped_column(String(700))
    category_slug: Mapped[str | None] = mapped_column(String(120))
    offer_type: Mapped[str | None] = mapped_column(String(32))
    notes: Mapped[str | None] = mapped_column(Text)
    evidence_url: Mapped[str | None] = mapped_column(String(700))
    status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    reviewed_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_offer_id: Mapped[str | None] = mapped_column(ForeignKey("offers.id"))


class EmailDelivery(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Lightweight outbox so notifications are auditable without a broker."""

    __tablename__ = "email_deliveries"

    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    to_email: Mapped[str] = mapped_column(String(320), index=True)
    subject: Mapped[str] = mapped_column(String(300))
    template: Mapped[str] = mapped_column(String(80))
    payload: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    error: Mapped[str | None] = mapped_column(String(500))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime)


class RateLimitHit(UUIDPrimaryKeyMixin, Base):
    """Observability only - mirrors limiter decisions for the admin panel."""

    __tablename__ = "rate_limit_hits"

    scope: Mapped[str] = mapped_column(String(120), index=True)
    identifier: Mapped[str] = mapped_column(String(120), index=True)
    hits: Mapped[int] = mapped_column(Integer, default=1)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)