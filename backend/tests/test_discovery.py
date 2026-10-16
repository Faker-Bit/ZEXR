"""Discovery engine: adapters, normalisation, dedupe, politeness."""

from __future__ import annotations

from datetime import datetime

import pytest

from app.discovery.adapters.base import AdapterContext
from app.discovery.adapters.html_listing import HtmlListingAdapter
from app.discovery.adapters.json_api import JsonApiAdapter, build_url, dig, parse_datetime
from app.discovery.adapters.rss import RSSAdapter, strip_html
from app.discovery.base import FetchResult, PoliteFetcher, is_safe_url
from app.discovery.dedupe import canonical_url, fingerprint_for, title_similarity
from app.discovery.normalize import (
    classify_offer_type,
    detect_countries,
    detect_eligibility,
    extract_coupon,
    extract_duration,
    extract_expiry,
    extract_prices,
    fingerprint_for as draft_fingerprint,
    normalise,
    tidy_title,
)
from app.discovery.registry import available, get_adapter
from app.models.enums import OfferType
from app.schemas.offer import DiscoveredItem
from app.models.source import Source


# ------------------------------------------------------------- politeness
@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://example.com/offers", True),
        ("http://example.com/offers", True),
        ("ftp://example.com/offers", False),
        ("file:///etc/passwd", False),
        ("http://localhost:8000/admin", False),
        ("http://127.0.0.1/x", False),
        ("https://192.168.1.1/x", False),
        ("javascript:alert(1)", False),
    ],
)
def test_is_safe_url(url, expected):
    assert is_safe_url(url) is expected


def test_fetcher_refuses_when_discovery_disabled(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "discovery_enabled", False)
    result = PoliteFetcher().fetch("https://example.com", source_key="t")
    assert result.ok is False
    assert result.skipped_reason == "disabled"


def test_fetcher_refuses_unsafe_url(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "discovery_enabled", True)
    result = PoliteFetcher().fetch("http://localhost/admin", source_key="t")
    assert result.ok is False
    assert result.skipped_reason == "unsafe_url"


def test_fetcher_respects_robots(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "discovery_enabled", True)
    fetcher = PoliteFetcher()
    monkeypatch.setattr(fetcher.robots, "allowed", lambda url: (False, "disallowed by robots.txt", None))
    result = fetcher.fetch("https://example.com/deals", source_key="t", respect_robots=True)
    assert result.ok is False
    assert result.skipped_reason == "robots_disallowed"


def test_throttle_spaces_requests():
    from app.discovery.base import SourceThrottle
    import time

    throttle = SourceThrottle()
    start = time.monotonic()
    throttle.wait("a", "host-a", min_interval=0.12, per_hour=100)
    throttle.wait("a", "host-a", min_interval=0.12, per_hour=100)
    assert time.monotonic() - start >= 0.1


# ------------------------------------------------------------- registry
def test_registry_maps_every_source_type():
    assert "rss" in available()
    assert "json_api" in available()
    assert "html_listing" in available()
    assert isinstance(get_adapter("rss"), RSSAdapter)
    assert isinstance(get_adapter(None, "json_api"), JsonApiAdapter)
    assert isinstance(get_adapter(None, None), JsonApiAdapter)


# ------------------------------------------------------------- helpers
def test_strip_html():
    assert strip_html("<p>Hello <b>world</b>&nbsp;!</p>") == "Hello world !"


def test_dig_supports_dotted_paths():
    data = {"data": {"offers": [{"name": "x"}]}}
    assert dig(data, "data.offers.0.name") == "x"
    assert dig(data, "data.missing.key") is None


def test_build_url_appends_query():
    url = build_url({"url": "https://x.dev/offers", "query": {"a": "1"}}, None)
    assert url == "https://x.dev/offers?a=1"


def test_parse_datetime_variants():
    assert parse_datetime("2026-01-02T03:04:05Z") == datetime(2026, 1, 2, 3, 4, 5)
    assert parse_datetime("not a date") is None
    assert parse_datetime(1767222245) is not None


# ------------------------------------------------------------- normaliser
def test_classify_offer_type_priority():
    assert classify_offer_type("Get 3 months free trial") is OfferType.FREE_TRIAL
    assert classify_offer_type("$50 in free credits for new users") is OfferType.FREE_CREDITS
    assert classify_offer_type("Use code SAVE20 for 20% off") is OfferType.DISCOUNT
    assert classify_offer_type("Earn cashback on every order") is OfferType.CASHBACK
    assert classify_offer_type("Free forever, no strings attached") is OfferType.FREE


def test_extract_prices_pair():
    original, promo, currency, kind = extract_prices("Was $20 now $10 for 3 months")
    assert original == 20.0
    assert promo == 10.0
    assert currency == "USD"
    assert kind == "percent"


def test_extract_prices_from_discount_percentage():
    original, promo, currency, _ = extract_prices("Get it for $50 — 50% off")
    assert promo == 50.0
    assert original == 100.0


def test_extract_prices_none_when_absent():
    original, promo, _, _ = extract_prices("A great free offer for everyone")
    assert original is None and promo is None


def test_extract_duration():
    assert extract_duration("30 day free trial") == (30, "day")
    assert extract_duration("3 months on us") == (90, "month")
    assert extract_duration("no duration here") == (None, None)


def test_extract_coupon():
    assert extract_coupon("Use code SAVE20 today") == "SAVE20"
    assert extract_coupon("nothing here") is None


def test_extract_expiry_only_accepts_future_dates():
    from app.db.base import utcnow

    far = (utcnow().replace(year=utcnow().year + 2)).strftime("%d-%m-%Y")
    past = "01-01-2000"
    assert extract_expiry(f"Offer ends {far}") is not None
    assert extract_expiry(f"Offer ended {past}") is None


def test_detect_eligibility():
    types, needs_card = detect_eligibility("For new users only. Credit card required.")
    assert "new_users" in {t.value for t in types}
    assert needs_card is True

    types, needs_card = detect_eligibility("No credit card required, available worldwide")
    assert needs_card is False


def test_detect_countries():
    assert "IN" in detect_countries("Available in India with prices in rupees")
    assert detect_countries("Available worldwide") == []


def test_tidy_title_strips_site_suffix():
    assert tidy_title("50% off hosting - Example.com") == "50% off hosting"


def test_normalise_never_invents_prices():
    draft = normalise(
        DiscoveredItem(title="Great free trial", description="No prices mentioned", url="https://x.dev/o")
    )
    assert draft.original_price is None
    assert draft.promo_price is None
    assert draft.confidence < 0.8


def test_missing_price_only_warns_for_priced_offer_types():
    """A permanently free offer has no price by definition; a discount does.

    Warning on every absent price used to push real free tiers ("10,000 free
    neurons/day", "free Serverless tier") under the 0.55 confidence threshold,
    so the warning is now limited to types where a price is genuinely expected.
    """
    free_tier = normalise(
        DiscoveredItem(
            title="Cloudflare Workers AI",
            description="Free edge inference with 10,000 free neurons per day.",
            url="https://ai.cloudflare.com",
        )
    )
    assert free_tier.offer_type.value in {"free", "freemium", "free_credits", "free_trial"}
    assert "no price found in source payload" not in free_tier.warnings
    assert free_tier.confidence >= 0.55

    discount = normalise(
        DiscoveredItem(
            title="50% off annual plan",
            description="Fifty percent off any annual subscription this month.",
            url="https://example.com/sale",
        )
    )
    assert discount.offer_type.value == "discount"
    assert "no price found in source payload" in discount.warnings
    assert discount.confidence < 0.55


def test_normalise_extracts_real_fields():
    draft = normalise(
        DiscoveredItem(
            title="Acme Cloud — 3 months free trial, 50% off",
            description="Get 3 months free on the Pro plan. Code SAVE50. Limited time.",
            url="https://acme.dev/pricing",
        )
    )
    assert draft.trial_days == 90
    assert draft.offer_type in (OfferType.FREE_TRIAL, OfferType.DISCOUNT)
    assert draft.confidence > 0.55


def test_normalise_confidence_penalises_empty_payload():
    good = normalise(
        DiscoveredItem(
            title="Acme Pro free for 30 days",
            description="A generous description of the offer terms and conditions.",
            url="https://acme.dev/x",
            brand_name="Acme",
        )
    )
    bad = normalise(DiscoveredItem(title="x", description=None, url="https://acme.dev/y"))
    assert good.confidence > bad.confidence


def test_fingerprint_is_order_independent_and_stable():
    a = normalise(DiscoveredItem(title="Acme 50% off", url="https://acme.dev/a"))
    b = normalise(DiscoveredItem(title="Acme 50% off", url="https://acme.dev/b?utm=x"))
    assert fingerprint_for(a) == fingerprint_for(b)


def test_title_similarity():
    assert title_similarity("Acme Cloud free trial", "Acme Cloud free trial") == 1.0
    assert title_similarity("Acme Cloud", "Totally different thing") < 0.5


def test_canonical_url():
    assert canonical_url("https://x.dev/a/?utm_source=n&b=2") == "x.dev/a?b=2"


# ------------------------------------------------------------- adapters
class _FakeSource:
    key = "fake"
    name = "Fake"
    publisher = "Fake"
    source_type = "rss"
    adapter = "rss"
    homepage_url = "https://fake.dev"
    feed_url = "https://fake.dev/feed.xml"
    is_active = True
    requires_js = False
    is_paywalled = False
    respect_robots = True
    min_request_interval_seconds = 0
    rate_limit_per_hour = 1000
    max_items = 10
    api_key_env = None
    config: dict = {}


RSS_XML = """<?xml version="1.0"?>
<rss version="2.0"><channel>
  <title>Fake Deals</title>
  <item>
    <title>Acme Cloud: 3 months free trial</title>
    <link>https://acme.dev/free-trial</link>
    <description>Get 3 months free with code SAVE50.</description>
    <pubDate>Mon, 01 Jan 2026 00:00:00 GMT</pubDate>
  </item>
  <item>
    <title>Our company news</title>
    <link>https://acme.dev/blog</link>
    <description>We raised a round of funding.</description>
  </item>
</channel></rss>"""


def test_rss_adapter_parses_only_offer_entries():
    adapter = RSSAdapter()
    ctx = AdapterContext(source=_FakeSource(), config={"max_items": 10})
    ctx.payload = FetchResult(True, 200, "https://fake.dev/feed.xml", RSS_XML)
    outcome = adapter.parse(ctx)
    assert outcome.total_seen == 2
    assert len(outcome.items) == 1
    item = outcome.items[0]
    assert item.title.startswith("Acme Cloud")
    assert item.url == "https://acme.dev/free-trial"


JSON_PAYLOAD = {
    "data": [
        {
            "id": 1,
            "name": "Acme Pro free trial",
            "summary": "30 days free for new accounts",
            "landing_page": "https://acme.dev/trial",
            "type": "trial",
            "pricing": {"original": "20", "promo": "0", "currency": "usd"},
            "terms": {"trial_days": 30, "code": "TRIAL30"},
            "availability": ["US", "GB"],
        },
        {"id": 2, "name": "No link here"},
    ]
}


def test_json_adapter_maps_configured_fields():
    adapter = JsonApiAdapter()
    config = {
        "items_path": "data",
        "fields": {
            "id": "id",
            "title": "name",
            "description": "summary",
            "url": "landing_page",
            "offer_type": "type",
            "original_price": "pricing.original",
            "promo_price": "pricing.promo",
            "currency": "pricing.currency",
            "trial_days": "terms.trial_days",
            "coupon_code": "terms.code",
            "countries": "availability",
        },
    }
    ctx = AdapterContext(source=_FakeSource(), config=config)
    ctx.payload = FetchResult(True, 200, "https://api.fake.dev", __import__("json").dumps(JSON_PAYLOAD))
    outcome = adapter.parse(ctx)
    assert len(outcome.items) == 1
    item = outcome.items[0]
    assert item.trial_days == 30
    assert item.promo_price == 0.0
    assert item.currency == "USD"
    assert item.coupon_code == "TRIAL30"
    assert item.country_codes == ["US", "GB"]


def test_json_adapter_missing_fields_stay_none():
    adapter = JsonApiAdapter()
    ctx = AdapterContext(source=_FakeSource(), config={"items_path": "data", "fields": {"title": "name", "url": "landing_page"}})
    ctx.payload = FetchResult(
        True, 200, "https://api.fake.dev", __import__("json").dumps(JSON_PAYLOAD)
    )
    item = adapter.parse(ctx).items[0]
    assert item.original_price is None
    assert item.expires_at is None
    assert item.currency == "USD"


HTML_PAGE = """
<html><body>
  <article class="offer">
    <h3><a href="/promo/acme">Acme Pro free for 30 days</a></h3>
    <p>Save 40% on your first year with code SAVE40.</p>
  </article>
  <article class="offer">
    <h3><a href="/about">About our company</a></h3>
    <p>We are a software company founded in 2010.</p>
  </article>
  <article class="offer">
    <h3><a href="https://other.example/promo">Off-site promo</a></h3>
    <p>50% off everything, free trial inside.</p>
  </article>
</body></html>
"""


def test_html_adapter_respects_selectors_and_host():
    adapter = HtmlListingAdapter()
    ctx = AdapterContext(
        source=_FakeSource(),
        config={
            "item_selector": "article.offer",
            "title_selector": "h3 a",
            "description_selector": "p",
            "same_host_only": True,
        },
    )
    ctx.payload = FetchResult(True, 200, "https://fake.dev/offers", HTML_PAGE)
    outcome = adapter.parse(ctx)
    assert len(outcome.items) == 1
    assert outcome.items[0].url == "https://fake.dev/promo/acme"


def test_html_adapter_refuses_js_sources():
    class JsSource(_FakeSource):
        requires_js = True

    result = HtmlListingAdapter().fetch(AdapterContext(source=JsSource()))
    assert result.ok is False
    assert result.skipped_reason == "requires_js"


def test_html_adapter_refuses_paywalled_sources():
    class PaywalledSource(_FakeSource):
        is_paywalled = True

    result = HtmlListingAdapter().fetch(AdapterContext(source=PaywalledSource()))
    assert result.ok is False
    assert result.skipped_reason == "paywalled"


def test_block_marker_detection():
    from app.services.verification import classify_body

    blocked, reason = classify_body("<html><body>Please verify you are human</body></html>")
    assert blocked is True
    assert "captcha" in (reason or "") or "human" in (reason or "")

    blocked, _ = classify_body("<html><body>" + "real content " * 50 + "</body></html>")
    assert blocked is False


def test_draft_fingerprint_helper_exists():
    draft = normalise(DiscoveredItem(title="Acme", url="https://acme.dev/a"))
    assert isinstance(draft_fingerprint(draft), str) and len(draft_fingerprint(draft)) == 64