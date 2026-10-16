"""FastAPI dependencies."""

from __future__ import annotations

from typing import Annotated, Callable

from fastapi import Cookie, Depends, Header, HTTPException, Query, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import decode_token
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)

SessionDep = Annotated[Session, Depends(get_db)]


def _token_from_request(
    request: Request,
    creds: HTTPAuthorizationCredentials | None,
    cookie_token: str | None,
) -> str | None:
    if creds and creds.scheme.lower() == "bearer":
        return creds.credentials
    if cookie_token:
        return cookie_token
    header = request.headers.get("x-auth-token")
    return header


def get_current_user_optional(
    request: Request,
    session: SessionDep,
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session_token: Annotated[str | None, Cookie(alias=settings.cookie_name)] = None,
) -> User | None:
    token = _token_from_request(request, creds, session_token)
    if not token:
        return None
    payload = decode_token(token, "access")
    if not payload:
        return None
    user = session.get(User, payload.get("sub"))
    if user is None or not user.is_active or user.is_banned:
        return None
    request.state.user_id = user.id
    return user


CurrentUser = Annotated[User, Depends(get_current_user_optional)]


def get_current_user(
    user: CurrentUser,
) -> User:
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sign in to use this feature",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


RequireUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: UserRole) -> Callable[..., User]:
    allowed = {r.value if isinstance(r, UserRole) else str(r) for r in roles}

    def _dependency(user: RequireUser) -> User:
        if user.role not in allowed and not user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of: {', '.join(sorted(allowed))}",
            )
        return user

    return _dependency


RequireAdmin = Annotated[User, Depends(require_roles(UserRole.ADMIN))]
RequireReviewer = Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.REVIEWER))]


class Pagination:
    def __init__(
        self,
        page: Annotated[int, Query(ge=1, le=500)] = 1,
        page_size: Annotated[int, Query(ge=1, le=100, alias="page_size")] = 24,
    ) -> None:
        self.page = page
        self.page_size = page_size

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


PaginationDep = Annotated[Pagination, Depends(Pagination)]


def get_viewer_country(
    x_country: Annotated[str | None, Header(alias="x-country-code")] = None,
    country: Annotated[str | None, Query(alias="country")] = None,
) -> str | None:
    raw = x_country or country
    return raw.upper()[:2] if raw else None


def get_viewer_currency(
    user: CurrentUser,
    x_currency: Annotated[str | None, Header(alias="x-currency")] = None,
    currency: Annotated[str | None, Query(alias="currency")] = None,
) -> str:
    raw = currency or x_currency or (user.preferred_currency if user else None)
    return (raw or "USD").upper()[:3]


CountryDep = Annotated[str | None, Depends(get_viewer_country)]
CurrencyDep = Annotated[str, Depends(get_viewer_currency)]


def bookmarked_offer_ids(session: Session, user: User | None, offer_ids: list[str]) -> set[str]:
    if not user or not offer_ids:
        return set()
    from app.models.user import Bookmark

    rows = session.execute(
        select(Bookmark.offer_id).where(Bookmark.user_id == user.id, Bookmark.offer_id.in_(offer_ids))
    ).all()
    return {row[0] for row in rows}


def load_user(session: Session, user_id: str) -> User | None:
    return session.get(User, user_id)