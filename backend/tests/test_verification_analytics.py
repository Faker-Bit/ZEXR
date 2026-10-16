"""Verification, expiry, analytics and notifications."""

from __future__ import annotations

from datetime import timedelta

import httpx
import pytest

from app.db.base import utcnow
from app.models.enums import OfferStatus, SourceType, VerificationStatus
from app.models.offer import OfferVerification
from app.models.source import Source
from tests.factories import make_offer, make_user, seed_brands, seed_taxonomy


@pytest.fixture()
def world(session):
    categories = seed_taxonomy(session)
    brands = seed_brands(session, categories)
    offer = make_offer(
        session, categories["ai-tools"], brand=brands["Replicate"], slug="verify-me"
    )
    session.commit()
    return categories, brands, offer


def _transport(html: str, status_code: int = 200) -> httpx.MockTransport:
    return httpx.MockTransport(lambda request: httpx.Response(status_code, text=html))


def test_extract_prices_from_html():
    from app.services.verification import extract_prices

    html = "<div>Pricing: <b>$20</b> list price, now <b>$10</b> per month</div>"
    prices = extract_prices(html)
    assert prices["promo_price"] == 10.0


def test_verify_marks_offer_verified(session, world):
    from app.services.verification import verify_offer

    _, _, offer = world
    html = (
        "<html><body><h1>Replicate free compute credit</h1>"
        "<p>Sign up for a free credit of $5. This page mentions replicate "
        "and free compute credit in detail, which is plenty of content to be "
        "considered a real page.</p></body></html>"
    )
    with httpx.Client(transport=_transport(html)) as client:
        result = verify_offer(session, offer, client=client)
    session.commit()

    assert result.value in ("ok", "redirected")
    assert offer.verification_status == VerificationStatus.VERIFIED.value
    assert offer.last_checked_at is not None
    assert offer.verifications  # history recorded


def test_verify_404_expires_after_threshold(session, world):
    from app.core.config import settings
    from app.services.verification import verify_offer

    _, _, offer = world
    with httpx.Client(transport=_transport("gone", 404)) as client:
        for _ in range(settings.verify_broken_link_threshold):
            verify_offer(session, offer, client=client)
    session.commit()

    assert offer.status == OfferStatus.EXPIRED.value
    assert offer.verification_status == VerificationStatus.NEEDS_MANUAL.value


def test_verify_price_change_flags_dispute(session, world):
    from app.services.verification import verify_offer

    _, _, offer = world
    html = (
        "<html><body><h1>Replicate free compute credit</h1>"
        "<p>Now only $999 per month for replicate compute credit users. "
        "This is an enormous change compared with the price this offer "
        "advertised when we first indexed the page, and it applies to every "
        "existing account from the moment the change takes effect.</p>"
        "</body></html>"
    )
    with httpx.Client(transport=_transport(html)) as client:
        result = verify_offer(session, offer, client=client)
    session.commit()

    assert result.value == "price_changed"
    assert offer.status == OfferStatus.DISPUTED.value


def test_verify_content_change_flags_manual_review(session, world):
    from app.services.verification import verify_offer

    _, _, offer = world
    html = "<html><body>" + ("completely unrelated content about gardening. " * 20) + "</body></html>"
    with httpx.Client(transport=_transport(html)) as client:
        result = verify_offer(session, offer, client=client)
    session.commit()
    assert result.value == "content_changed"
    assert offer.verification_status == VerificationStatus.NEEDS_MANUAL.value


def test_verify_detects_antibot_block(session, world):
    from app.services.verification import verify_offer

    _, _, offer = world
    html = "<html><body>Please verify you are human to continue replicate access.</body></html>"
    with httpx.Client(transport=_transport(html)) as client:
        result = verify_offer(session, offer, client=client)
    session.commit()
    assert result.value == "blocked"


def test_js_only_sources_are_skipped_not_guessed(session, world):
    from app.services.verification import verify_offer

    _, _, offer = world
    offer.source_id = None
    source = Source(
        key="js-source",
        name="JS only",
        publisher="JS",
        source_type=SourceType.HTML_LISTING.value,
        adapter="html_listing",
        homepage_url="https://js.dev",
        requires_js=True,
    )
    session.add(source)
    session.flush()
    offer.source_id = source.id
    session.commit()

    result = verify_offer(session, offer)
    session.commit()
    assert result.value == "skipped"
    assert offer.verification_status == VerificationStatus.NEEDS_MANUAL.value


def test_verification_sweep_reports_counts(session, world):
    from app.services.verification import run_verification_sweep

    _, _, offer = world
    make_offer(session, offer.category, slug="verify-two")

    html = "<html><body><h1>Replicate</h1><p>" + ("free compute credit details. " * 20) + "</p></body></html>"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=html)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        from app.services import verification

        monkeypatched = verification.verify_offer
        try:
            verification.verify_offer = lambda s, o, client=None: monkeypatched(s, o, client=client)
            result = verification.run_verification_sweep(session, offer_ids=[offer.id], only_stale=False)
        finally:
            verification.verify_offer = monkeypatched
    session.commit()
    assert result.checked == 1


def test_expiry_moves_past_offers(session, world):
    from app.services.verification import expire_finished_offers

    _, _, offer = world
    offer.expires_at = utcnow() - timedelta(hours=1)
    session.commit()

    count = expire_finished_offers(session)
    session.commit()
    assert count == 1
    assert offer.status == OfferStatus.EXPIRED.value


def test_expired_offers_disappear_from_listings(client, session, world):
    _, _, offer = world
    offer.expires_at = utcnow() - timedelta(days=1)
    session.commit()
    assert client.get("/api/v1/offers").json()["total"] == 0
    assert client.get("/api/v1/expired").json()["total"] == 1


# ------------------------------------------------------------- analytics
def test_clicks_and_views_are_recorded(client, session, world):
    _, _, offer = world
    client.get(f"/api/v1/offers/{offer.slug}")
    client.get(f"/api/v1/offers/{offer.slug}")
    client.get(f"/api/v1/go/{offer.slug}", follow_redirects=False)

    from app.models.analytics import Event
    from app.models.offer import Offer as OfferModel
    from sqlalchemy import select

    events = session.execute(select(Event.event_type)).all()
    kinds = {row[0] for row in events}
    assert "offer_view" in kinds
    assert "offer_click" in kinds

    session.expire_all()
    refreshed = session.get(OfferModel, offer.id)
    assert refreshed.click_count >= 1
    assert refreshed.view_count >= 2


def test_dashboard_stats_and_analytics(client, session, world):
    make_user(session, "stats@zexrdealhub.dev")
    session.commit()
    admin = make_user(session, "statsadmin@zexrdealhub.dev", role="admin")
    session.commit()
    headers = {"Authorization": f"Bearer {client.post('/api/v1/auth/login', json={'email': admin.email, 'password': 'Passw0rdTest'}).json()['access_token']}"}

    stats = client.get("/api/v1/admin/stats", headers=headers).json()
    assert stats["total_offers"] >= 1
    assert stats["total_users"] >= 1

    analytics = client.get("/api/v1/admin/analytics?days=7", headers=headers).json()
    assert analytics["range_days"] == 7
    assert len(analytics["clicks"]) == 7


def test_quality_score_penalises_demo_data(session, world):
    from app.services.analytics import recompute_quality

    _, _, offer = world
    recompute_quality(session, offer)
    clean = offer.quality_score
    offer.is_demo_data = True
    recompute_quality(session, offer)
    assert offer.quality_score < clean


def test_quality_score_flags_scam_copy(session, world):
    from app.services.analytics import recompute_quality, re_scammy

    _, _, offer = world
    recompute_quality(session, offer)
    clean = offer.quality_score
    offer.description = "Guaranteed profit, double your money, act now or lose it all."
    recompute_quality(session, offer)
    assert re_scammy(offer.description) is True
    assert offer.quality_score < clean


def test_trending_ranks_are_recomputed(session, world):
    from app.services.analytics import bump_trending

    _, _, offer = world
    bump_trending(session)
    session.commit()
    assert offer.trending_rank in (1, None)


# ---------------------------------------------------------- notifications
def test_expiry_alerts_are_queued(session, world):
    from app.models.user import Bookmark
    from app.services.notifications import notify_expiring_bookmarks

    _, _, offer = world
    offer.expires_at = utcnow() + timedelta(days=2)
    user = make_user(session, "notify@zexrdealhub.dev", email_notifications=True)
    session.add(Bookmark(user_id=user.id, offer_id=offer.id, notify_on_expiry=True))
    session.commit()

    sent = notify_expiring_bookmarks(session)
    session.commit()
    assert sent == 1

    from app.models.user import EmailDelivery

    delivery = session.query(EmailDelivery).first()
    assert delivery is not None
    assert delivery.template == "expiry_alert"
    assert delivery.status == "sent"


def test_weekly_digest_lists_recent_offers(session, world):
    from app.services.notifications import send_weekly_digest

    _, _, offer = world
    from app.models.user import NewsletterSubscriber

    session.add(
        NewsletterSubscriber(
            email="digest@zexrdealhub.dev",
            frequency="weekly",
            is_active=True,
            token="test-token-digest",
        )
    )
    session.commit()

    assert send_weekly_digest(session) == 1
    session.commit()

    from app.models.user import EmailDelivery

    payload = session.query(EmailDelivery).first().payload
    assert payload["count"] >= 1
    assert payload["offers"][0]["slug"] == offer.slug


def test_alerts_dispatch_only_for_new_matches(session, world):
    from app.models.enums import AlertKind
    from app.models.user import Alert
    from app.services.notifications import dispatch_alerts

    _, _, offer = world
    user = make_user(session, "alertsend@zexrdealhub.dev")
    session.add(
        Alert(
            user_id=user.id,
            kind=AlertKind.CATEGORY.value,
            label="AI alerts",
            category_id=offer.category_id,
            is_active=True,
        )
    )
    session.commit()

    result = dispatch_alerts(session)
    session.commit()
    assert result["notifications"] >= 1