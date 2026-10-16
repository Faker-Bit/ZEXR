"""Authentication: email/password plus pluggable OAuth."""

from __future__ import annotations

from typing import Annotated, Any

import httpx
from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select

from app.api.deps import RequireUser, SessionDep
from app.core.config import settings
from app.core.logging import get_logger
from app.core.oauth_state import (OAuthState, StateError, decode_state, encode_state, pkce_pair,)
from app.core.ratelimit import limit
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    random_token,
    verify_password,
)
from app.db.base import utcnow
from app.models.enums import AuthProvider, UserRole
from app.models.taxonomy import Country
from app.models.user import OAuthAccount, User
from app.schemas.auth import (
    LoginRequest,
    OAuthCallbackRequest,
    OAuthStartRequest,
    RefreshRequest,
    RegisterRequest,
    TokenPair,
    UserOut,
)
from app.services import analytics

log = get_logger("auth")
router = APIRouter(prefix="/auth", tags=["auth"])

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"
GITHUB_EMAILS_URL = "https://api.github.com/user/emails"


def _issue_tokens(response: Response, user: User) -> TokenPair:
    access = create_access_token(user.id, role=user.role, email=user.email)
    refresh = create_refresh_token(user.id)
    response.set_cookie(
        settings.cookie_name,
        access,
        max_age=settings.access_token_ttl_minutes * 60,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )
    user.last_login_at = utcnow()
    return TokenPair(
        access_token=access,
        refresh_token=refresh,
        expires_in=settings.access_token_ttl_minutes * 60,
        user=_user_out(user),
    )


def _user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
        role=UserRole(user.role),
        country_code=user.country_code,
        preferred_currency=user.preferred_currency,
        locale=user.locale,
        interests=list(user.interests or []),
        email_notifications=user.email_notifications,
        newsletter_subscribed=user.newsletter_subscribed,
        is_active=user.is_active,
        created_at=user.created_at,
        bookmark_count=0,
        alert_count=0,
    )


@router.post("/register", response_model=TokenPair, status_code=status.HTTP_201_CREATED)
@limit("10/minute")
def register(
    request: Request,
    payload: RegisterRequest,
    response: Response,
    session: SessionDep,
) -> TokenPair:
    email = payload.email.lower().strip()
    existing = session.execute(select(User).where(User.email == email)).scalars().first()
    if existing is not None:
        raise HTTPException(status_code=409, detail="An account with this email already exists")

    if payload.country_code:
        known = session.execute(
            select(Country.id).where(Country.code == payload.country_code)
        ).first()
        if not known:
            raise HTTPException(status_code=400, detail="Unsupported country code")

    user = User(
        email=email,
        hashed_password=hash_password(payload.password),
        display_name=payload.display_name or email.split("@")[0],
        country_code=payload.country_code,
        preferred_currency=payload.preferred_currency,
        interests=payload.interests,
        newsletter_subscribed=payload.newsletter_opt_in,
        marketing_opt_in=payload.newsletter_opt_in,
        role=UserRole.USER.value,
    )
    session.add(user)
    session.flush()

    if payload.newsletter_opt_in:
        _subscribe_newsletter(session, email, payload.country_code, payload.interests)

    analytics.record_event(session, "signup", entity_type="user", entity_id=user.id)
    session.commit()
    return _issue_tokens(response, user)


@router.post("/login", response_model=TokenPair)
@limit("20/minute")
def login(
    request: Request,
    payload: LoginRequest,
    response: Response,
    session: SessionDep,
) -> TokenPair:
    email = payload.email.lower().strip()
    user = session.execute(select(User).where(User.email == email)).scalars().first()
    password_ok = verify_password(
        payload.password,
        user.hashed_password if user and user.hashed_password else hash_password("decoy-password"),
    )
    if user is None or not password_ok:
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    if user.is_banned:
        raise HTTPException(status_code=403, detail="This account has been suspended")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="This account is not active")
    session.commit()
    return _issue_tokens(response, user)


@router.post("/refresh", response_model=TokenPair)
def refresh(payload: RefreshRequest, response: Response, session: SessionDep) -> TokenPair:
    claims = decode_token(payload.refresh_token, "refresh")
    if not claims:
        raise HTTPException(status_code=401, detail="Refresh token is invalid or expired")
    user = session.get(User, claims.get("sub"))
    if user is None or not user.is_active or user.is_banned:
        raise HTTPException(status_code=401, detail="Account is no longer available")
    return _issue_tokens(response, user)


@router.post("/logout")
def logout(response: Response) -> dict:
    response.delete_cookie(settings.cookie_name, path="/")
    return {"ok": True}


@router.get("/me", response_model=UserOut, summary="Current profile")
def me(user: RequireUser, session: SessionDep) -> UserOut:
    from sqlalchemy import func

    from app.models.user import Alert, Bookmark

    bookmarks = int(
        session.execute(
            select(func.count(Bookmark.id)).where(Bookmark.user_id == user.id)
        ).scalar()
        or 0
    )
    alerts = int(
        session.execute(select(func.count(Alert.id)).where(Alert.user_id == user.id)).scalar() or 0
    )
    out = _user_out(user)
    out.bookmark_count = bookmarks
    out.alert_count = alerts
    return out


@router.get("/providers", summary="Supported sign-in methods")
def providers() -> dict:
    return {
        "providers": [
            {"id": AuthProvider.EMAIL.value, "label": "Email", "enabled": True},
            {
                "id": AuthProvider.GOOGLE.value,
                "label": "Google",
                "enabled": _oauth_provider_ready(AuthProvider.GOOGLE),
            },
            {
                "id": AuthProvider.GITHUB.value,
                "label": "GitHub",
                "enabled": _oauth_provider_ready(AuthProvider.GITHUB),
            },
        ]
    }


# --------------------------------------------------------------------- OAuth
#
# The provider redirects the *browser* back to us, so both endpoints are GET and
# the callback ends in a redirect back to the frontend. No frontend route is
# needed: the API owns the whole handshake and hands the browser back to the web
# app already holding its session cookie.
#
# `state` is a signed, expiring token carrying the PKCE verifier (see
# `app.core.oauth_state`), which is what makes the flow CSRF-safe.


def _oauth_provider_ready(provider: AuthProvider) -> bool:
    if provider is AuthProvider.GOOGLE:
        return bool(settings.google_client_id and settings.google_client_secret)
    if provider is AuthProvider.GITHUB:
        return bool(settings.github_client_id and settings.github_client_secret)
    return False


@router.get("/oauth/{provider}/start", summary="Begin an OAuth flow")
def oauth_start(
    provider: AuthProvider,
    redirect_uri: str | None = None,
) -> dict[str, Any]:
    """Return the provider URL the browser should be sent to.

    Kept as JSON rather than a 307 so the frontend can show a clear message when
    a provider is not configured, instead of a dead redirect.
    """
    if not _oauth_provider_ready(provider):
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=(
                f"{provider.value.title()} sign-in is not configured. Set "
                f"{provider.value.upper()}_CLIENT_ID and {provider.value.upper()}_CLIENT_SECRET "
                "in backend/.env, then register the redirect URI."
            ),
        )

    from urllib.parse import urlencode

    redirect = redirect_uri or settings.oauth_redirect_uri
    verifier, challenge = pkce_pair()
    token = encode_state(
        OAuthState(
            provider=provider.value,
            verifier=verifier,
            redirect_uri=redirect,
            created_at=int(time.time()),
        )
    )

    if provider is AuthProvider.GOOGLE:
        params = {
            "client_id": settings.google_client_id,
            "redirect_uri": redirect,
            "response_type": "code",
            "scope": "openid email profile",
            "state": token,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "prompt": "select_account",
        }
        authorize_url = f"{GOOGLE_AUTH_URL}?{urlencode(params)}"
    else:
        params = {
            "client_id": settings.github_client_id,
            "redirect_uri": redirect,
            "scope": "read:user user:email",
            "state": token,
        }
        authorize_url = f"{GITHUB_AUTHORIZE_URL}?{urlencode(params)}"

    return {
        "provider": provider.value,
        "authorize_url": authorize_url,
        "redirect_uri": redirect,
    }


@router.get("/oauth/{provider}/callback", summary="Complete an OAuth flow")
def oauth_callback(
    provider: AuthProvider,
    response: Response,
    session: SessionDep,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    """Exchange the code, sign the user in, and bounce back to the web app."""
    site = settings.site_url.rstrip("/")

    if error:
        return RedirectResponse(f"{site}/login?oauth_error={error}", status_code=302)
    if not code:
        return RedirectResponse(f"{site}/login?oauth_error=missing_code", status_code=302)

    try:
        decoded = decode_state(state or "", expected_provider=provider.value)
    except StateError as exc:
        log.warning("auth.oauth_state_invalid", provider=provider.value, error=str(exc))
        return RedirectResponse(f"{site}/login?oauth_error=invalid_state", status_code=302)

    try:
        profile = _fetch_oauth_profile(
            provider, code, decoded.redirect_uri, code_verifier=decoded.verifier
        )
    except HTTPException as exc:
        return RedirectResponse(f"{site}/login?oauth_error={exc.status_code}", status_code=302)

    email = (profile.get("email") or "").lower().strip()
    if not email:
        return RedirectResponse(
            f"{site}/login?oauth_error=no_email_from_provider", status_code=302
        )

    user = session.execute(select(User).where(User.email == email)).scalars().first()
    if user is None:
        user = User(
            email=email,
            display_name=profile.get("name") or email.split("@")[0],
            avatar_url=profile.get("avatar"),
            email_verified=True,
            role=UserRole.USER.value,
        )
        session.add(user)
        session.flush()
        analytics.record_event(session, "signup", entity_type="user", entity_id=user.id)
    elif not user.email_verified:
        user.email_verified = True

    provider_id = str(profile.get("id", email))
    account = session.execute(
        select(OAuthAccount).where(
            OAuthAccount.provider == provider.value,
            OAuthAccount.provider_account_id == provider_id,
        )
    ).scalars().first()
    if account is None:
        session.add(
            OAuthAccount(
                user_id=user.id,
                provider=provider.value,
                provider_account_id=provider_id,
                email=email,
                raw_profile=_safe_profile(profile),
            )
        )
    else:
        # Re-linking the same provider identity to the same account refreshes the
        # cached email in case it changed upstream.
        account.email = email
        account.raw_profile = _safe_profile(profile)

    _issue_tokens(response, user)
    session.commit()
    analytics.record_event(
        session,
        "login",
        entity_type="user",
        entity_id=user.id,
        properties={"method": provider.value},
    )
    return RedirectResponse(f"{site}/?oauth=success", status_code=302)


def _safe_profile(profile: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in profile.items() if k not in ("access_token", "id_token")}


def _fetch_oauth_profile(
    provider: AuthProvider,
    code: str,
    redirect_uri: str | None,
    *,
    code_verifier: str | None = None,
) -> dict[str, Any]:
    redirect = redirect_uri or settings.oauth_redirect_uri
    try:
        with httpx.Client(timeout=15.0, follow_redirects=True) as client:
            if provider is AuthProvider.GOOGLE:
                token_res = client.post(
                    GOOGLE_TOKEN_URL,
                    data={
                        "code": code,
                        "client_id": settings.google_client_id,
                        "client_secret": settings.google_client_secret,
                        "redirect_uri": redirect,
                        "grant_type": "authorization_code",
                        **({
                            "code_verifier": code_verifier
                        } if code_verifier else {}),
                    },
                )
                token_res.raise_for_status()
                token = token_res.json().get("access_token")
                if not token:
                    raise HTTPException(status_code=400, detail="Could not obtain an access token")
                info = client.get(
                    GOOGLE_USERINFO_URL, headers={"Authorization": f"Bearer {token}"}
                )
                info.raise_for_status()
                profile = info.json()
                return {
                    "id": profile.get("sub"),
                    "email": profile.get("email"),
                    "name": profile.get("name"),
                    "avatar": profile.get("picture"),
                    "email_verified": profile.get("email_verified"),
                }

            token_res = client.post(
                GITHUB_TOKEN_URL,
                headers={"Accept": "application/json"},
                data={
                    "code": code,
                    "client_id": settings.github_client_id,
                    "client_secret": settings.github_client_secret,
                    "redirect_uri": redirect,
                    **({
                        "code_verifier": code_verifier
                    } if code_verifier else {}),
                },
            )
            token_res.raise_for_status()
            token = token_res.json().get("access_token")
            if not token:
                raise HTTPException(status_code=400, detail="Could not obtain an access token")

            headers = {
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
            }
            info = client.get(GITHUB_USER_URL, headers=headers)
            info.raise_for_status()
            profile = info.json()
            email = profile.get("email")
            if not email:
                emails = client.get(GITHUB_EMAILS_URL, headers=headers)
                emails.raise_for_status()
                primary = next(
                    (e for e in emails.json() if e.get("primary") and e.get("verified")),
                    None,
                )
                email = primary.get("email") if primary else None
            return {
                "id": profile.get("id"),
                "email": email,
                "name": profile.get("name") or profile.get("login"),
                "avatar": profile.get("avatar_url"),
                "email_verified": True,
            }
    except HTTPException:
        raise
    except httpx.HTTPError as exc:
        log.warning("auth.oauth_failed", provider=provider.value, error=str(exc))
        raise HTTPException(status_code=502, detail="Could not complete sign-in with the provider")


def _subscribe_newsletter(
    session, email: str, country_code: str | None, interests: list[str]
) -> None:
    from app.models.user import NewsletterSubscriber

    existing = session.execute(
        select(NewsletterSubscriber).where(NewsletterSubscriber.email == email)
    ).scalars().first()
    if existing:
        existing.is_active = True
        existing.unsubscribed_at = None
        existing.interests = interests
        return
    session.add(
        NewsletterSubscriber(
            email=email,
            country_code=country_code,
            interests=interests,
            token=random_token(24),
            confirmed_at=utcnow(),
        )
    )


__all__ = ["Annotated", "RedirectResponse", "router"]