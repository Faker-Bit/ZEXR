"""Taxonomy: categories, brands, countries."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Category(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "categories"

    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    tagline: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    icon: Mapped[str] = mapped_column(String(60), default="tag")
    color: Mapped[str] = mapped_column(String(20), default="lime")
    group_name: Mapped[str | None] = mapped_column(String(80), index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=100)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Optional SEO overrides; fall back to the generated description.
    seo_title: Mapped[str | None] = mapped_column(String(180))
    seo_description: Mapped[str | None] = mapped_column(String(320))
    keywords: Mapped[list | None] = mapped_column(JSON, default=list)
    aliases: Mapped[list | None] = mapped_column(JSON, default=list)

    offers: Mapped[list["Offer"]] = relationship(back_populates="category")  # noqa: F821
    brands: Mapped[list["Brand"]] = relationship(back_populates="category")  # noqa: F821

    @property
    def offer_count(self) -> int:
        return getattr(self, "_offer_count", 0)


class Brand(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "brands"
    __table_args__ = (
        UniqueConstraint("name", name="uq_brands_name"),
        Index("ix_brands_domain_active", "domain", "is_active"),
    )

    name: Mapped[str] = mapped_column(String(120), index=True)
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    domain: Mapped[str | None] = mapped_column(String(190), index=True)
    website_url: Mapped[str | None] = mapped_column(String(500))
    logo_url: Mapped[str | None] = mapped_column(String(500))
    accent_color: Mapped[str | None] = mapped_column(String(20))
    description: Mapped[str | None] = mapped_column(Text)
    aliases: Mapped[list | None] = mapped_column(JSON, default=list)
    country_code: Mapped[str | None] = mapped_column(String(2), ForeignKey("countries.code"))
    category_id: Mapped[str | None] = mapped_column(ForeignKey("categories.id"), index=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    followers_count: Mapped[int] = mapped_column(Integer, default=0)

    offers: Mapped[list["Offer"]] = relationship(back_populates="brand")  # noqa: F821
    category: Mapped["Category | None"] = relationship(back_populates="brands")


class Country(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "countries"
    __table_args__ = (UniqueConstraint("code", name="uq_countries_code"),)

    code: Mapped[str] = mapped_column(String(2), index=True)
    name: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(120), index=True)
    flag_emoji: Mapped[str | None] = mapped_column(String(16))
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    region: Mapped[str | None] = mapped_column(String(60), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=100)