"""Authenticated user endpoints: profile, bookmarks, alerts, history, recs."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import delete, func, select

from app.api.deps import CountryDep, CurrencyDep, PaginationDep, RequireUser, SessionDep
from app.core.money import public_currency
from app.core.security import hash_password, verify_password
from app.db.base import utcnow
from app.models.enums import AlertKind, AuthProvider
from app.models.offer import Offer
from app.models.taxonomy import Category, Country
from app.models.user import Alert, Bookmark, OAuthAccount, RecentView, User
from app.schemas.auth import (
    AlertOut,
    AlertUpsert,
    BookmarkCreate,
    BookmarkOut,
    PasswordChange,
    RecommendationRequest,
    UserOut,
    UserUpdate,
)
from app.schemas.offer import OfferCard
from app.services import recommendations
from app.services.serializers import serialize_card

router = APIRouter(prefix="/me", tags=["account"])


@router.get("", response_model=UserOut, summary="Profile with live counters")
def profile(user: RequireUser, session: SessionDep) -> UserOut:
    bookmarks = int(
        session.execute(select(func.count(Bookmark.id)).where(Bookmark.user_id == user.id)).scalar() or 0
    )
    alerts = int(session.execute(select(func.count(Alert.id)).where(Alert.user_id == user.id)).scalar() or 0)
    return UserOut(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
        role=user.role,  # type: ignore[arg-type]
        country_code=user.country_code,
        preferred_currency=user.preferred_currency,
        locale=user.locale,
        interests=list(user.interests or []),
        email_notifications=user.email_notifications,
        newsletter_subscribed=user.newsletter_subscribed,
        is_active=user.is_active,
        created_at=user.created_at,
        bookmark_count=bookmarks,
        alert_count=alerts,
    )


@router.patch("", response_model=UserOut, summary="Update profile preferences")
def update_profile(payload: UserUpdate, user: RequireUser, session: SessionDep) -> UserOut:
    data = payload.model_dump(exclude_unset=True)

    if "country_code" in data and data["country_code"]:
        known = session.execute(
            select(Country.id).where(Country.code == data["country_code"])
        ).first()
        if not known:
            raise HTTPException(status_code=400, detail="Unsupported country code")

    if "newsletter_subscribed" in data:
        _sync_newsletter(session, user, bool(data.pop("newsletter_subscribed")))

    for key, value in data.items():
        setattr(user, key, value)
    session.commit()
    session.refresh(user)
    return profile(user, session)


@router.post("/password", summary="Change password")
def change_password(payload: PasswordChange, user: RequireUser, session: SessionDep) -> dict:
    if not user.hashed_password or not verify_password(payload.current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    user.hashed_password = hash_password(payload.new_password)
    session.commit()
    return {"ok": True, "detail": "Password updated"}


@router.get("/sessions", summary="Linked accounts")
def linked_accounts(user: RequireUser, session: SessionDep) -> list[dict]:
    rows = session.execute(
        select(OAuthAccount).where(OAuthAccount.user_id == user.id)
    ).scalars().all()
    accounts = [
        {
            "provider": AuthProvider.EMAIL.value,
            "provider_account_id": user.email,
            "email": user.email,
            "linked_at": user.created_at,
        }
    ]
    accounts.extend(
        {
            "provider": row.provider,
            "provider_account_id": row.provider_account_id,
            "email": row.email,
            "linked_at": row.created_at,
        }
        for row in rows
    )
    return accounts


@router.delete("/sessions/{provider}", status_code=status.HTTP_204_NO_CONTENT)
def unlink(provider: str, user: RequireUser, session: SessionDep) -> None:
    if provider == AuthProvider.EMAIL.value:
        raise HTTPException(status_code=400, detail="The email account cannot be unlinked")
    session.execute(
        delete(OAuthAccount).where(
            OAuthAccount.user_id == user.id, OAuthAccount.provider == provider
        )
    )
    session.commit()


# ------------------------------------------------------------- bookmarks
@router.get("/bookmarks", response_model=list[BookmarkOut], summary="Saved offers")
def list_bookmarks(
    user: RequireUser,
    session: SessionDep,
    currency: CurrencyDep,
    pagination: PaginationDep,
    include_expired: bool = True,
) -> list[BookmarkOut]:
    stmt = (
        select(Bookmark, Offer)
        .join(Offer, Bookmark.offer_id == Offer.id)
        .where(Bookmark.user_id == user.id)
        .order_by(Bookmark.created_at.desc())
        .offset((pagination.page - 1) * pagination.page_size)
        .limit(pagination.page_size)
    )
    rows = session.execute(stmt).all()
    out: list[BookmarkOut] = []
    for bookmark, offer in rows:
        if not include_expired and offer.is_expired:
            continue
        out.append(
            BookmarkOut(
                id=bookmark.id,
                offer_id=offer.id,
                note=bookmark.note,
                notify_on_expiry=bookmark.notify_on_expiry,
                notify_on_price_drop=bookmark.notify_on_price_drop,
                created_at=bookmark.created_at,
                offer=serialize_card(offer, currency=public_currency(currency)).model_dump(  # type: ignore[arg-type]
                    include={
                        "id", "slug", "title", "short_description", "offer_type", "official_url",
                        "redemption_url", "currency", "promo_price", "original_price",
                        "savings_percent", "expires_at", "is_expired", "image_url", "brand", "category",
                    }
                ),
            )
        )
    return out


@router.post("/bookmarks", response_model=BookmarkOut, status_code=status.HTTP_201_CREATED)
def add_bookmark(payload: BookmarkCreate, user: RequireUser, session: SessionDep) -> BookmarkOut:
    offer = session.get(Offer, payload.offer_id)
    if offer is None:
        raise HTTPException(status_code=404, detail="Offer not found")

    existing = session.execute(
        select(Bookmark).where(Bookmark.user_id == user.id, Bookmark.offer_id == offer.id)
    ).scalars().first()
    if existing is None:
        bookmark = Bookmark(
            user_id=user.id,
            offer_id=offer.id,
            note=payload.note,
            notify_on_expiry=payload.notify_on_expiry,
            notify_on_price_drop=payload.notify_on_price_drop,
        )
        session.add(bookmark)
        offer.bookmark_count = (offer.bookmark_count or 0) + 1
        session.flush()
    else:
        bookmark = existing
        bookmark.note = payload.note or bookmark.note

    from app.services import analytics

    analytics.record_event(
        session, "bookmark", entity_type="offer", entity_id=offer.id, user_id=user.id
    )
    session.commit()
    return BookmarkOut(
        id=bookmark.id,
        offer_id=bookmark.offer_id,
        note=bookmark.note,
        notify_on_expiry=bookmark.notify_on_expiry,
        notify_on_price_drop=bookmark.notify_on_price_drop,
        created_at=bookmark.created_at,
    )


@router.delete("/bookmarks/{offer_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_bookmark(offer_id: str, user: RequireUser, session: SessionDep) -> None:
    bookmark = session.execute(
        select(Bookmark).where(Bookmark.user_id == user.id, Bookmark.offer_id == offer_id)
    ).scalars().first()
    if bookmark is None:
        raise HTTPException(status_code=404, detail="Bookmark not found")
    session.delete(bookmark)
    offer = session.get(Offer, offer_id)
    if offer:
        offer.bookmark_count = max(0, (offer.bookmark_count or 0) - 1)
    session.commit()


@router.get("/bookmarks/check", summary="Which of these offers are saved")
def check_bookmarks(
    user: RequireUser,
    session: SessionDep,
    offer_ids: Annotated[list[str], Query()],
) -> dict:
    rows = session.execute(
        select(Bookmark.offer_id).where(Bookmark.user_id == user.id, Bookmark.offer_id.in_(offer_ids))
    ).all()
    return {"bookmarked": [row[0] for row in rows]}


# ---------------------------------------------------------------- history
@router.get("/recent", summary="Recently viewed offers")
def recent_views(
    user: RequireUser,
    session: SessionDep,
    currency: CurrencyDep,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> list[OfferCard]:
    rows = session.execute(
        select(Offer)
        .join(RecentView, RecentView.offer_id == Offer.id)
        .where(RecentView.user_id == user.id)
        .order_by(RecentView.viewed_at.desc())
        .limit(limit)
    ).scalars().unique().all()
    return [serialize_card(o, currency=public_currency(currency)) for o in rows]


@router.delete("/recent", status_code=status.HTTP_204_NO_CONTENT)
def clear_recent(user: RequireUser, session: SessionDep) -> None:
    session.execute(delete(RecentView).where(RecentView.user_id == user.id))
    session.commit()


# ----------------------------------------------------------------- alerts
@router.get("/alerts", response_model=list[AlertOut], summary="Custom alerts")
def list_alerts(user: RequireUser, session: SessionDep) -> list[AlertOut]:
    rows = session.execute(
        select(Alert).where(Alert.user_id == user.id).order_by(Alert.created_at.desc())
    ).scalars().all()
    out: list[AlertOut] = []
    for alert in rows:
        match_count = _count_alert_matches(session, alert)
        out.append(
            AlertOut(
                id=alert.id,
                kind=alert.kind,  # type: ignore[arg-type]
                label=alert.label,
                query=alert.query,
                category_id=alert.category_id,
                brand_id=alert.brand_id,
                filters=alert.filters or {},
                frequency=alert.frequency,
                is_active=alert.is_active,
                created_at=alert.created_at,
                last_triggered_at=alert.last_triggered_at,
                match_count=match_count,
            )
        )
    return out


def _count_alert_matches(session, alert: Alert) -> int:
    from app.models.enums import OfferStatus

    stmt = select(func.count(Offer.id)).where(
        Offer.status == OfferStatus.PUBLISHED.value,
        (Offer.expires_at.is_(None)) | (Offer.expires_at > utcnow()),
    )
    if alert.category_id:
        stmt = stmt.where(Offer.category_id == alert.category_id)
    if alert.brand_id:
        stmt = stmt.where(Offer.brand_id == alert.brand_id)
    if alert.filters.get("offer_type"):
        stmt = stmt.where(Offer.offer_type == alert.filters["offer_type"])
    if alert.query:
        like = f"%{alert.query.lower()}%"
        stmt = stmt.where(func.lower(Offer.title).like(like) | func.lower(Offer.short_description).like(like))
    return int(session.execute(stmt).scalar() or 0)


@router.post("/alerts", response_model=AlertOut, status_code=status.HTTP_201_CREATED)
def create_alert(payload: AlertUpsert, user: RequireUser, session: SessionDep) -> AlertOut:
    label = payload.label or _default_alert_label(session, payload)
    alert = Alert(
        user_id=user.id,
        kind=payload.kind.value,
        label=label,
        query=payload.query,
        category_id=payload.category_id,
        brand_id=payload.brand_id,
        filters=payload.filters,
        frequency=payload.frequency,
        is_active=payload.is_active,
    )
    session.add(alert)
    session.commit()
    return AlertOut(
        id=alert.id,
        kind=alert.kind,  # type: ignore[arg-type]
        label=alert.label,
        query=alert.query,
        category_id=alert.category_id,
        brand_id=alert.brand_id,
        filters=alert.filters or {},
        frequency=alert.frequency,
        is_active=alert.is_active,
        created_at=alert.created_at,
        last_triggered_at=alert.last_triggered_at,
        match_count=_count_alert_matches(session, alert),
    )


def _default_alert_label(session, payload: AlertUpsert) -> str:
    if payload.kind == AlertKind.CATEGORY and payload.category_id:
        category = session.get(Category, payload.category_id)
        if category:
            return f"New {category.name} offers"
    if payload.kind == AlertKind.BRAND and payload.brand_id:
        from app.models.taxonomy import Brand

        brand = session.get(Brand, payload.brand_id)
        if brand:
            return f"New {brand.name} offers"
    return payload.query or "New offers"


@router.patch("/alerts/{alert_id}", response_model=AlertOut)
def update_alert(alert_id: str, payload: AlertUpsert, user: RequireUser, session: SessionDep) -> AlertOut:
    alert = session.execute(
        select(Alert).where(Alert.id == alert_id, Alert.user_id == user.id)
    ).scalars().first()
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(alert, key, value.value if hasattr(value, "value") else value)
    session.commit()
    return AlertOut(
        id=alert.id,
        kind=alert.kind,  # type: ignore[arg-type]
        label=alert.label,
        query=alert.query,
        category_id=alert.category_id,
        brand_id=alert.brand_id,
        filters=alert.filters or {},
        frequency=alert.frequency,
        is_active=alert.is_active,
        created_at=alert.created_at,
        last_triggered_at=alert.last_triggered_at,
        match_count=_count_alert_matches(session, alert),
    )


@router.delete("/alerts/{alert_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_alert(alert_id: str, user: RequireUser, session: SessionDep) -> None:
    alert = session.execute(
        select(Alert).where(Alert.id == alert_id, Alert.user_id == user.id)
    ).scalars().first()
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    session.delete(alert)
    session.commit()


# -------------------------------------------------------- recommendations
@router.post("/recommendations", response_model=list[OfferCard], summary="Personalised picks")
def get_recommendations(
    payload: RecommendationRequest,
    user: RequireUser,
    session: SessionDep,
    country: CountryDep,
    currency: CurrencyDep,
) -> list[OfferCard]:
    interests = payload.interests or list(user.interests or [])
    categories = payload.categories or []
    rows = recommendations.recommend_offers(
        session,
        interests=interests,
        categories=categories,
        country_code=payload.country_code or country or user.country_code,
        limit=payload.limit,
        exclude_ids=[b.offer_id for b in user.bookmarks],
    )
    return [serialize_card(o, currency=public_currency(currency), country_code=country) for o in rows]


def _sync_newsletter(session, user: User, subscribe: bool) -> None:
    from app.core.security import random_token
    from app.models.user import NewsletterSubscriber

    row = session.execute(
        select(NewsletterSubscriber).where(NewsletterSubscriber.email == user.email)
    ).scalars().first()
    if subscribe:
        user.newsletter_subscribed = True
        if row is None:
            session.add(
                NewsletterSubscriber(
                    email=user.email,
                    country_code=user.country_code,
                    interests=list(user.interests or []),
                    token=random_token(24),
                    confirmed_at=utcnow(),
                )
            )
        else:
            row.is_active = True
            row.unsubscribed_at = None
    else:
        user.newsletter_subscribed = False
        if row is not None:
            row.is_active = False
            row.unsubscribed_at = utcnow()


def _unused(*_args: object) -> None:  # pragma: no cover
    return None