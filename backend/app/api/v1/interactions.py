"""Public interaction endpoints: click tracking, reports, newsletter, events."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from sqlalchemy import func, select

from app.api.deps import CountryDep, CurrentUser, SessionDep
from app.core.logging import get_logger
from app.core.ratelimit import limit
from app.core.security import random_token
from app.db.base import utcnow
from app.services import stats as stats_service
from app.models.offer import Offer
from app.models.user import NewsletterSubscriber, Report, Submission
from app.schemas.auth import NewsletterResult, NewsletterSubscribe, ReportCreate
from app.schemas.common import Message
from app.services import analytics

log = get_logger("interactions")
router = APIRouter(tags=["interactions"])


@router.get("/go/{slug}", summary="Track an outbound claim click and redirect")
@limit("240/minute")
def track_click(
    slug: str,
    session: SessionDep,
    request: Request,
    response: Response,
    country: CountryDep,
    session_id: Annotated[str | None, Query(alias="sid")] = None,
    user: CurrentUser = None,
) -> Response:
    offer = (
        session.execute(select(Offer).where(Offer.slug == slug)).scalars().first()
    )
    if offer is None:
        raise HTTPException(status_code=404, detail="Offer not found")

    analytics.record_offer_click(
        session,
        offer,
        user_id=user.id if user else None,
        session_id=session_id,
        referrer=request.headers.get("referer"),
        country_code=country,
    )
    session.commit()

    target = offer.redemption_url
    response = Response(status_code=307)
    response.headers["Location"] = target
    response.headers["Referrer-Policy"] = "no-referrer-when-downgrade"
    response.headers["Cache-Control"] = "no-store"
    # Surfaced so the frontend can label the outbound link for the user.
    # Header names must be HTTP tokens (no spaces), so this uses the slug rather
    # than the human-readable app name.
    response.headers["X-Zexr-Affiliate"] = "1" if offer.affiliate_url else "0"
    return response


@router.post("/reports", response_model=Message, status_code=status.HTTP_201_CREATED)
@limit("10/minute")
def create_report(
    request: Request,
    response: Response,
    payload: ReportCreate,
    session: SessionDep,
    user: CurrentUser,
) -> Message:
    if payload.offer_id:
        offer = session.get(Offer, payload.offer_id)
        if offer is None:
            raise HTTPException(status_code=404, detail="Offer not found")
        if offer.status == "disputed":
            raise HTTPException(status_code=409, detail="This offer is already under review")

    report = Report(
        offer_id=payload.offer_id,
        user_id=user.id if user else None,
        reporter_email=(payload.email or (user.email if user else None)),
        reason=payload.reason,
        details=payload.details,
    )
    session.add(report)
    analytics.record_event(
        session,
        "report",
        entity_type="offer",
        entity_id=payload.offer_id,
        user_id=user.id if user else None,
        properties={"reason": payload.reason},
    )
    session.commit()
    return Message(
        detail="Thanks — a reviewer will check this offer. Reported offers are re-verified automatically.",
        ok=True,
    )


@router.post("/newsletter", response_model=NewsletterResult)
@limit("8/minute")
def subscribe_newsletter(
    request: Request, response: Response, payload: NewsletterSubscribe, session: SessionDep
) -> NewsletterResult:
    email = payload.email.lower().strip()
    existing = session.execute(
        select(NewsletterSubscriber).where(NewsletterSubscriber.email == email)
    ).scalars().first()
    if existing and existing.is_active:
        return NewsletterResult(
            ok=True,
            message="You are already subscribed — nothing more to do.",
            already_subscribed=True,
        )

    if existing:
        existing.is_active = True
        existing.unsubscribed_at = None
        existing.interests = payload.interests
        existing.country_code = payload.country_code or existing.country_code
        existing.frequency = payload.frequency
        existing.confirmed_at = utcnow()
        existing.token = random_token(24)
    else:
        session.add(
            NewsletterSubscriber(
                email=email,
                country_code=payload.country_code,
                interests=payload.interests,
                frequency=payload.frequency,
                token=random_token(24),
                confirmed_at=utcnow(),
            )
        )

    analytics.record_event(session, "newsletter_signup", properties={"email_domain": email.split("@")[-1]})
    session.commit()
    return NewsletterResult(
        ok=True,
        message="Subscribed. Look out for the next digest of verified deals.",
        already_subscribed=False,
    )


@router.get("/newsletter/unsubscribe")
def unsubscribe(token: str, session: SessionDep) -> Message:
    row = session.execute(
        select(NewsletterSubscriber).where(NewsletterSubscriber.token == token)
    ).scalars().first()
    if row is None:
        raise HTTPException(status_code=404, detail="Unknown subscription token")
    row.is_active = False
    row.unsubscribed_at = utcnow()
    session.commit()
    return Message(detail="You have been unsubscribed.", ok=True)


@router.post("/submit", response_model=Message, status_code=status.HTTP_201_CREATED)
@limit("5/hour")
def submit_offer(
    request: Request,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
    title: Annotated[str, Query(min_length=6, max_length=240)] = "",
    url: Annotated[str, Query(min_length=8, max_length=700)] = "",
    brand_name: Annotated[str | None, Query(max_length=160)] = None,
    category_slug: Annotated[str | None, Query(max_length=120)] = None,
    notes: Annotated[str | None, Query(max_length=2000)] = None,
) -> Message:
    if not title or not url:
        raise HTTPException(status_code=400, detail="title and url are required")
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"

    submission = Submission(
        submitted_by_id=user.id if user else None,
        submitter_email=user.email if user else None,
        title=title,
        brand_name=brand_name,
        official_url=url,
        category_slug=category_slug,
        notes=notes,
        status="pending",
    )
    session.add(submission)
    session.commit()
    return Message(
        detail=(
            "Thanks. A reviewer will confirm the offer against the official page before it "
            "goes live — nothing is published automatically."
        ),
        ok=True,
    )


@router.post("/events", status_code=status.HTTP_202_ACCEPTED)
@limit("300/minute")
def track_event(
    request: Request,
    response: Response,
    session: SessionDep,
    country: CountryDep,
    user: CurrentUser,
    event: Annotated[str, Query(max_length=40)],
    path: Annotated[str | None, Query(max_length=500)] = None,
    session_id: Annotated[str | None, Query(alias="sid")] = None,
    category: Annotated[str | None, Query(max_length=120)] = None,
    value: Annotated[float | None, Query()] = None,
) -> dict:
    allowed = {
        "page_view", "search", "share", "offer_view", "newsletter_signup",
        "category_view", "filter_applied",
    }
    if event not in allowed:
        raise HTTPException(status_code=400, detail=f"Unknown event '{event}'")

    analytics.record_event(
        session,
        event,
        user_id=user.id if user else None,
        session_id=session_id,
        path=path,
        country_code=country,
        referrer=request.headers.get("referer"),
        value=value,
        properties={"category": category} if category else None,
        flush=False,
    )
    session.commit()
    return {"ok": True}


@router.get("/stats/today", summary="Today's page views and visitors (public)")
@limit("120/minute")
def today_stats(request: Request, response: Response, session: SessionDep) -> dict[str, int]:
    """Public counters for the header.

    Two integers, no breakdown. Anonymous and read-only, so it is safe to expose,
    and it is the same first-party session count the privacy page describes.
    Served from a short in-process cache so the header costs nothing per render.
    """
    return stats_service.today_stats(session)


@router.get("/reports/mine", summary="Reports you have filed")
def my_reports(user: CurrentUser, session: SessionDep) -> list[dict]:
    rows = session.execute(
        select(Report).where(Report.user_id == user.id).order_by(Report.created_at.desc())
    ).scalars().all()
    return [
        {
            "id": r.id,
            "offer_id": r.offer_id,
            "reason": r.reason,
            "status": r.status,
            "created_at": r.created_at,
            "resolution_note": r.resolution_note if r.status == "resolved" else None,
        }
        for r in rows
    ]