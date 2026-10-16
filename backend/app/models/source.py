"""Data sources + discovery run bookkeeping."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utcnow
from app.models.enums import SourceHealth, SourceType


class Source(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A legitimate upstream we are allowed to read offers from.

    Adding a new integration is a matter of inserting a row here plus (optionally)
    a matching adapter in `app.discovery.adapters` — no migrations required.
    """

    __tablename__ = "sources"

    key: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    publisher: Mapped[str] = mapped_column(String(160))
    source_type: Mapped[str] = mapped_column(String(32), default=SourceType.RSS.value, index=True)
    adapter: Mapped[str | None] = mapped_column(String(60))
    homepage_url: Mapped[str] = mapped_column(String(500))
    feed_url: Mapped[str | None] = mapped_column(String(700))
    api_docs_url: Mapped[str | None] = mapped_column(String(500))
    api_key_env: Mapped[str | None] = mapped_column(String(80))
    config: Mapped[dict | None] = mapped_column(JSON, default=dict)

    # crawl policy - the crawler refuses to act outside these bounds
    respect_robots: Mapped[bool] = mapped_column(Boolean, default=True)
    requires_js: Mapped[bool] = mapped_column(Boolean, default=False)
    is_paywalled: Mapped[bool] = mapped_column(Boolean, default=False)
    rate_limit_per_hour: Mapped[int] = mapped_column(Integer, default=30)
    min_request_interval_seconds: Mapped[float] = mapped_column(Float, default=120.0)
    cache_ttl_seconds: Mapped[int] = mapped_column(Integer, default=900)
    max_items: Mapped[int] = mapped_column(Integer, default=50)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    health: Mapped[str] = mapped_column(String(20), default=SourceHealth.HEALTHY.value, index=True)
    trust_weight: Mapped[float] = mapped_column(Float, default=0.5)
    license_note: Mapped[str | None] = mapped_column(String(400))
    terms_url: Mapped[str | None] = mapped_column(String(500))

    # runtime stats
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
    total_items_seen: Mapped[int] = mapped_column(Integer, default=0)
    total_items_accepted: Mapped[int] = mapped_column(Integer, default=0)
    total_items_duplicate: Mapped[int] = mapped_column(Integer, default=0)
    total_items_rejected: Mapped[int] = mapped_column(Integer, default=0)

    offers: Mapped[list["Offer"]] = relationship(back_populates="source")  # noqa: F821
    runs: Mapped[list["SourceRun"]] = relationship(
        back_populates="source", cascade="all, delete-orphan"
    )
    candidates: Mapped[list["DiscoveryCandidate"]] = relationship(
        back_populates="source", cascade="all, delete-orphan"
    )

    @property
    def is_usable(self) -> bool:
        return self.is_active and self.health != SourceHealth.PAUSED.value


class SourceRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "source_runs"

    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(24), default="running")
    http_status: Mapped[int | None] = mapped_column(Integer)
    items_seen: Mapped[int] = mapped_column(Integer, default=0)
    items_accepted: Mapped[int] = mapped_column(Integer, default=0)
    items_duplicate: Mapped[int] = mapped_column(Integer, default=0)
    items_rejected: Mapped[int] = mapped_column(Integer, default=0)
    skipped_reason: Mapped[str | None] = mapped_column(String(200))
    error: Mapped[str | None] = mapped_column(String(600))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    raw_meta: Mapped[dict | None] = mapped_column(JSON)

    source: Mapped["Source"] = relationship(back_populates="runs")


class DiscoveryCandidate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Raw, un-normalised item scraped from a source.

    Stored before normalisation so admins can audit exactly what we saw and why
    an item was accepted, rejected or duplicated.
    """

    __tablename__ = "discovery_candidates"

    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"), index=True)
    external_id: Mapped[str | None] = mapped_column(String(300), index=True)
    source_url: Mapped[str] = mapped_column(String(700))
    raw_title: Mapped[str] = mapped_column(String(400))
    raw_description: Mapped[str | None] = mapped_column(Text)
    raw_payload: Mapped[dict | None] = mapped_column(JSON)
    fingerprint: Mapped[str] = mapped_column(String(64), index=True)

    status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    rejection_reason: Mapped[str | None] = mapped_column(String(240))
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    offer_id: Mapped[str | None] = mapped_column(ForeignKey("offers.id"))
    duplicate_of_id: Mapped[str | None] = mapped_column(ForeignKey("offers.id"))
    reviewed_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    seen_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)

    source: Mapped["Source"] = relationship(back_populates="candidates")