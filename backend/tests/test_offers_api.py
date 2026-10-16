"""Public API surface: directory, filters, detail, collections."""

from __future__ import annotations

from datetime import timedelta

import pytest

from app.db.base import utcnow
from app.models.enums import OfferStatus, OfferType
from tests.factories import (
    make_offer,
    seed_brands,
    seed_countries,
    seed_taxonomy,
)


def _seed(session):
    categories = seed_taxonomy(session)
    brands = seed_brands(session, categories)
    countries = seed_countries(session)
    return categories, brands, countries


def test_health(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_categories_list_includes_empty_ones(client, session):
    _seed(session)
    session.commit()
    response = client.get("/api/v1/categories")
    assert response.status_code == 200
    assert len(response.json()) == 6


def test_offers_directory_pagination(client, session):
    categories, brands, _ = _seed(session)
    for index in range(7):
        make_offer(
            session,
            categories["ai-tools"],
            brand=brands["Replicate"],
            slug=f"offer-{index}",
            title=f"AI offer {index}",
        )
    session.commit()

    response = client.get("/api/v1/offers", params={"page": 1, "page_size": 3})
    body = response.json()
    assert response.status_code == 200
    assert body["total"] == 7
    assert len(body["items"]) == 3
    assert body["pages"] == 3
    assert body["has_next"] is True


def test_offers_filter_by_type_and_category(client, session):
    categories, brands, _ = _seed(session)
    make_offer(session, categories["ai-tools"], brand=brands["Replicate"], slug="a1")
    make_offer(
        session,
        categories["vpn-security-privacy"],
        brand=brands["Proton"],
        slug="v1",
        offer_type=OfferType.DISCOUNT,
    )
    session.commit()

    response = client.get("/api/v1/offers", params={"type": "discount"})
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["slug"] == "v1"

    response = client.get("/api/v1/offers", params={"category": "ai-tools"})
    assert response.json()["total"] == 1


def test_offers_filter_min_trial_days(client, session):
    categories, brands, _ = _seed(session)
    make_offer(session, categories["ai-tools"], brand=brands["Replicate"], slug="t30", trial_days=30)
    make_offer(session, categories["ai-tools"], brand=brands["Replicate"], slug="t7", trial_days=7)
    session.commit()

    response = client.get("/api/v1/offers", params={"min_trial_days": 20})
    slugs = [item["slug"] for item in response.json()["items"]]
    assert "t30" in slugs
    assert "t7" not in slugs


def test_offers_filter_ending_soon(client, session):
    categories, brands, _ = _seed(session)
    make_offer(
        session,
        categories["ai-tools"],
        brand=brands["Replicate"],
        slug="soon",
        expires_in_days=2,
    )
    make_offer(
        session,
        categories["ai-tools"],
        brand=brands["Replicate"],
        slug="later",
        expires_in_days=60,
    )
    session.commit()

    response = client.get("/api/v1/offers", params={"ending_within_days": 7})
    slugs = [item["slug"] for item in response.json()["items"]]
    assert slugs == ["soon"]


def test_offers_filter_no_payment_method(client, session):
    categories, brands, _ = _seed(session)
    make_offer(
        session,
        categories["ai-tools"],
        brand=brands["Replicate"],
        slug="nocard",
        requires_payment_method=False,
    )
    make_offer(
        session,
        categories["ai-tools"],
        brand=brands["Replicate"],
        slug="card",
        requires_payment_method=True,
    )
    session.commit()

    response = client.get("/api/v1/offers", params={"requires_payment_method": False})
    slugs = [item["slug"] for item in response.json()["items"]]
    assert slugs == ["nocard"]


def test_country_filter_and_currency_conversion(client, session):
    categories, brands, countries = _seed(session)
    make_offer(
        session,
        categories["ai-tools"],
        brand=brands["Replicate"],
        slug="india-only",
        is_global=False,
        country_codes=("IN",),
        currency="INR",
        original_price=2000.0,
        promo_price=0.0,
    )
    session.commit()

    response = client.get("/api/v1/offers", params={"country_codes": "IN", "currency": "INR"})
    item = response.json()["items"][0]
    assert item["slug"] == "india-only"
    assert item["currency"] == "INR"
    assert item["is_global"] is False
    assert "IN" in item["country_codes"]

    response = client.get("/api/v1/offers", params={"country_codes": "US"})
    assert response.json()["total"] == 0


def test_price_conversion_to_inr(client, session):
    categories, brands, _ = _seed(session)
    make_offer(
        session,
        categories["ai-tools"],
        brand=brands["Replicate"],
        slug="usd-offer",
        original_price=10.0,
        promo_price=4.0,
        savings_value=6.0,
        savings_percent=60,
    )
    session.commit()

    usd = client.get("/api/v1/offers", params={"currency": "USD"}).json()["items"][0]
    inr = client.get("/api/v1/offers", params={"currency": "INR"}).json()["items"][0]
    assert usd["promo_price"] == 4.0
    assert inr["currency"] == "INR"
    assert inr["promo_price"] == pytest.approx(4 * 83.5, rel=0.02)
    assert inr["original_price"] == pytest.approx(10 * 83.5, rel=0.02)
    assert inr["savings_percent"] == 60


def test_expired_offers_are_hidden_but_listed_separately(client, session):
    categories, brands, _ = _seed(session)
    make_offer(
        session,
        categories["ai-tools"],
        brand=brands["Replicate"],
        slug="dead",
        expires_in_days=-2,
    )
    session.commit()

    assert client.get("/api/v1/offers").json()["total"] == 0
    expired = client.get("/api/v1/expired")
    assert expired.status_code == 200
    assert [item["slug"] for item in expired.json()["items"]] == ["dead"]


def test_offer_detail_and_related(client, session):
    categories, brands, _ = _seed(session)
    main = make_offer(
        session,
        categories["ai-tools"],
        brand=brands["Replicate"],
        slug="main",
        title="Replicate free credits",
    )
    make_offer(
        session,
        categories["ai-tools"],
        brand=brands["Replicate"],
        slug="sibling",
        title="Replicate pay as you go",
    )
    session.commit()

    response = client.get(f"/api/v1/offers/{main.slug}")
    body = response.json()
    assert response.status_code == 200
    assert body["slug"] == "main"
    assert len(body["how_to_redeem"]) == 3
    assert len(body["similar"]) >= 1
    assert body["is_verified"] is True


def test_offer_detail_404(client, session):
    _seed(session)
    assert client.get("/api/v1/offers/does-not-exist").status_code == 404


def test_collections(client, session):
    categories, brands, _ = _seed(session)
    make_offer(
        session,
        categories["ai-tools"],
        brand=brands["Replicate"],
        slug="ending",
        expires_in_days=1,
    )
    make_offer(
        session,
        categories["free-websites-utilities"],
        slug="freebie",
        offer_type=OfferType.FREE,
        is_genuinely_free=True,
        expires_in_days=None,
    )
    session.commit()

    for name in ("trending", "ending-soon", "free", "no-card", "verified"):
        response = client.get(f"/api/v1/collections/{name}")
        assert response.status_code == 200, name
        assert isinstance(response.json(), list)

    assert client.get("/api/v1/collections/nope").status_code == 404


def test_home_bundle(client, session):
    categories, brands, _ = _seed(session)
    make_offer(
        session,
        categories["ai-tools"],
        brand=brands["Replicate"],
        slug="one",
        is_featured=True,
        is_handpicked=True,
    )
    session.commit()

    response = client.get("/api/v1/home", params={"limit": 4})
    body = response.json()
    assert response.status_code == 200
    assert len(body["trending"]) == 1
    assert len(body["featured"]) == 1
    assert body["stats"]["live_offers"] == 1


def test_facets(client, session):
    categories, brands, _ = _seed(session)
    make_offer(session, categories["ai-tools"], brand=brands["Replicate"], slug="f1")
    make_offer(
        session,
        categories["vpn-security-privacy"],
        brand=brands["Proton"],
        slug="f2",
        offer_type=OfferType.DISCOUNT,
    )
    session.commit()

    response = client.get("/api/v1/offers/facets")
    body = response.json()
    assert response.status_code == 200
    assert {bucket["value"] for bucket in body["offer_types"]} >= {"free_trial", "discount"}
    assert body["max_savings"] >= 0


def test_click_tracking_redirects(client, session):
    categories, brands, _ = _seed(session)
    offer = make_offer(
        session,
        categories["ai-tools"],
        brand=brands["Replicate"],
        slug="clickable",
    )
    session.commit()

    response = client.get(f"/api/v1/go/{offer.slug}", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"].startswith("https://")
    assert response.headers["x-zexr-affiliate"] == "0"


def test_availability_endpoint(client, session):
    categories, brands, _ = _seed(session)
    offer = make_offer(
        session,
        categories["ai-tools"],
        brand=brands["Replicate"],
        slug="regional",
        is_global=False,
        country_codes=("IN",),
    )
    session.commit()

    response = client.get("/api/v1/search/availability", params={"slug": offer.slug})
    body = response.json()
    assert body["is_global"] is False
    assert any(entry["code"] == "IN" and entry["available"] for entry in body["countries"])


def test_offer_status_filters_do_not_leak(client, session):
    categories, brands, _ = _seed(session)
    make_offer(
        session,
        categories["ai-tools"],
        brand=brands["Replicate"],
        slug="pending",
        status=OfferStatus.PENDING_REVIEW.value,
    )
    session.commit()

    assert client.get("/api/v1/offers").json()["total"] == 0
    assert client.get(f"/api/v1/offers/pending").status_code == 404


def test_demo_data_is_flagged(client, session):
    categories, brands, _ = _seed(session)
    make_offer(
        session,
        categories["ai-tools"],
        brand=brands["Replicate"],
        slug="demo",
        demo=True,
        verification="unverified",
    )
    session.commit()

    item = client.get("/api/v1/offers").json()["items"][0]
    assert item["is_demo_data"] is True
    assert item["is_verified"] is False


def test_ending_soon_uses_expiry_date_not_published_date(client, session):
    categories, brands, _ = _seed(session)
    offer = make_offer(
        session,
        categories["ai-tools"],
        brand=brands["Replicate"],
        slug="fresh-long",
        expires_in_days=100,
        published_days_ago=0,
    )
    session.commit()
    assert offer.expires_at > utcnow() + timedelta(days=90)
    assert client.get("/api/v1/offers", params={"ending_within_days": 3}).json()["total"] == 0