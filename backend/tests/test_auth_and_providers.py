"""OAuth state signing and the curated AI provider catalogue."""

from __future__ import annotations

import pytest

from app.core.oauth_state import (
    STATE_TTL_SECONDS,
    StateError,
    decode_state,
    encode_state,
    issue_state,
    pkce_pair,
)


# ------------------------------------------------------------------ oauth
def test_pkce_verifier_and_challenge_differ():
    verifier, challenge = pkce_pair()
    assert verifier and challenge
    assert verifier != challenge


def test_state_round_trip_preserves_fields():
    state = issue_state("google", "http://localhost:3000/auth/callback")
    restored = decode_state(encode_state(state), expected_provider="google")
    assert restored.provider == "google"
    assert restored.redirect_uri == "http://localhost:3000/auth/callback"
    assert restored.verifier == state.verifier


def test_state_rejects_tampering():
    """A forged `state` must not be accepted — this is the CSRF defence."""
    state = issue_state("google", "http://localhost:3000")
    token = encode_state(state)

    # Flip a character in the signature.
    forged = token[:-1] + ("a" if token[-1] != "a" else "b")
    with pytest.raises(StateError):
        decode_state(forged)

    # Rewrite the payload but keep the old signature.
    with pytest.raises(StateError):
        decode_state("eyJwIjoiZ2l0aHViIn0.deadbeef")


def test_state_rejects_garbage():
    for token in ("", "nodot", "a.b.c", "..."):
        with pytest.raises(StateError):
            decode_state(token)


def test_state_rejects_provider_confusion():
    """A `state` issued for Google must not be replayed against GitHub."""
    state = issue_state("google", "http://localhost:3000")
    with pytest.raises(StateError):
        decode_state(encode_state(state), expected_provider="github")


def test_state_expires(monkeypatch):
    import app.core.oauth_state as module

    state = issue_state("google", "http://localhost:3000")
    token = encode_state(state)

    real = module.time.time
    monkeypatch.setattr(
        module.time, "time", lambda: real() + STATE_TTL_SECONDS + 60
    )
    with pytest.raises(StateError):
        decode_state(token)


# --------------------------------------------------------------- catalogue
def test_catalogue_entries_are_well_formed():
    from app.db.provider_catalog import CATALOGUE

    assert len(CATALOGUE) > 40
    seen = set()
    for entry in CATALOGUE:
        assert entry.name and entry.url.startswith("https://")
        assert entry.access in {"FREE", "CREDITS", "CHECK", "PAID"}
        assert entry.label in {"GATEWAY", "HOST", "SELF-HOST"}
        assert entry.note
        seen.add(entry.name)
    # A couple of names legitimately share a URL (Ollama local vs cloud).
    assert len(seen) >= len(CATALOGUE) - 1


def test_catalogue_import_is_idempotent_and_never_verified(session):
    from app.db.provider_catalog import import_catalogue
    from app.models.enums import VerificationStatus
    from app.models.offer import Offer
    from app.models.source import Source
    from app.db.provider_catalog import SOURCE_KEY

    first = import_catalogue(session)
    session.commit()
    assert first["created"] > 0

    before = session.query(Offer).count()
    second = import_catalogue(session)
    session.commit()
    assert second["created"] == 0, "re-running must not create duplicates"
    assert session.query(Offer).count() == before

    # The whole point: claims compiled from vendor docs are never "verified".
    source = (
        session.query(Source).filter(Source.key == SOURCE_KEY).one()
    )
    rows = session.query(Offer).filter(Offer.source_id == source.id).all()
    assert rows
    assert all(
        row.verification_status != VerificationStatus.VERIFIED.value for row in rows
    )
    assert all(row.is_demo_data is False for row in rows)
    assert all(row.official_url for row in rows)


def test_check_label_is_not_stated_as_a_confirmed_free_tier():
    """The weakest label must read as unverified, not as a promise."""
    from app.db.provider_catalog import ACCESS_COPY, OFFER_TYPE_BY_ACCESS

    assert "unconfirmed" in ACCESS_COPY["CHECK"].lower()
    assert "verify" in ACCESS_COPY["CHECK"].lower()
    for label in ("FREE", "CREDITS", "CHECK", "PAID"):
        assert label in OFFER_TYPE_BY_ACCESS


# --------------------------------------------------------------------- api
def test_oauth_start_reports_unconfigured_provider(client):
    """A dead button is worse than a clear message."""
    for provider in ("google", "github"):
        response = client.get(f"/api/v1/auth/oauth/{provider}/start")
        assert response.status_code == 501
        assert "not configured" in response.json()["detail"].lower()


def test_oauth_callback_redirects_to_frontend_on_error(client):
    response = client.get(
        "/api/v1/auth/oauth/google/callback?code=abc",
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert "/login?oauth_error=" in response.headers["location"]

    tampered = client.get(
        "/api/v1/auth/oauth/google/callback?code=abc&state=forged",
        follow_redirects=False,
    )
    assert tampered.status_code == 302
    assert "invalid_state" in tampered.headers["location"]


def test_oauth_callback_honours_provider_error(client):
    denied = client.get(
        "/api/v1/auth/oauth/github/callback?error=access_denied",
        follow_redirects=False,
    )
    assert denied.status_code == 302
    assert "access_denied" in denied.headers["location"]


def test_providers_endpoint_gates_on_credentials(client):
    body = client.get("/api/v1/auth/providers").json()
    by_id = {p["id"]: p for p in body["providers"]}
    assert by_id["email"]["enabled"] is True
    # No keys in the test environment, so the OAuth buttons must be off.
    assert by_id["google"]["enabled"] is False
    assert by_id["github"]["enabled"] is False


def test_email_register_and_login(client):
    register = client.post(
        "/api/v1/auth/register",
        json={
            "email": "signup-test@zexrdealhub.dev",
            "password": "Str0ngPassw0rd!",
            "display_name": "Signup Test",
        },
    )
    assert register.status_code == 201
    assert register.json()["access_token"]

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "signup-test@zexrdealhub.dev", "password": "Str0ngPassw0rd!"},
    )
    assert login.status_code == 200
    assert login.json()["user"]["email"] == "signup-test@zexrdealhub.dev"


def test_login_rejects_bad_password(client):
    client.post(
        "/api/v1/auth/register",
        json={"email": "wrongpass@zexrdealhub.dev", "password": "Str0ngPassw0rd!"},
    )
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "wrongpass@zexrdealhub.dev", "password": "not-the-password"},
    )
    assert response.status_code in (400, 401)


def test_duplicate_email_is_rejected(client):
    payload = {"email": "dupe@zexrdealhub.dev", "password": "Str0ngPassw0rd!"}
    assert client.post("/api/v1/auth/register", json=payload).status_code == 201
    second = client.post("/api/v1/auth/register", json=payload)
    assert second.status_code in (400, 409)