"""Stateless OAuth state and PKCE.

The `state` parameter is the CSRF defence for the authorization-code flow: it
ties the callback back to the request that started it.  It has to survive a
round-trip to the provider and back, which rules out an in-memory store unless
we accept losing logins on restart.

So `state` is a **signed, expiring token** carrying the PKCE verifier.  It is
verified with an HMAC keyed by ``SECRET_KEY``, so it cannot be forged or edited,
and it expires on its own.  No server-side session is needed.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass
from typing import Any

from app.core.config import settings

STATE_TTL_SECONDS = 600


class StateError(ValueError):
    """Raised when a `state` token is missing, forged, or expired."""


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _unb64(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _sign(payload: bytes) -> str:
    return _b64(hmac.new(settings.secret_key.encode(), payload, hashlib.sha256).digest())


@dataclass(frozen=True)
class OAuthState:
    provider: str
    verifier: str
    redirect_uri: str
    created_at: int

    @property
    def pkce_challenge(self) -> str:
        digest = hashlib.sha256(self.verifier.encode()).digest()
        return _b64(digest)


def pkce_pair() -> tuple[str, str]:
    """Return `(verifier, challenge)` for S256."""
    verifier = _b64(secrets.token_bytes(64))
    challenge = _b64(hashlib.sha256(verifier.encode()).digest())
    return verifier, challenge


def issue_state(provider: str, redirect_uri: str) -> OAuthState:
    verifier, _ = pkce_pair()
    state = OAuthState(
        provider=provider,
        verifier=verifier,
        redirect_uri=redirect_uri,
        created_at=int(time.time()),
    )
    return state


def encode_state(state: OAuthState) -> str:
    body = {
        "p": state.provider,
        "v": state.verifier,
        "r": state.redirect_uri,
        "t": state.created_at,
    }
    payload = json.dumps(body, separators=(",", ":")).encode()
    return f"{_b64(payload)}.{_sign(payload)}"


def decode_state(token: str, *, expected_provider: str | None = None) -> OAuthState:
    if not token or "." not in token:
        raise StateError("Missing or malformed OAuth state")

    encoded, _, signature = token.partition(".")
    try:
        payload = _unb64(encoded)
    except (ValueError, base64.binascii.Error) as exc:  # type: ignore[attr-defined]
        raise StateError("OAuth state is not valid base64") from exc

    if not hmac.compare_digest(signature, _sign(payload)):
        raise StateError("OAuth state signature does not match")

    try:
        body: dict[str, Any] = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise StateError("OAuth state is not valid JSON") from exc

    created = int(body.get("t") or 0)
    if not created or time.time() - created > STATE_TTL_SECONDS:
        raise StateError("OAuth state has expired — restart the sign-in")

    provider = str(body.get("p") or "")
    if expected_provider and provider != expected_provider:
        raise StateError("OAuth state was issued for a different provider")

    return OAuthState(
        provider=provider,
        verifier=str(body.get("v") or ""),
        redirect_uri=str(body.get("r") or ""),
        created_at=created,
    )


__all__ = [
    "OAuthState",
    "STATE_TTL_SECONDS",
    "StateError",
    "decode_state",
    "encode_state",
    "issue_state",
    "pkce_pair",
]