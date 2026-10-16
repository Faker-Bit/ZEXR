"""Shared schema primitives."""

from __future__ import annotations

import math
from datetime import date, datetime
from typing import Annotated, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

T = TypeVar("T")


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


Slug = Annotated[str, Field(min_length=1, max_length=200, pattern=r"^[a-z0-9\-]+$")]


class QuotaMeta(BaseModel):
    """Free-tier truncation details attached to listing responses.

    `total` is the real catalogue count and is never reduced, so the UI can say
    "showing 12 of 410" rather than pretending the catalogue is empty.
    """

    limited: bool = False
    shown: int = 0
    limit: int | None = None
    total: int = 0
    plan: str = "free"
    is_pro: bool = False
    reason: str | None = None




class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int
    has_next: bool
    has_prev: bool
    meta: QuotaMeta | None = None

    @classmethod
    def build(cls, items: list[T], total: int, page: int, page_size: int) -> "Page[T]":
        pages = max(1, math.ceil(total / page_size)) if page_size else 1
        return cls(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            pages=pages,
            has_next=page < pages,
            has_prev=page > 1,
        )


class Message(BaseModel):
    detail: str
    ok: bool = True


class HealthStatus(BaseModel):
    status: str = "ok"
    version: str
    environment: str
    database: str
    cache: str
    scheduler: str
    checked_at: datetime


class DateRange(BaseModel):
    start: date | None = None
    end: date | None = None

    @field_validator("end")
    @classmethod
    def _order(cls, v: date | None, info) -> date | None:  # type: ignore[no-untyped-def]
        start = info.data.get("start")
        if v and start and v < start:
            raise ValueError("end must be after start")
        return v


class WebsiteUrl(str):
    """Permissive URL string that also accepts scheme-less input."""

    @classmethod
    def __get_pydantic_core_schema__(cls, source_type, handler):  # type: ignore[no-untyped-def]
        from pydantic_core import core_schema

        return core_schema.no_info_after_validator_function(
            cls._validate,
            core_schema.str_schema(min_length=4, max_length=700),
        )

    @staticmethod
    def _validate(value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("URL cannot be empty")
        if not value.startswith(("http://", "https://")):
            value = "https://" + value
        from urllib.parse import urlparse

        parsed = urlparse(value)
        if not parsed.netloc or "." not in parsed.netloc:
            raise ValueError("Invalid URL")
        return value


def safe_url(value: str | HttpUrl | None) -> str | None:
    if value is None:
        return None
    text = str(value)
    if text.startswith(("http://", "https://")):
        return text
    return f"https://{text}"