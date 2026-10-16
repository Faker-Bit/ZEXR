"""Accounts, authorisation boundaries and admin moderation."""

from __future__ import annotations

from app.models.enums import OfferStatus, UserRole
from tests.factories import (
    auth_headers,
    make_offer,
    make_user,
    seed_brands,
    seed_taxonomy,
)


def _world(session):
    categories = seed_taxonomy(session)
    brands = seed_brands(session, categories)
    offer = make_offer(
        session, categories["ai-tools"], brand=brands["Replicate"], slug="ai-one", title="AI offer"
    )
    session.commit()
    return categories, brands, offer


# ------------------------------------------------------------------- auth
def test_register_and_login(client, session):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "new@zexrdealhub.dev",
            "password": "Str0ngPassw0rd",
            "display_name": "New",
            "preferred_currency": "INR",
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["user"]["email"] == "new@zexrdealhub.dev"
    assert body["user"]["preferred_currency"] == "INR"

    response = client.post(
        "/api/v1/auth/login", json={"email": "new@zexrdealhub.dev", "password": "Str0ngPassw0rd"}
    )
    assert response.status_code == 200


def test_register_rejects_duplicate_email(client, session):
    payload = {"email": "dup@zexrdealhub.dev", "password": "Str0ngPassw0rd"}
    assert client.post("/api/v1/auth/register", json=payload).status_code == 201
    assert client.post("/api/v1/auth/register", json=payload).status_code == 409


def test_register_rejects_weak_password(client, session):
    response = client.post(
        "/api/v1/auth/register", json={"email": "weak@zexrdealhub.dev", "password": "password"}
    )
    assert response.status_code == 422


def test_login_wrong_password_is_401(client, session):
    make_user(session, "a@zexrdealhub.dev")
    session.commit()
    response = client.post(
        "/api/v1/auth/login", json={"email": "a@zexrdealhub.dev", "password": "WrongPass1"}
    )
    assert response.status_code == 401


def test_password_hashing_is_salted():
    from app.core.security import hash_password, verify_password

    first = hash_password("Passw0rdTest")
    second = hash_password("Passw0rdTest")
    assert first != second
    assert verify_password("Passw0rdTest", first)
    assert not verify_password("wrong", first)


def test_protected_route_requires_auth(client, session):
    assert client.get("/api/v1/me/bookmarks").status_code == 401


def test_refresh_token_flow(client, session):
    make_user(session, "refresh@zexrdealhub.dev")
    session.commit()
    tokens = client.post(
        "/api/v1/auth/login", json={"email": "refresh@zexrdealhub.dev", "password": "Passw0rdTest"}
    ).json()
    response = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert response.status_code == 200
    assert response.json()["access_token"]


def test_expired_or_bogus_refresh_token(client, session):
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": "nope"}).status_code == 401


# -------------------------------------------------------------- bookmarks
def test_bookmark_lifecycle(client, session):
    _, _, offer = _world(session)
    user = make_user(session, "bm@zexrdealhub.dev")
    session.commit()
    headers = auth_headers(client, session, user)

    assert client.post("/api/v1/me/bookmarks", json={"offer_id": offer.id}, headers=headers).status_code == 201
    listing = client.get("/api/v1/me/bookmarks", headers=headers).json()
    assert len(listing) == 1

    checked = client.get(
        "/api/v1/me/bookmarks/check", params={"offer_ids": offer.id}, headers=headers
    ).json()
    assert offer.id in checked["bookmarked"]

    assert client.delete(f"/api/v1/me/bookmarks/{offer.id}", headers=headers).status_code == 204
    assert client.get("/api/v1/me/bookmarks", headers=headers).json() == []


def test_bookmarked_flag_on_cards(client, session):
    _, _, offer = _world(session)
    user = make_user(session, "bm2@zexrdealhub.dev")
    session.commit()
    headers = auth_headers(client, session, user)
    client.post("/api/v1/me/bookmarks", json={"offer_id": offer.id}, headers=headers)

    items = client.get("/api/v1/offers").json()["items"]
    assert items[0]["bookmarked"] is True


def test_cannot_bookmark_missing_offer(client, session):
    user = make_user(session, "bm3@zexrdealhub.dev")
    session.commit()
    headers = auth_headers(client, session, user)
    response = client.post("/api/v1/me/bookmarks", json={"offer_id": "nope"}, headers=headers)
    assert response.status_code == 404


# ----------------------------------------------------------------- alerts
def test_alert_crud(client, session):
    categories, _, _ = _world(session)
    user = make_user(session, "alert@zexrdealhub.dev")
    session.commit()
    headers = auth_headers(client, session, user)

    created = client.post(
        "/api/v1/me/alerts",
        json={"kind": "category", "category_id": categories["ai-tools"].id},
        headers=headers,
    )
    assert created.status_code == 201
    assert created.json()["match_count"] >= 1

    alerts = client.get("/api/v1/me/alerts", headers=headers).json()
    assert len(alerts) == 1

    patched = client.patch(
        f"/api/v1/me/alerts/{alerts[0]['id']}", json={"is_active": False}, headers=headers
    )
    assert patched.status_code == 200
    assert patched.json()["is_active"] is False

    assert client.delete(f"/api/v1/me/alerts/{alerts[0]['id']}", headers=headers).status_code == 204


# ------------------------------------------------------------------- admin
def test_admin_requires_authentication(client, session):
    assert client.get("/api/v1/admin/stats").status_code == 401


def test_normal_user_cannot_reach_admin(client, session):
    user = make_user(session, "plain@zexrdealhub.dev")
    session.commit()
    headers = auth_headers(client, session, user)
    assert client.get("/api/v1/admin/stats", headers=headers).status_code == 403


def test_admin_can_create_and_publish_offer(client, session):
    categories, _, _ = _world(session)
    admin = make_user(session, "admin@zexrdealhub.dev", role=UserRole.ADMIN.value)
    session.commit()
    headers = auth_headers(client, session, admin)

    payload = {
        "title": "Acme free trial created by the admin API",
        "short_description": "A short summary that comfortably clears validation rules.",
        "description": "A longer description with redemption instructions and eligibility notes.",
        "category_id": categories["ai-tools"].id,
        "offer_type": "free_trial",
        "trial_days": 14,
        "official_url": "https://acme.dev/trial",
        "status": "pending_review",
        "verification_status": "unverified",
    }
    created = client.post("/api/v1/admin/offers", json=payload, headers=headers)
    assert created.status_code == 201, created.text
    slug = created.json()["slug"]

    # Not visible publicly until published.
    assert client.get(f"/api/v1/offers/{slug}").status_code == 404

    published = client.patch(
        f"/api/v1/admin/offers/{created.json()['id']}/status",
        json={"status": "published", "verification_status": "verified"},
        headers=headers,
    )
    assert published.status_code == 200
    assert published.json()["status"] == "published"

    public = client.get(f"/api/v1/offers/{slug}")
    assert public.status_code == 200
    assert public.json()["is_verified"] is True


def test_admin_bulk_action(client, session):
    categories, brands, _ = _world(session)
    second = make_offer(
        session, categories["ai-tools"], brand=brands["Replicate"], slug="ai-two"
    )
    session.commit()
    admin = make_user(session, "bulk@zexrdealhub.dev", role=UserRole.ADMIN.value)
    session.commit()
    headers = auth_headers(client, session, admin)

    response = client.post(
        "/api/v1/admin/offers/bulk",
        json={"offer_ids": [second.id], "action": "feature"},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["affected"] == 1


def test_offer_price_validation_blocks_bad_pairs(client, session):
    categories, _, _ = _world(session)
    admin = make_user(session, "admin2@zexrdealhub.dev", role=UserRole.ADMIN.value)
    session.commit()
    headers = auth_headers(client, session, admin)

    response = client.post(
        "/api/v1/admin/offers",
        json={
            "title": "Impossible discount that should be rejected",
            "short_description": "Promo price is higher than the original price here.",
            "description": "This payload is invalid and must be rejected by the schema.",
            "category_id": categories["ai-tools"].id,
            "original_price": 10,
            "promo_price": 25,
            "official_url": "https://acme.dev/x",
        },
        headers=headers,
    )
    assert response.status_code == 422


def test_admin_cannot_delete_a_category_in_use(client, session):
    categories, _, _ = _world(session)
    admin = make_user(session, "admin3@zexrdealhub.dev", role=UserRole.ADMIN.value)
    session.commit()
    headers = auth_headers(client, session, admin)

    response = client.delete(f"/api/v1/admin/categories/{categories['ai-tools'].id}", headers=headers)
    assert response.status_code == 409


def test_reviewer_can_see_but_not_delete_offers(client, session):
    _, _, offer = _world(session)
    reviewer = make_user(session, "rev@zexrdealhub.dev", role=UserRole.REVIEWER.value)
    session.commit()
    headers = auth_headers(client, session, reviewer)

    assert client.get("/api/v1/admin/offers", headers=headers).status_code == 200
    assert client.delete(f"/api/v1/admin/offers/{offer.id}", headers=headers).status_code == 403


def test_admin_can_manage_categories(client, session):
    _world(session)
    admin = make_user(session, "cat@zexrdealhub.dev", role=UserRole.ADMIN.value)
    session.commit()
    headers = auth_headers(client, session, admin)

    created = client.post(
        "/api/v1/admin/categories",
        json={"slug": "new-bucket", "name": "New Bucket", "icon": "sparkles"},
        headers=headers,
    )
    assert created.status_code == 201

    listed = client.get("/api/v1/categories").json()
    assert any(item["slug"] == "new-bucket" for item in listed)


def test_role_changes_are_blocked_for_self_demotion(client, session):
    _world(session)
    admin = make_user(session, "boss@zexrdealhub.dev", role=UserRole.ADMIN.value)
    session.commit()
    headers = auth_headers(client, session, admin)
    response = client.patch(
        f"/api/v1/admin/users/{admin.id}/role", json={"role": "user"}, headers=headers
    )
    assert response.status_code == 400


def test_source_crud_and_manual_run(client, session):
    from app.models.source import Source

    _world(session)
    source = Source(
        key="rss-test",
        name="Test feed",
        publisher="Test",
        source_type="rss",
        adapter="rss",
        homepage_url="https://test.dev",
        feed_url="https://test.dev/feed.xml",
    )
    session.add(source)
    session.commit()

    admin = make_user(session, "src@zexrdealhub.dev", role=UserRole.ADMIN.value)
    session.commit()
    headers = auth_headers(client, session, admin)

    listing = client.get("/api/v1/admin/sources", headers=headers).json()
    assert any(item["key"] == "rss-test" for item in listing)

    # With discovery disabled the run must be skipped, never executed.
    run = client.post(f"/api/v1/admin/sources/{source.id}/run", headers=headers)
    assert run.status_code == 200


def test_reports_flow(client, session):
    _, _, offer = _world(session)
    user = make_user(session, "rep@zexrdealhub.dev")
    session.commit()
    headers = auth_headers(client, session, user)

    created = client.post(
        "/api/v1/reports",
        json={"offer_id": offer.id, "reason": "wrong_price", "details": "Price looks wrong"},
        headers=headers,
    )
    assert created.status_code == 201

    admin = make_user(session, "repadmin@zexrdealhub.dev", role=UserRole.ADMIN.value)
    session.commit()
    admin_headers = auth_headers(client, session, admin)
    reports = client.get("/api/v1/admin/reports", headers=admin_headers).json()
    assert len(reports) == 1

    resolved = client.patch(
        f"/api/v1/admin/reports/{reports[0]['id']}",
        json={"status": "resolved", "resolution_note": "Price confirmed correct"},
        headers=admin_headers,
    )
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "resolved"


def test_newsletter_subscribe_is_idempotent(client, session):
    first = client.post("/api/v1/newsletter", json={"email": "sub@zexrdealhub.dev"})
    assert first.status_code == 200
    assert first.json()["already_subscribed"] is False

    second = client.post("/api/v1/newsletter", json={"email": "sub@zexrdealhub.dev"})
    assert second.json()["already_subscribed"] is True


def test_events_endpoint_rejects_unknown_types(client, session):
    assert client.post("/api/v1/events?event=teleport").status_code == 400
    assert client.post("/api/v1/events?event=page_view&path=/").status_code == 202