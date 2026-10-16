"""Password hashing and JWT helpers.

We talk to `bcrypt` directly instead of passlib: passlib is unmaintained and its
bcrypt backend breaks on bcrypt >= 4.1.  The wrapper below keeps a PBKDF2
fallback so the app still boots in an environment where bcrypt cannot load.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings

TokenType = Literal["access", "refresh"]

try:  # pragma: no cover - depends on wheel availability
    bcrypt.hashpw(b"x", bcrypt.gensalt(rounds=4))
    _BCRYPT_AVAILABLE = True
except Exception:  # pragma: no cover
    _BCRYPT_AVAILABLE = False

_PBKDF2_ROUNDS = 390_000


# --------------------------------------------------------------------- hashes
def hash_password(password: str) -> str:
    if _BCRYPT_AVAILABLE:
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ROUNDS)
    return "pbkdf2$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(digest).decode()


def verify_password(password: str, password_hash: str) -> bool:
    if not password_hash:
        return False
    if password_hash.startswith("pbkdf2$"):
        try:
            _, salt_b64, digest_b64 = password_hash.split("$", 2)
            expected = base64.b64decode(digest_b64)
            actual = hashlib.pbkdf2_hmac(
                "sha256", password.encode("utf-8"), base64.b64decode(salt_b64), _PBKDF2_ROUNDS
            )
            return hmac.compare_digest(expected, actual)
        except Exception:
            return False
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# ----------------------------------------------------------------------- jwt
def _create_token(subject: str, token_type: TokenType, expires_delta: timedelta, **claims: Any) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "typ": token_type,
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
        "jti": secrets.token_urlsafe(12),
    }
    payload.update(claims)
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(subject: str | int, **claims: Any) -> str:
    return _create_token(
        str(subject), "access", timedelta(minutes=settings.access_token_ttl_minutes), **claims
    )


def create_refresh_token(subject: str | int, **claims: Any) -> str:
    return _create_token(
        str(subject), "refresh", timedelta(days=settings.refresh_token_ttl_days), **claims
    )


def decode_token(token: str, expected_type: TokenType | None = None) -> dict[str, Any] | None:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None
    if expected_type and payload.get("typ") != expected_type:
        return None
    return payload


# -------------------------------------------------------------------- misc
def random_token(length: int = 32) -> str:
    return secrets.token_urlsafe(length)


def constant_time_equals(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


def slugify(value: str, max_length: int = 80) -> str:
    value = value.strip().lower()
    out: list[str] = []
    prev_dash = False
    for ch in value:
        if ch.isalnum():
            out.append(ch)
            prev_dash = False
        elif not prev_dash:
            out.append("-")
            prev_dash = True
    slug = "".join(out).strip("-")[:max_length].strip("-")
    return slug or "offer"


def favicon_seed(host: str) -> str:
    """Deterministic colour seed so brand avatars stay stable without assets."""
    return hashlib.sha1(host.encode("utf-8")).hexdigest()[:8]


def new_salt() -> str:
    return os.urandom(16).hex()