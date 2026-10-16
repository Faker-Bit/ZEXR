"""HTML listing adapter — reads a publisher's public offer index page.

Configured from the source's `config` column:

```json
{
  "list_url": "https://example.com/offers",
  "item_selector": "article.offer-card",
  "title_selector": "h3 a",
  "link_attribute": "href",
  "description_selector": "p",
  "absolute_links": true,
  "same_host_only": true,
  "require_text": ["free", "trial"]
}
```

CSS selectors are powered by BeautifulSoup + soupsieve.  Pages that need
JavaScript to render their list must be flagged `requires_js` on the source — the
adapter then refuses to run and the offer is labelled *needs manual
verification* rather than guessed at.
"""

from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urljoin, urlparse

from app.discovery.adapters.base import AdapterContext, AdapterOutcome, SourceAdapter
from app.discovery.adapters.rss import strip_html
from app.discovery.base import FetchResult, fetcher
from app.models.enums import OfferType
from app.schemas.offer import DiscoveredItem

OFFER_HINT_RE = re.compile(
    r"\b(free|trial|discount|\d{1,3}%\s*off|save|credit|deal|promo|coupon|voucher|cashback|limited time)\b",
    re.IGNORECASE,
)




def _scrape_number(node, selector: str | None) -> float | None:
    """Pull a number out of a matched node, tolerating `$`, `%` and commas.

    Handles "599", "$5.99", "-70%", "$1,234.50" — anything that is not a plain
    number is skipped rather than coerced to 0, because a wrong price is worse
    than a missing one.
    """
    if not selector:
        return None
    found = node.select_one(selector)
    if found is None:
        return None
    text = found.get_text(" ", strip=True)
    match = re.search(r"-?\d[\d,]*(?:\.\d+)?", text)
    if not match:
        return None
    try:
        return float(match.group(0).replace(",", ""))
    except ValueError:
        return None



def _scrape_price(node, selector: str | None) -> float | None:
    """Like `_scrape_number`, but also understands the word "Free".

    Storefronts render a free price as text rather than a number, and for a
    giveaway that *is* the price: 0, not "unknown".
    """
    if not selector:
        return None
    found = node.select_one(selector)
    if found is None:
        return None
    text = found.get_text(" ", strip=True)
    if not text:
        return None
    if "free" in text.lower():
        return 0.0
    return _scrape_number(node, selector)


def _forced_type(ctx: AdapterContext) -> OfferType | None:
    """Offer type forced by config, for listings whose nature is known.

    A free-to-keep promotion carries no price evidence, so inferring its type
    from text is guesswork; the source config states it outright instead.
    """
    value = ctx.option("force_offer_type")
    if not value:
        return None
    try:
        return OfferType(str(value).strip().lower())
    except ValueError:
        return None

class HtmlListingAdapter(SourceAdapter):
    name = "html_listing"

    def fetch(self, ctx: AdapterContext) -> FetchResult:
        if ctx.source.requires_js:
            return FetchResult(
                False,
                error="source is marked requires_js; cannot read a JS-rendered listing",
                skipped_reason="requires_js",
            )
        if ctx.source.is_paywalled and not ctx.option("allow_paywalled", False):
            return FetchResult(
                False,
                error="source is behind a login/paywall; refusing to bypass access controls",
                skipped_reason="paywalled",
            )
        list_url = ctx.option("list_url") or ctx.source.feed_url or ctx.source.homepage_url
        return fetcher.fetch(
            list_url,
            source_key=ctx.source.key,
            respect_robots=ctx.source.respect_robots,
            min_interval=ctx.source.min_request_interval_seconds,
            per_hour=ctx.source.rate_limit_per_hour,
        )

    def parse(self, ctx: AdapterContext) -> AdapterOutcome:
        outcome = AdapterOutcome()
        payload = ctx.payload
        if payload is None or not payload.text:
            outcome.warnings.append("empty response body")
            return outcome

        try:
            from bs4 import BeautifulSoup
        except ImportError:  # pragma: no cover
            outcome.warnings.append("beautifulsoup4 is not installed")
            return outcome

        soup = BeautifulSoup(payload.text, "lxml" if _has_lxml() else "html.parser")
        base_url = payload.url or ctx.option("list_url") or ctx.source.homepage_url
        host = urlparse(base_url).netloc

        selector = ctx.option("item_selector") or "article, li.offer, .deal, .offer"
        nodes = soup.select(selector)
        if not nodes:
            outcome.warnings.append(f"no nodes matched {selector!r}")
            return outcome

        title_sel = ctx.option("title_selector") or "h1, h2, h3, h4, .title"
        link_attr = ctx.option("link_attribute", "href")
        desc_sel = ctx.option("description_selector") or "p, .description, .summary"
        require_text = [t.lower() for t in (ctx.option("require_text") or [])]
        same_host = bool(ctx.option("same_host_only", True))
        limit = int(ctx.option("max_items", ctx.source.max_items) or 50)

        for node in nodes:
            outcome.total_seen += 1
            if len(outcome.items) >= limit:
                break

            title_node = node.select_one(title_sel)
            # Card-style listings (Steam's search rows, for example) are
            # themselves the anchor, so the node may carry the link rather than
            # containing one. Check the node before looking for a descendant.
            if getattr(node, "name", None) == "a" and node.get(link_attr):
                anchor = node
                href = node.get(link_attr)
                title = strip_html(
                    (title_node.get_text(" ") if title_node else node.get_text(" "))
                )
            else:
                anchor = title_node or node
                if getattr(anchor, "name", None) == "a":
                    href = anchor.get(link_attr)
                else:
                    link = node.select_one("a[href]")
                    href = link.get("href") if link else None
                title = strip_html(
                    anchor.get_text(" ") if hasattr(anchor, "get_text") else str(anchor)
                )
            if not href or not title:
                outcome.warnings.append("item without title or link")
                continue

            url = urljoin(base_url, href)
            if urlparse(url).netloc != host and same_host:
                outcome.warnings.append(f"skipped off-host link {url}")
                continue

            description_node = node.select_one(desc_sel)
            description = (
                strip_html(description_node.get_text(" ")) if description_node else None
            )

            haystack = f"{title} {description or ''}"
            # The keyword heuristic guards against scraping a nav bar or a
            # "related items" block. A store search filtered to promotions has
            # already done that filtering server-side, so sources can opt out.
            needs_hint = bool(ctx.option("require_offer_hint", True))
            if needs_hint and not OFFER_HINT_RE.search(haystack):
                outcome.warnings.append(f"skipped non-offer entry: {title[:60]!r}")
                continue
            if require_text and not any(term in haystack.lower() for term in require_text):
                continue

    # Optional structured fields. Store listings render prices and discount
            # percentages in sibling nodes, and without these the offer imports with
            # no price at all — which for a discount site is the whole point.
            original_price = _scrape_price(node, ctx.option("original_price_selector"))
            promo_price = _scrape_price(node, ctx.option("promo_price_selector"))
            discount_pct = _scrape_number(node, ctx.option("discount_selector"))

            outcome.items.append(
                DiscoveredItem(
    external_id=url,
                    title=title[:240],
                    description=(description or "")[:MAX] or None,
                    url=url[:700],
                    original_price=original_price,
                    category_slug=ctx.option("category_slug") or None,
                    promo_price=promo_price,
                    offer_type=_forced_type(ctx) or OfferType.FREE
                    if (promo_price == 0 or discount_pct == 100)
                    else OfferType.DISCOUNT
                    if discount_pct
                    else None,
                    raw={
                        "selector": selector,
                        "discount_percent": discount_pct,
                        "tags": [t.get_text(strip=True) for t in node.select(".tag, .badge")][:10],
                    },
                )
                )
        return outcome


MAX = 2000


def _has_lxml() -> bool:
    try:
        import lxml  # noqa: F401

        return True
    except ImportError:  # pragma: no cover
        return False


def extract_expiry_hint(text: str) -> datetime | None:
    """Read a date that is literally present in the text. Never guesses."""
    from app.discovery.adapters.json_api import parse_datetime

    patterns = [
        r"(?:ends?|expires?|valid|until|through)\s+(?:on\s+)?([0-9]{1,2}[/-][0-9]{1,2}[/-][0-9]{2,4})",
        r"([0-9]{4}-[0-9]{2}-[0-9]{2})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            parsed = parse_datetime(match.group(1))
            if parsed:
                return parsed
    return None
