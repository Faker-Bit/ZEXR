"""Analytics: raw events + rolled-up daily aggregates."""

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
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utcnow
from app.models.enums import EventType


class Event(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "events"
    __table_args__ = (Index("ix_events_type_created", "event_type", "created_at"),)

    event_type: Mapped[str] = mapped_column(String(32), default=EventType.PAGE_VIEW.value, index=True)
    entity_type: Mapped[str | None] = mapped_column(String(40))
    entity_id: Mapped[str | None] = mapped_column(String(40), index=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    session_id: Mapped[str | None] = mapped_column(String(64), index=True)
    path: Mapped[str | None] = mapped_column(String(500))
    referrer: Mapped[str | None] = mapped_column(String(500))
    country_code: Mapped[str | None] = mapped_column(String(2), index=True)
    currency: Mapped[str | None] = mapped_column(String(3))
    value: Mapped[float | None] = mapped_column(Float)
    referrer_domain: Mapped[str | None] = mapped_column(String(160))
    properties: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class DailyStat(UUIDPrimaryKeyMixin, Base):
    """Pre-aggregated counters powering the admin dashboard without heavy scans."""

    __tablename__ = "daily_stats"
    __table_args__ = (UniqueConstraint("day", "metric", "dimension_key", name="uq_daily_stats_dim"),)

    day: Mapped[date] = mapped_column(Date, index=True)
    metric: Mapped[str] = mapped_column(String(48), index=True)
    dimension: Mapped[str | None] = mapped_column(String(48))
    dimension_key: Mapped[str | None] = mapped_column(String(64))
    value: Mapped[float] = mapped_column(Float, default=0.0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class SearchQueryLog(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "search_query_logs"
    __table_args__ = (Index("ix_search_logs_created", "created_at"),)

    query: Mapped[str] = mapped_column(String(300), index=True)
    normalised_query: Mapped[str | None] = mapped_column(String(300), index=True)
    intent: Mapped[str | None] = mapped_column(String(40), index=True)
    filters: Mapped[dict | None] = mapped_column(JSON)
    result_count: Mapped[int] = mapped_column(Integer, default=0)
    took_ms: Mapped[float | None] = mapped_column(Float)
    zero_results: Mapped[bool] = mapped_column(Boolean, default=False)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    country_code: Mapped[str | None] = mapped_column(String(2))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)