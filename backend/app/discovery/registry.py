"""Adapter registry — maps a source row to the code that can read it."""

from __future__ import annotations

from typing import Callable

from app.discovery.adapters.base import AdapterContext, AdapterOutcome, SourceAdapter
from app.discovery.adapters.html_listing import HtmlListingAdapter
from app.discovery.adapters.json_api import JsonApiAdapter
from app.discovery.adapters.rss import RSSAdapter
from app.models.enums import SourceType

_REGISTRY: dict[str, Callable[[], SourceAdapter]] = {
    "rss": RSSAdapter,
    "atom": RSSAdapter,
    "feed": RSSAdapter,
    "json": JsonApiAdapter,
    "json_api": JsonApiAdapter,
    "rest": JsonApiAdapter,
    "affiliate_api": JsonApiAdapter,
    "partner_api": JsonApiAdapter,
    "api": JsonApiAdapter,
    "html": HtmlListingAdapter,
    "html_listing": HtmlListingAdapter,
    "scrape": HtmlListingAdapter,
}


def register(name: str, factory: Callable[[], SourceAdapter]) -> None:
    """Register a new integration at runtime (no migration required)."""
    _REGISTRY[name.strip().lower()] = factory


def available() -> list[str]:
    return sorted(_REGISTRY)


def get_adapter(name: str | None, source_type: str | None = None) -> SourceAdapter:
    for candidate in (name, source_type):
        if candidate and candidate.lower() in _REGISTRY:
            return _REGISTRY[candidate.lower()]()
    # JSON adapters degrade the most gracefully: an unconfigured source simply
    # returns an empty run instead of mis-parsing a feed.
    return JsonApiAdapter()


def adapter_for_source(source: object) -> SourceAdapter:
    return get_adapter(
        getattr(source, "adapter", None), getattr(source, "source_type", None)
    )


__all__ = [
    "AdapterContext",
    "AdapterOutcome",
    "SourceAdapter",
    "SourceType",
    "adapter_for_source",
    "available",
    "get_adapter",
    "register",
]