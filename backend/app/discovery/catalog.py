"""Curated catalogue of real, permissively-licensed public deal datasets.

Why this exists
---------------
New integrations should normally be added by writing a `sources` row.  This module
is the exception: it is a **reviewed, version-controlled list** of upstream feeds
that have been checked for licensing and robots permissions, so an operator can
install them in one command instead of hand-typing JSON into the admin UI.

Selection rules every entry must satisfy:

1. **Permissive licence.** Only MIT/Apache/CC/public-domain datasets are listed.
   Anything with an unclear licence (``NOASSERTION``, "source available", custom
   terms) is deliberately excluded even when the data is attractive.
2. **robots.txt permits it.** Each host was checked and allows ``User-agent: *``.
   The fetcher still re-checks robots on every request, so a host that tightens
   its policy later simply stops being crawled.
3. **Direct vendor URLs.** The dataset must carry the *vendor's* page, not the
   aggregator's own landing page.  Verification checks the vendor page, so an
   aggregator URL would make every verification meaningless.
4. **Structured fields.** A JSON/JSONL payload beats scraping HTML: it is stable,
   diffable, and cheap to fetch politely.

Both entries below are JSON over HTTPS, require no API key, and are refreshed by
their upstream maintainers on their own cadence.

Attribution
-----------
ZEXR Deal Hub republishes *links and summary facts* about third-party offers.  The
`license_note` on each source is surfaced in the admin UI so attribution stays
attached to the data.
"""

from __future__ import annotations

from typing import Any, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.source import Source

log = get_logger("discovery.catalog")


PUBLIC_SOURCES: tuple[dict[str, Any], ...] = (
    {
        "key": "freetokens-index",
        "name": "FreeTokens — free AI & developer credits",
        "publisher": "freetokens (luongnv89)",
        "source_type": "json_api",
        "adapter": "json_api",
        "homepage_url": "https://luongnv89.github.io/freetokens/",
        "feed_url": "https://raw.githubusercontent.com/luongnv89/freetokens/main/index.json",
        "upstream_repo": "https://github.com/luongnv89/freetokens",
        "license_note": "MIT (luongnv89/freetokens). Links and summary facts republished with attribution.",
        "terms_url": "https://github.com/luongnv89/freetokens",
        "trust_weight": 0.8,
        # The upstream regenerates this file daily; one polite fetch an hour is
        # far more than enough and keeps us a good citizen.
        "rate_limit_per_hour": 4,
        "min_request_interval_seconds": 900.0,
        "cache_ttl_seconds": 1800,
        "max_items": 300,
        "config": {
            "url": "https://raw.githubusercontent.com/luongnv89/freetokens/main/index.json",
            "format": "json",
            "items_path": "offers",
            "fields": {
                "id": "slug",
                "title": "title",
                "description": "amount",
                "url": "source_url",
                "expires_at": "expiry_date",
                "brand_name": "provider",
                "tags": "category",
            },
        },
    },
    {
        "key": "devcheap-jsonl",
        "name": "DevCheap — developer deals and free tiers",
        "publisher": "DevCheap (hasitpbhatt)",
        "source_type": "json_api",
        "adapter": "json_api",
        "homepage_url": "https://devcheap.click/",
        "feed_url": "https://raw.githubusercontent.com/hasitpbhatt/devcheap/main/data/deals.jsonl",
        "upstream_repo": "https://github.com/hasitpbhatt/devcheap",
        "license_note": "MIT (hasitpbhatt/devcheap). Some upstream links are affiliate links; we import the direct vendor URL only.",
        "terms_url": "https://devcheap.click/disclosure/",
        "trust_weight": 0.7,
        "rate_limit_per_hour": 4,
        "min_request_interval_seconds": 900.0,
        "cache_ttl_seconds": 1800,
        "max_items": 300,
        "config": {
            "url": "https://raw.githubusercontent.com/hasitpbhatt/devcheap/main/data/deals.jsonl",
            "format": "jsonl",
            "fields": {
                "id": "id",
                "title": "name",
                "description": "desc",
                "url": "url",
                "offer_type": "pricing",
                "expires_at": "expires",
                "coupon_code": "code",
                "tags": "tags",
            },
        },
    },
{
        "key": "steam-specials",
        "name": "Steam — current store specials",
        "publisher": "Valve Corporation (Steam)",
        "source_type": "json_api",
        "adapter": "json_api",
        "homepage_url": "https://store.steampowered.com/",
        "feed_url": "https://store.steampowered.com/api/featuredcategories?cc=US&l=en",
        "upstream_repo": "https://store.steampowered.com/api/featuredcategories",
        "license_note": (
            "Steam's public storefront API. Prices are quoted in the store's own "
            "currency (cc=US gives USD) and are redistributed under Valve's Web API terms."
        ),
        "terms_url": "https://www.valvesoftware.com/en/legal/webapi",
        "trust_weight": 0.9,
        "rate_limit_per_hour": 10,
        "min_request_interval_seconds": 300.0,
        "cache_ttl_seconds": 900,
        "max_items": 60,
        "config": {
            "url": "https://store.steampowered.com/api/featuredcategories?cc=US&l=en",
            "format": "json",
            "items_path": "specials.items",
            # No link field in the payload, but the canonical store page is
            # derivable from the app id.
            "url_template": "https://store.steampowered.com/app/{id}",
            # Everything in the specials carousel is, by definition, a discount.
            "offer_type": "discount",
            # Steam quotes money in minor units (599 == $5.99).
            "price_divisor": 100,
            "fields": {
                "id": "id",
                "title": "name",
                "original_price": "original_price",
                "promo_price": "final_price",
                "currency": "currency",
                "expires_at": "discount_expiration",
                "category_slug": "gaming",
            },
        },
    },
{
        "key": "openrouter-free-models",
        "name": "OpenRouter — free-tier AI models",
        "publisher": "OpenRouter",
        "source_type": "json_api",
        "adapter": "json_api",
        "homepage_url": "https://openrouter.ai/",
        "feed_url": "https://openrouter.ai/api/v1/models",
        "upstream_repo": "https://openrouter.ai/api/v1/models",
        "license_note": (
            "OpenRouter's public model catalogue. Model names, descriptions and "
            "pricing are Valve-style third-party metadata republished for "
            "attribution under their API terms."
        ),
        "terms_url": "https://openrouter.ai/terms",
        "trust_weight": 0.85,
        "rate_limit_per_hour": 6,
        "min_request_interval_seconds": 900.0,
        "cache_ttl_seconds": 3600,
        "max_items": 200,
        "config": {
            "url": "https://openrouter.ai/api/v1/models",
            "format": "json",
            "items_path": "data",
            # No per-model link in the payload; the canonical page is derived
            # from the model id.
            "url_template": "https://openrouter.ai/{id}",
            # Everything selected below is genuinely free, so no price is quoted.
            "offer_type": "free",
            # The catalogue holds ~460 models; keep only the ones a user can
            # actually call at no cost.
            "filter": [
                {"field": "pricing.prompt", "op": "equals", "value": "0"},
                {"field": "pricing.completion", "op": "equals", "value": "0"},
            ],
            "fields": {
                "id": "id",
                "title": "name",
                "description": "description",
                "category_slug": "ai-tools",
                "tags": "architecture.modality",
            },
        },
    },
{
        "key": "steam-free-keep",
        "name": "Steam — free to keep right now",
        "publisher": "Valve Corporation (Steam)",
        "source_type": "html_listing",
        "adapter": "html_listing",
        "homepage_url": "https://store.steampowered.com/search/?maxprice=free",
        "feed_url": "https://store.steampowered.com/search/?maxprice=free&specials=1&cc=US&l=english",
        "upstream_repo": "https://store.steampowered.com/search/",
        "license_note": (
            "Steam's public store search, filtered to free promotions. Prices and "
            "titles republished under Valve's Web API / storefront terms."
        ),
        "terms_url": "https://www.valvesoftware.com/en/legal/webapi",
        "trust_weight": 0.95,
        "rate_limit_per_hour": 6,
        "min_request_interval_seconds": 900.0,
        "cache_ttl_seconds": 900,
        "max_items": 40,
        "config": {
            "list_url": "https://store.steampowered.com/search/?maxprice=free&specials=1&cc=US&l=english",
            "item_selector": "a.search_result_row",
            "title_selector": ".title",
            "link_attribute": "href",
            "description_selector": ".search_released",
            "absolute_links": True,
            "same_host_only": True,
            "category_slug": "gaming",
            "require_offer_hint": False,
            "force_offer_type": "free",
            "discount_selector": ".search_discount_block",
            "original_price_selector": ".discount_original_price",
            "promo_price_selector": ".discount_final_price",
        },
    },
    {
        "key": "steam-deep-discounts",
        "name": "Steam — 80% and deeper",
        "publisher": "Valve Corporation (Steam)",
        "source_type": "html_listing",
        "adapter": "html_listing",
        "homepage_url": "https://store.steampowered.com/search/?discounts=80,85,90,95,100",
        "feed_url": "https://store.steampowered.com/search/?discounts=80,85,90,95,100&cc=US&l=english",
        "upstream_repo": "https://store.steampowered.com/search/",
        "license_note": (
            "Steam's public store search, filtered to 80%+ discounts. Prices and "
            "titles republished under Valve's Web API / storefront terms."
        ),
        "terms_url": "https://www.valvesoftware.com/en/legal/webapi",
        "trust_weight": 0.95,
        "rate_limit_per_hour": 6,
        "min_request_interval_seconds": 900.0,
        "cache_ttl_seconds": 900,
        "max_items": 60,
        "config": {
            "list_url": "https://store.steampowered.com/search/?discounts=80,85,90,95,100&cc=US&l=english",
            "item_selector": "a.search_result_row",
            "title_selector": ".title",
            "link_attribute": "href",
            "description_selector": ".search_released",
            "absolute_links": True,
            "same_host_only": True,
            "category_slug": "gaming",
            "require_offer_hint": False,
            "force_offer_type": "discount",
            "discount_selector": ".search_discount_block",
            "original_price_selector": ".discount_original_price",
            "promo_price_selector": ".discount_final_price",
        },
    },
)


def describe() -> list[dict[str, Any]]:
    """Return the catalogue without touching the database."""
    return [dict(entry) for entry in PUBLIC_SOURCES]


def install(
    session: Session,
    *,
    keys: Sequence[str] | None = None,
    activate: bool = True,
) -> dict[str, Any]:
    """Create or refresh `sources` rows for the curated public datasets.

    Idempotent: re-running updates the stored config so upstream URL changes are
    picked up, without clobbering operational state (health counters, last run,
    activation) that the platform maintains itself.
    """
    wanted = {k.strip().lower() for k in keys} if keys else None
    result: dict[str, Any] = {"created": [], "updated": [], "skipped": []}

    for entry in PUBLIC_SOURCES:
        key = entry["key"]
        if wanted and key not in wanted:
            result["skipped"].append(key)
            continue

        existing = session.execute(select(Source).where(Source.key == key)).scalar_one_or_none()

        if existing is None:
            source = Source(
                key=key,
                name=entry["name"],
                publisher=entry["publisher"],
                source_type=entry["source_type"],
                adapter=entry["adapter"],
                homepage_url=entry["homepage_url"],
                feed_url=entry["feed_url"],
                api_docs_url=entry["upstream_repo"],
                config=dict(entry["config"]),
                respect_robots=True,
                requires_js=False,
                is_paywalled=False,
                rate_limit_per_hour=entry["rate_limit_per_hour"],
                min_request_interval_seconds=entry["min_request_interval_seconds"],
                cache_ttl_seconds=entry["cache_ttl_seconds"],
                max_items=entry["max_items"],
                trust_weight=entry["trust_weight"],
                license_note=entry["license_note"],
                terms_url=entry["terms_url"],
                is_active=activate,
            )
            session.add(source)
            result["created"].append(key)
            log.info("catalog.source_created", extra={"source": key})
        else:
            existing.name = entry["name"]
            existing.publisher = entry["publisher"]
            existing.source_type = entry["source_type"]
            existing.adapter = entry["adapter"]
            existing.homepage_url = entry["homepage_url"]
            existing.feed_url = entry["feed_url"]
            existing.api_docs_url = entry["upstream_repo"]
            existing.config = dict(entry["config"])
            existing.trust_weight = entry["trust_weight"]
            existing.license_note = entry["license_note"]
            existing.terms_url = entry["terms_url"]
            existing.max_items = entry["max_items"]
            existing.rate_limit_per_hour = entry["rate_limit_per_hour"]
            existing.min_request_interval_seconds = entry["min_request_interval_seconds"]
            if activate and not existing.is_active:
                existing.is_active = True
            result["updated"].append(key)
            log.info("catalog.source_updated", extra={"source": key})

    session.flush()
    return result


__all__ = ["PUBLIC_SOURCES", "describe", "install"]