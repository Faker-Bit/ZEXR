"""Search: intent parsing, ranking, facets, autocomplete, typo tolerance."""

from __future__ import annotations

import pytest

from app.models.enums import OfferType
from app.services import search as search_service
from tests.factories import make_offer, seed_brands, seed_countries, seed_taxonomy


@pytest.fixture()
def world(session):
    categories = seed_taxonomy(session)
    brands = seed_brands(session, categories)

    make_offer(
        session,
        categories["vpn-security-privacy"],
        brand=brands["Proton"],
        slug="vpn-30",
        title="Proton VPN 30 days free on the Plus plan",
        keywords="vpn trial",
        offer_type=OfferType.FREE_TRIAL,
        trial_days=30,
    )
    make_offer(
        session,
        categories["vpn-security-privacy"],
        slug="vpn-7",
        title="ShortVPN 7 day trial",
        keywords="vpn",
        offer_type=OfferType.FREE_TRIAL,
        trial_days=7,
    )
    make_offer(
        session,
        categories["ai-tools"],
        brand=brands["Replicate"],
        slug="ai-credits",
        title="Replicate $5 free compute credit",
        keywords="ai credits",
        offer_type=OfferType.FREE_CREDITS,
        trial_days=None,
    )
    make_offer(
        session,
        categories["cloud-hosting"],
        brand=brands["DigitalOcean"],
        slug="cloud-credit",
        title="DigitalOcean $200 cloud credit",
        keywords="hosting credit",
        offer_type=OfferType.FREE_CREDITS,
        trial_days=None,
    )
    make_offer(
        session,
        categories["free-websites-utilities"],
        slug="photopea",
        title="Photopea free browser image editor",
        keywords="free tool",
        offer_type=OfferType.FREE,
        is_genuinely_free=True,
        expires_in_days=None,
        trial_days=None,
    )
    session.commit()
    return categories, brands


# ------------------------------------------------------------ intent parsing
def test_parse_intent_duration_and_category(world):
    _, brands = world
    vocab = search_service.load_vocabulary(
        __import__("app.db.session", fromlist=["SessionLocal"]).SessionLocal()
    )
    intent = search_service.parse_intent("30 days free vpn", vocab)
    assert intent.min_trial_days == 30
    assert "vpn-security-privacy" in intent.category_slugs


def test_parse_intent_no_credit_card(world):
    vocab = search_service.Vocabulary()
    intent = search_service.parse_intent("free premium tools without a credit card", vocab)
    assert intent.requires_payment_method is False


def test_parse_intent_price_threshold():
    intent = search_service.parse_intent("free VPN under $10", search_service.Vocabulary())
    assert intent.max_price == 10.0


def test_parse_intent_price_threshold_rupees():
    intent = search_service.parse_intent("hosting under 500 rupees", search_service.Vocabulary())
    assert intent.max_price == 500.0


def test_parse_intent_coupon_and_cashback():
    vocab = search_service.Vocabulary()
    assert search_service.parse_intent("coupon codes for hosting", vocab).offer_types == [
        OfferType.COUPON
    ]
    assert search_service.parse_intent("cashback on shopping", vocab).offer_types == [
        OfferType.CASHBACK
    ]


def test_parse_intent_bare_free_is_not_a_type_filter():
    """A bare "free" must not exclude trials and credits."""
    intent = search_service.parse_intent("free cloud hosting", search_service.Vocabulary())
    assert intent.offer_types == []


def test_parse_intent_strong_free_is_a_type_filter():
    intent = search_service.parse_intent("free tools that are free forever", search_service.Vocabulary())
    assert OfferType.FREE in intent.offer_types


def test_parse_intent_brand_preferred_over_alias_confusion(world):
    from app.db.session import SessionLocal

    session = SessionLocal()
    vocab = search_service.load_vocabulary(session)
    # "proton vpn" is a multi-word brand alias; the bare word "vpn" must still
    # resolve to the category, not to the Proton brand.
    assert vocab.brand_aliases.get("vpn") is None
    kind, slug = vocab.lookup("vpn")
    assert kind == "category"
    intent = search_service.parse_intent("best vpn deals", vocab)
    assert "vpn-security-privacy" in intent.category_slugs
    assert intent.brand_slugs == []
    session.close()


# ------------------------------------------------------------------ ranking
def test_search_returns_relevant_offers(client, world):
    response = client.get("/api/v1/search", params={"q": "30 days free vpn"})
    body = response.json()
    assert response.status_code == 200
    assert body["total"] >= 1
    assert body["results"][0]["slug"] in ("vpn-30", "vpn-7")


def test_search_respects_min_trial_days(client, world):
    body = client.get("/api/v1/search", params={"q": "30 days free vpn"}).json()
    slugs = [item["slug"] for item in body["results"]]
    assert "vpn-30" in slugs
    assert "vpn-7" not in slugs


def test_search_credits_query(client, world):
    body = client.get("/api/v1/search", params={"q": "ai tools with free credits"}).json()
    assert body["intent"]["offer_types"] == ["free_credits"]
    assert "ai-credits" in [item["slug"] for item in body["results"]]


def test_search_hosting(client, world):
    body = client.get("/api/v1/search", params={"q": "free cloud hosting"}).json()
    slugs = [item["slug"] for item in body["results"]]
    assert "cloud-credit" in slugs


def test_search_typo_is_corrected_and_reported(client, world):
    # "hostng" matches nothing, so the corrected spelling is used instead.
    response = client.get("/api/v1/search", params={"q": "hostng"})
    body = response.json()
    assert body["total"] >= 1
    assert body["did_you_mean"] == "hosting"
    assert body["query"] == "hosting"


def test_search_no_results_returns_empty_not_error(client, world):
    body = client.get("/api/v1/search", params={"q": "zzzzqqqxxxx nonsense"}).json()
    assert body["total"] == 0
    assert body["results"] == []


def test_search_facets_present(client, world):
    body = client.get("/api/v1/search", params={"q": "vpn"}).json()
    assert "categories" in body["facets"]
    assert body["facets"]["categories"].get("vpn-security-privacy", 0) >= 1


def test_autocomplete_returns_brands_and_offers(client, world):
    response = client.get("/api/v1/search/suggest", params={"q": "proto"})
    body = response.json()
    assert response.status_code == 200
    assert any(item["type"] == "brand" for item in body)


def test_autocomplete_empty_query(client, world):
    assert client.get("/api/v1/search/suggest", params={"q": ""}).json() == []


def test_parse_endpoint_exposes_intent(client, world):
    response = client.get("/api/v1/search/parse", params={"q": "30 days free vpn"})
    body = response.json()
    assert body["min_trial_days"] == 30
    assert body["intent"] in {"mixed", "duration", "offer_type"}


def test_search_combines_explicit_filters(client, world):
    body = client.get(
        "/api/v1/search", params={"q": "free vpn", "type": "discount"}
    ).json()
    assert body["total"] == 0  # no VPN discount in the fixture


def test_canonical_url_strips_tracking():
    from app.discovery.dedupe import canonical_url

    assert canonical_url("https://Example.com/offers/?utm_source=x&id=3") == "example.com/offers?id=3"