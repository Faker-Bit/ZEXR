"""Admin API. Every route requires an authenticated admin or reviewer account."""

from __future__ import annotations

import os
from datetime import timedelta
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import delete, func, or_, select

from app.api.deps import RequireAdmin, RequireReviewer, SessionDep
from app.api.cache_sync import cache_drop
from app.core.logging import get_logger
from app.core.security import slugify
from app.db.base import utcnow
from app.discovery import dedupe
from app.discovery.runner import create_offer_from_draft, run_source, run_sweep
from app.discovery.normalize import normalise
from app.discovery.normalize import fingerprint_for
from app.models.analytics import SearchQueryLog
from app.models.enums import (
    OfferStatus,
    SourceHealth,
    VerificationStatus,
)
from app.models.offer import Offer, OfferCountry, OfferVerification
from app.models.source import DiscoveryCandidate, Source, SourceRun
from app.models.taxonomy import Brand, Category
from app.models.user import Report, Submission, User
from app.schemas.admin import (
    AnalyticsOverview,
    BrandAdminOut,
    BrandUpsert,
    BulkOfferAction,
    CandidateDecision,
    CandidateOut,
    CategoryAdminOut,
    CategoryUpsert,
    DashboardStats,
    DiscoverySweepResult,
    ReportAdminOut,
    ReportResolution,
    ScheduledJobOut,
    SourceOut,
    SourceRunOut,
    SourceUpsert,
    SubmissionOut,
    UserAdminOut,
    UserRoleChange,
    VerificationSweepResult,
)
from app.schemas.common import Page
from app.schemas.offer import DiscoveredItem, OfferDetail, OfferStatusChange, OfferUpsert
from app.services import analytics
from app.services import search as search_service
from app.services import verification
from app.services.offers import unique_slug
from app.services.serializers import serialize_detail

log = get_logger("admin")
router = APIRouter(prefix="/admin", tags=["admin"])


def _invalidate() -> None:
    for namespace in ("offers", "search", "stats", "taxonomy"):
        cache_drop(namespace)
    search_service.invalidate_vocabulary_cache()


# ---------------------------------------------------------------- dashboard
@router.get("/stats", response_model=DashboardStats, summary="Platform health at a glance")
def stats(session: SessionDep, _admin: RequireReviewer) -> DashboardStats:
    return analytics.dashboard_stats(session)


@router.get("/analytics", response_model=AnalyticsOverview, summary="Traffic + conversion overview")
def overview(
    session: SessionDep,
    _admin: RequireReviewer,
    days: Annotated[int, Query(ge=1, le=180)] = 30,
) -> AnalyticsOverview:
    return analytics.analytics_overview(session, days=days)


# ------------------------------------------------------------------- offers
def _load_offer(session, offer_id: str) -> Offer:
    from app.services.offers import get_offer_by_slug

    offer = session.get(Offer, offer_id)
    if offer is None:
        raise HTTPException(status_code=404, detail="Offer not found")
    return offer


@router.get("/offers", summary="Admin offer list (includes every status)")
def admin_offers(
    session: SessionDep,
    _admin: RequireReviewer,
    page: Annotated[int, Query(ge=1, le=500)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, alias="page_size")] = 25,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    verification_filter: Annotated[str | None, Query(alias="verification")] = None,
    category: Annotated[str | None, Query()] = None,
    source: Annotated[str | None, Query()] = None,
    q: Annotated[str | None, Query(max_length=200)] = None,
    demo_only: bool | None = None,
    include_duplicates: bool = True,
) -> dict:
    stmt = select(Offer)
    if status_filter:
        stmt = stmt.where(Offer.status == status_filter)
    if verification_filter:
        stmt = stmt.where(Offer.verification_status == verification_filter)
    if category:
        stmt = stmt.join(Category, Offer.category_id == Category.id).where(Category.slug == category)
    if source:
        stmt = stmt.join(Source, Offer.source_id == Source.id).where(Source.key == source)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(
            or_(func.lower(Offer.title).like(like), func.lower(Offer.short_description).like(like))
        )
    if demo_only is not None:
        stmt = stmt.where(Offer.is_demo_data.is_(demo_only))
    if not include_duplicates:
        stmt = stmt.where(Offer.duplicate_of_id.is_(None))

    stmt = stmt.order_by(Offer.created_at.desc())
    total = int(
        session.execute(select(func.count()).select_from(stmt.order_by(None).subquery())).scalar() or 0
    )
    rows = session.execute(
        stmt.offset((page - 1) * page_size).limit(page_size)
    ).scalars().unique().all()

    from app.services.serializers import serialize_card

    return {
        "items": [
            {
                **serialize_card(offer).model_dump(mode="json"),
                "source_key": getattr(offer.source, "key", None),
                "duplicate_of_id": offer.duplicate_of_id,
                "created_at": offer.created_at.isoformat(),
                "consecutive_failures": offer.consecutive_failures,
                "discovery_confidence": offer.discovery_confidence,
            }
            for offer in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, (total + page_size - 1) // page_size),
    }


@router.post("/offers", response_model=OfferDetail, status_code=status.HTTP_201_CREATED)
def create_offer(
    payload: OfferUpsert, session: SessionDep, admin: RequireAdmin, publish: bool = False
) -> OfferDetail:
    from app.models.enums import OfferType

    category = session.get(Category, payload.category_id)
    if category is None:
        raise HTTPException(status_code=400, detail="Unknown category")

    slug = payload.slug or unique_slug(session, f"{payload.title}")
    now = utcnow()
    final_status = OfferStatus.PUBLISHED if publish else payload.status
    if publish and not payload.published_at:
        payload.published_at = now

    offer = Offer(
        slug=slug,
        title=payload.title,
        subtitle=payload.subtitle,
        short_description=payload.short_description,
        description=payload.description,
        category_id=payload.category_id,
        brand_id=payload.brand_id,
        secondary_category_ids=payload.secondary_category_ids,
        offer_type=payload.offer_type.value,
        tags=payload.tags,
        currency=payload.currency,
        original_price=payload.original_price,
        promo_price=payload.promo_price,
        billing_period=payload.billing_period,
        renewal_price=payload.renewal_price,
        discount_kind=payload.discount_kind.value if payload.discount_kind else None,
        discount_amount=payload.discount_amount,
        credits_amount=payload.credits_amount,
        credits_unit=payload.credits_unit,
        trial_days=payload.trial_days,
        starts_at=payload.starts_at,
        expires_at=payload.expires_at,
        redemption_deadline=payload.redemption_deadline,
        is_global=payload.is_global,
        excluded_countries=payload.excluded_countries,
        requires_new_user=payload.requires_new_user,
        requires_student_id=payload.requires_student_id,
        minimum_age=payload.minimum_age,
        requires_payment_method=payload.requires_payment_method,
        requires_auto_renew=payload.requires_auto_renew,
        eligibility_notes=payload.eligibility_notes,
        eligibility_types=[e.value for e in payload.eligibility_types],
        how_to_redeem=payload.how_to_redeem,
        fine_print=payload.fine_print,
        features=payload.features,
        is_genuinely_free=payload.is_genuinely_free,
        ends_as_paid=payload.ends_as_paid,
        official_url=str(payload.official_url),
        affiliate_url=str(payload.affiliate_url) if payload.affiliate_url else None,
        coupon_code=payload.coupon_code,
        image_url=payload.image_url,
        is_sponsored=payload.is_sponsored,
        sponsor_name=payload.sponsor_name,
        status=final_status.value,
        verification_status=payload.verification_status.value,
        verified_by_id=admin.id if payload.verification_status == VerificationStatus.VERIFIED else None,
        verified_at=now if payload.verification_status == VerificationStatus.VERIFIED else None,
        published_at=payload.published_at,
        is_featured=payload.is_featured,
        is_handpicked=payload.is_handpicked,
        is_demo_data=payload.is_demo_data,
        internal_notes=payload.internal_notes,
    )
    session.add(offer)
    session.flush()

    _sync_children(session, offer, payload)
    value, percent = _savings(offer)
    offer.savings_value = value
    offer.savings_percent = percent
    analytics.recompute_quality(session, offer)
    analytics.recompute_popularity(session, offer)

    analytics.record_event(
        session,
        "admin_action",
        entity_type="offer",
        entity_id=offer.id,
        user_id=admin.id,
        properties={"action": "create"},
    )
    session.commit()
    _invalidate()
    return serialize_detail(_reload(session, offer.id))


def _savings(offer: Offer) -> tuple[float, int]:
    from app.services.offers import compute_savings

    return compute_savings(offer)


def _sync_children(session, offer: Offer, payload: OfferUpsert) -> None:
    from app.models.offer import OfferEligibility

    session.query(OfferCountry).filter(OfferCountry.offer_id == offer.id).delete(
        synchronize_session=False
    )
    for code in payload.country_codes:
        session.add(
            OfferCountry(
                offer_id=offer.id,
                country_code=code.upper(),
                is_available=True,
                verified_at=utcnow(),
                note="Set by admin",
            )
        )
    session.query(OfferEligibility).filter(OfferEligibility.offer_id == offer.id).delete(
        synchronize_session=False
    )
    for rule in payload.eligibility_types:
        session.add(
            OfferEligibility(
                offer_id=offer.id,
                rule=rule.value,
                label=rule.value.replace("_", " ").title(),
                blocking=rule.value in ("invite_only", "students", "existing_customers"),
                source_url=offer.official_url,
            )
        )
    session.flush()


def _reload(session, offer_id: str) -> Offer:
    from app.services.offers import get_offer_by_slug

    session.expire_all()
    offer = session.get(Offer, offer_id)
    assert offer is not None
    return get_offer_by_slug(session, offer.slug) or offer


@router.get("/offers/{offer_id}", response_model=OfferDetail, summary="Offer with internal fields")
def get_offer_admin(offer_id: str, session: SessionDep, _admin: RequireReviewer) -> OfferDetail:
    offer = session.get(Offer, offer_id)
    if offer is None:
        raise HTTPException(status_code=404, detail="Offer not found")
    from app.services.offers import get_offer_by_slug

    full = get_offer_by_slug(session, offer.slug) or offer
    detail = serialize_detail(full)
    return detail


@router.put("/offers/{offer_id}", response_model=OfferDetail, summary="Update an offer")
def update_offer(
    offer_id: str, payload: OfferUpsert, session: SessionDep, admin: RequireAdmin
) -> OfferDetail:
    offer = _load_offer(session, offer_id)
    before_status = offer.status

    for key, value in payload.model_dump(exclude_unset=True, exclude={"slug"}).items():
        if hasattr(Offer, key):
            setattr(offer, key, value.value if hasattr(value, "value") else value)

    if payload.slug and payload.slug != offer.slug:
        offer.slug = payload.slug
    offer.updated_at = utcnow()
    _sync_children(session, offer, payload)

    value, percent = _savings(offer)
    offer.savings_value = value
    offer.savings_percent = percent
    analytics.recompute_quality(session, offer)

    if payload.verification_status == VerificationStatus.VERIFIED:
        offer.verified_by_id = admin.id
        offer.verified_at = utcnow()
    elif payload.verification_status != VerificationStatus.VERIFIED:
        offer.verified_by_id = None
        offer.verified_at = None

    if before_status != offer.status:
        analytics.record_event(
            session,
            "admin_action",
            entity_type="offer",
            entity_id=offer.id,
            user_id=admin.id,
            properties={"action": "status", "from": before_status, "to": offer.status},
        )
    session.commit()
    _invalidate()
    return serialize_detail(_reload(session, offer.id))


@router.patch("/offers/{offer_id}/status", response_model=OfferDetail, summary="Publish / reject / expire")
def change_status(
    offer_id: str, payload: OfferStatusChange, session: SessionDep, admin: RequireReviewer
) -> OfferDetail:
    offer = _load_offer(session, offer_id)
    now = utcnow()
    offer.status = payload.status.value
    if payload.verification_status:
        offer.verification_status = payload.verification_status.value
        if payload.verification_status == VerificationStatus.VERIFIED:
            offer.verified_by_id = admin.id
            offer.verified_at = now
    if payload.is_featured is not None:
        offer.is_featured = payload.is_featured
    if payload.is_handpicked is not None:
        offer.is_handpicked = payload.is_handpicked
    if payload.status == OfferStatus.PUBLISHED and not offer.published_at:
        offer.published_at = now
    if payload.status in (OfferStatus.EXPIRED, OfferStatus.REJECTED, OfferStatus.ARCHIVED):
        offer.trending_rank = None

    analytics.record_event(
        session,
        "admin_action",
        entity_type="offer",
        entity_id=offer.id,
        user_id=admin.id,
        properties={"action": "status", "to": offer.status, "reason": payload.reason},
    )
    session.commit()
    _invalidate()
    return serialize_detail(_reload(session, offer.id))


@router.post("/offers/bulk", summary="Bulk moderation action")
def bulk_action(
    payload: BulkOfferAction, session: SessionDep, admin: RequireReviewer
) -> dict:
    now = utcnow()
    rows = session.execute(select(Offer).where(Offer.id.in_(payload.offer_ids))).scalars().all()
    affected = 0
    for offer in rows:
        action = payload.action
        if action == "publish":
            offer.status = OfferStatus.PUBLISHED.value
            offer.published_at = offer.published_at or now
        elif action == "reject":
            offer.status = OfferStatus.REJECTED.value
        elif action == "expire":
            offer.status = OfferStatus.EXPIRED.value
        elif action == "archive":
            offer.status = OfferStatus.ARCHIVED.value
        elif action == "feature":
            offer.is_featured = True
        elif action == "unfeature":
            offer.is_featured = False
        elif action == "verify":
            offer.verification_status = VerificationStatus.VERIFIED.value
            offer.verified_by_id = admin.id
            offer.verified_at = now
        elif action == "delete":
            session.delete(offer)
        affected += 1

    analytics.record_event(
        session,
        "admin_action",
        user_id=admin.id,
        properties={"action": f"bulk:{payload.action}", "count": affected},
    )
    session.commit()
    _invalidate()
    return {"ok": True, "affected": affected, "reason": payload.reason}


@router.delete("/offers/{offer_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_offer(offer_id: str, session: SessionDep, admin: RequireAdmin) -> None:
    offer = _load_offer(session, offer_id)
    session.delete(offer)
    analytics.record_event(
        session, "admin_action", entity_type="offer", user_id=admin.id,
        properties={"action": "delete", "slug": offer.slug},
    )
    session.commit()
    _invalidate()


@router.post("/offers/{offer_id}/verify", response_model=VerificationSweepResult)
def verify_now(offer_id: str, session: SessionDep, _admin: RequireReviewer) -> VerificationSweepResult:
    offer = _load_offer(session, offer_id)
    result = verification.run_verification_sweep(session, offer_ids=[offer.id], only_stale=False)
    session.commit()
    _invalidate()
    return result


@router.post("/verify/sweep", response_model=VerificationSweepResult, summary="Run verification across the catalogue")
def verify_sweep(
    session: SessionDep,
    _admin: RequireReviewer,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    all_offers: bool = False,
) -> VerificationSweepResult:
    result = verification.run_verification_sweep(session, limit=limit, only_stale=not all_offers)
    verification.expire_finished_offers(session)
    session.commit()
    _invalidate()
    return result


# --------------------------------------------------------------- duplicates
@router.get("/duplicates", summary="Possible duplicate pairs")
def duplicates(
    session: SessionDep, _admin: RequireReviewer, limit: Annotated[int, Query(ge=1, le=100)] = 25
) -> list[dict]:
    pairs = dedupe.suggest_duplicate_groups(session, limit=limit)
    return [
        {
            "primary": {
                "id": a.id, "slug": a.slug, "title": a.title, "status": a.status,
                "official_url": a.official_url, "savings_value": float(a.savings_value or 0),
            },
            "duplicate": {
                "id": b.id, "slug": b.slug, "title": b.title, "status": b.status,
                "official_url": b.official_url, "savings_value": float(b.savings_value or 0),
            },
            "similarity": score,
        }
        for a, b, score in pairs
    ]


@router.post("/duplicates/merge", summary="Merge a duplicate into the primary offer")
def merge_duplicate(
    session: SessionDep, admin: RequireReviewer, keep_id: str, drop_id: str
) -> dict:
    primary = session.get(Offer, keep_id)
    duplicate = session.get(Offer, drop_id)
    if primary is None or duplicate is None or primary.id == duplicate.id:
        raise HTTPException(status_code=400, detail="Two distinct offers are required")
    winner = dedupe.merge_offers(session, primary, duplicate, keep_id=keep_id)
    analytics.record_event(
        session, "admin_action", entity_type="offer", entity_id=winner.id, user_id=admin.id,
        properties={"action": "merge", "dropped": duplicate.slug},
    )
    session.commit()
    _invalidate()
    return {"ok": True, "kept": winner.slug}


# ------------------------------------------------------------------ sources
@router.get("/sources", response_model=list[SourceOut], summary="Data sources")
def list_sources(session: SessionDep, _admin: RequireReviewer) -> list[SourceOut]:
    rows = session.execute(select(Source).order_by(Source.name.asc())).scalars().all()
    out: list[SourceOut] = []
    for source in rows:
        out.append(
            SourceOut(
                id=source.id,
                key=source.key,
                name=source.name,
                publisher=source.publisher,
                source_type=source.source_type,  # type: ignore[arg-type]
                adapter=source.adapter,
                homepage_url=source.homepage_url,
                feed_url=source.feed_url,
                api_docs_url=source.api_docs_url,
                is_active=source.is_active,
                respect_robots=source.respect_robots,
                requires_js=source.requires_js,
                is_paywalled=source.is_paywalled,
                rate_limit_per_hour=source.rate_limit_per_hour,
                min_request_interval_seconds=source.min_request_interval_seconds,
                cache_ttl_seconds=source.cache_ttl_seconds,
                max_items=source.max_items,
                health=source.health,  # type: ignore[arg-type]
                trust_weight=source.trust_weight,
                license_note=source.license_note,
                terms_url=source.terms_url,
                config=source.config or {},
                api_key_configured=bool(source.api_key_env and os.getenv(source.api_key_env)),
                last_run_at=source.last_run_at,
                last_success_at=source.last_success_at,
                consecutive_failures=source.consecutive_failures,
                total_items_seen=source.total_items_seen,
                total_items_accepted=source.total_items_accepted,
                total_items_duplicate=source.total_items_duplicate,
                total_items_rejected=source.total_items_rejected,
            )
        )
    return out


@router.post("/sources", response_model=SourceOut, status_code=status.HTTP_201_CREATED)
def create_source(payload: SourceUpsert, session: SessionDep, _admin: RequireAdmin) -> SourceOut:
    if session.execute(select(Source.id).where(Source.key == payload.key)).first():
        raise HTTPException(status_code=409, detail="A source with this key already exists")
    source = Source(**{**payload.model_dump(), "source_type": payload.source_type.value})
    session.add(source)
    session.commit()
    return list_sources(session, _admin)[0]


@router.patch("/sources/{source_id}", response_model=SourceOut)
def update_source(source_id: str, payload: SourceUpsert, session: SessionDep, _admin: RequireAdmin) -> SourceOut:
    source = session.get(Source, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(source, key, value.value if hasattr(value, "value") else value)
    session.commit()
    return [s for s in list_sources(session, _admin) if s.id == source_id][0]


@router.delete("/sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_source(source_id: str, session: SessionDep, _admin: RequireAdmin) -> None:
    source = session.get(Source, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    session.delete(source)
    session.commit()


@router.post("/sources/{source_id}/run", summary="Run one source immediately")
def run_one_source(source_id: str, session: SessionDep, _admin: RequireReviewer) -> dict:
    source = session.get(Source, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    summary = run_source(session, source, force=True)
    session.commit()
    _invalidate()
    return summary


@router.post("/discover/sweep", response_model=DiscoverySweepResult, summary="Run discovery across sources")
def discover(
    session: SessionDep,
    _admin: RequireReviewer,
    source_key: Annotated[str | None, Query()] = None,
    max_sources: Annotated[int, Query(ge=1, le=100)] = 10,
) -> DiscoverySweepResult:
    result = run_sweep(
        session,
        source_keys=[source_key] if source_key else None,
        max_sources=max_sources,
    )
    session.commit()
    _invalidate()
    return result


@router.get("/sources/{source_id}/runs", response_model=list[SourceRunOut])
def source_runs(
    source_id: str, session: SessionDep, _admin: RequireReviewer, limit: int = 25
) -> list[SourceRunOut]:
    rows = session.execute(
        select(SourceRun)
        .where(SourceRun.source_id == source_id)
        .order_by(SourceRun.started_at.desc())
        .limit(limit)
    ).scalars().all()
    return [
        SourceRunOut(
            id=r.id,
            source_id=r.source_id,
            source_key=getattr(r.source, "key", None),
            started_at=r.started_at,
            finished_at=r.finished_at,
            status=r.status,
            http_status=r.http_status,
            items_seen=r.items_seen,
            items_accepted=r.items_accepted,
            items_duplicate=r.items_duplicate,
            items_rejected=r.items_rejected,
            skipped_reason=r.skipped_reason,
            error=r.error,
            duration_ms=r.duration_ms,
        )
        for r in rows
    ]


@router.get("/candidates", response_model=Page[CandidateOut], summary="Discovery review queue")
def candidates(
    session: SessionDep,
    _admin: RequireReviewer,
    page: Annotated[int, Query(ge=1, le=500)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, alias="page_size")] = 25,
    status_filter: Annotated[str | None, Query(alias="status")] = "pending",
    source_key: Annotated[str | None, Query()] = None,
) -> Page[CandidateOut]:
    stmt = select(DiscoveryCandidate)
    if status_filter:
        stmt = stmt.where(DiscoveryCandidate.status == status_filter)
    if source_key:
        stmt = stmt.join(Source, DiscoveryCandidate.source_id == Source.id).where(Source.key == source_key)
    stmt = stmt.order_by(DiscoveryCandidate.confidence.desc(), DiscoveryCandidate.seen_at.desc())

    total = int(
        session.execute(select(func.count()).select_from(stmt.order_by(None).subquery())).scalar() or 0
    )
    rows = session.execute(
        stmt.offset((page - 1) * page_size).limit(page_size)
    ).scalars().all()
    items = [
        CandidateOut(
            id=c.id,
            source_id=c.source_id,
            source_key=getattr(c.source, "key", None),
            source_url=c.source_url,
            raw_title=c.raw_title,
            raw_description=c.raw_description,
            status=c.status,
            rejection_reason=c.rejection_reason,
            confidence=c.confidence,
            offer_id=c.offer_id,
            duplicate_of_id=c.duplicate_of_id,
            reviewed_at=c.reviewed_at,
            seen_at=c.seen_at,
            parsed=_summarise_candidate(c),
        )
        for c in rows
    ]
    return Page.build(items, total, page, page_size)


def _candidate_raw(candidate: DiscoveryCandidate) -> dict[str, Any]:
    import json

    try:
        payload = json.loads(candidate.raw_payload or "{}")
    except (TypeError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _summarise_candidate(candidate: DiscoveryCandidate) -> dict[str, Any]:
    item = _candidate_raw(candidate)
    draft = normalise(
        DiscoveredItem(
            title=candidate.raw_title,
            description=candidate.raw_description,
            url=candidate.source_url,
            raw=item,
        )
    )
    return {
        "offer_type": draft.offer_type.value,
        "original_price": draft.original_price,
        "promo_price": draft.promo_price,
        "currency": draft.currency,
        "trial_days": draft.trial_days,
        "expires_at": draft.expires_at.isoformat() if draft.expires_at else None,
        "coupon_code": draft.coupon_code,
        "country_codes": draft.country_codes,
        "eligibility": [e.value for e in draft.eligibility_types],
        "confidence": draft.confidence,
        "warnings": draft.warnings,
    }


@router.post("/candidates/{candidate_id}/decision", summary="Approve / reject / mark duplicate")
def decide_candidate(
    candidate_id: str, payload: CandidateDecision, session: SessionDep, admin: RequireReviewer
) -> dict:
    candidate = session.get(DiscoveryCandidate, candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found")
    source = candidate.source
    if source is None:
        raise HTTPException(status_code=400, detail="Candidate has no source")

    if payload.action == "approve":
        item = _candidate_raw(candidate)
        draft = normalise(
            DiscoveredItem(
                title=candidate.raw_title,
                description=candidate.raw_description,
                url=candidate.source_url,
                raw=item,
            )
        )
        offer = create_offer_from_draft(session, source, draft, confidence=candidate.confidence)
        candidate.status = "accepted"
        candidate.offer_id = offer.id
        result = {"offer_slug": offer.slug}
    elif payload.action == "reject":
        candidate.status = "rejected"
        candidate.rejection_reason = payload.reason or "Rejected by reviewer"
        result = {}
    else:
        candidate.status = "duplicate"
        candidate.rejection_reason = payload.reason or "Marked as duplicate by reviewer"
        result = {}

    candidate.reviewed_by_id = admin.id
    candidate.reviewed_at = utcnow()
    session.commit()
    _invalidate()
    return {"ok": True, "candidate_status": candidate.status, **result}


# ----------------------------------------------------------------- taxonomy
@router.get("/categories", response_model=list[CategoryAdminOut])
def admin_categories(session: SessionDep, _admin: RequireReviewer) -> list[CategoryAdminOut]:
    rows = session.execute(
        select(Category, func.count(Offer.id))
        .join(Offer, Offer.category_id == Category.id, isouter=True)
        .group_by(Category.id)
        .order_by(Category.sort_order.asc())
    ).all()
    out: list[CategoryAdminOut] = []
    for category, count in rows:
        item = CategoryAdminOut(
            id=category.id,
            slug=category.slug,
            name=category.name,
            tagline=category.tagline,
            description=category.description,
            icon=category.icon,
            color=category.color,
            group_name=category.group_name,
            sort_order=category.sort_order,
            is_active=category.is_active,
            seo_title=category.seo_title,
            seo_description=category.seo_description,
            keywords=list(category.keywords or []),
            aliases=list(category.aliases or []),
            offer_count=int(count),
        )
        out.append(item)
    return out


@router.post("/categories", response_model=CategoryAdminOut, status_code=status.HTTP_201_CREATED)
def create_category(payload: CategoryUpsert, session: SessionDep, _admin: RequireAdmin) -> CategoryAdminOut:
    if session.execute(select(Category.id).where(Category.slug == payload.slug)).first():
        raise HTTPException(status_code=409, detail="Category slug already exists")
    category = Category(**payload.model_dump())
    session.add(category)
    session.commit()
    _invalidate()
    return admin_categories(session, _admin)[0]


@router.patch("/categories/{category_id}", response_model=CategoryAdminOut)
def update_category(
    category_id: str, payload: CategoryUpsert, session: SessionDep, _admin: RequireAdmin
) -> CategoryAdminOut:
    category = session.get(Category, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(category, key, value)
    session.commit()
    _invalidate()
    return [c for c in admin_categories(session, _admin) if c.id == category_id][0]


@router.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(category_id: str, session: SessionDep, admin: RequireAdmin) -> None:
    category = session.get(Category, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")
    used = int(
        session.execute(
            select(func.count(Offer.id)).where(Offer.category_id == category_id)
        ).scalar()
        or 0
    )
    if used:
        raise HTTPException(
            status_code=409, detail=f"{used} offers still use this category — reassign them first"
        )
    session.delete(category)
    session.commit()
    _invalidate()


@router.get("/brands", response_model=list[BrandAdminOut])
def admin_brands(session: SessionDep, _admin: RequireReviewer) -> list[BrandAdminOut]:
    rows = session.execute(
        select(Brand, func.count(Offer.id))
        .join(Offer, Offer.brand_id == Brand.id, isouter=True)
        .group_by(Brand.id)
        .order_by(func.count(Offer.id).desc())
    ).all()
    return [
        BrandAdminOut(
            id=brand.id,
            name=brand.name,
            slug=brand.slug,
            domain=brand.domain,
            website_url=brand.website_url,
            logo_url=brand.logo_url,
            accent_color=brand.accent_color,
            description=brand.description,
            aliases=list(brand.aliases or []),
            category_id=brand.category_id,
            country_code=brand.country_code,
            is_verified=brand.is_verified,
            is_active=brand.is_active,
            followers_count=brand.followers_count,
            offer_count=int(count),
        )
        for brand, count in rows
    ]


@router.post("/brands", response_model=BrandAdminOut, status_code=status.HTTP_201_CREATED)
def create_brand(payload: BrandUpsert, session: SessionDep, _admin: RequireAdmin) -> BrandAdminOut:
    base = slugify(payload.name)
    candidate, counter = base, 2
    while session.execute(select(Brand.id).where(Brand.slug == candidate)).first():
        candidate = f"{base}-{counter}"
        counter += 1
    brand = Brand(**{**payload.model_dump(), "slug": candidate})
    session.add(brand)
    session.commit()
    _invalidate()
    return admin_brands(session, _admin)[0]


@router.patch("/brands/{brand_id}", response_model=BrandAdminOut)
def update_brand(
    brand_id: str, payload: BrandUpsert, session: SessionDep, _admin: RequireAdmin
) -> BrandAdminOut:
    brand = session.get(Brand, brand_id)
    if brand is None:
        raise HTTPException(status_code=404, detail="Brand not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(brand, key, value)
    session.commit()
    _invalidate()
    return [b for b in admin_brands(session, _admin) if b.id == brand_id][0]


# -------------------------------------------------------------------- users
@router.get("/users", response_model=list[UserAdminOut])
def list_users(
    session: SessionDep, _admin: RequireAdmin, q: str | None = None, limit: int = 50
) -> list[UserAdminOut]:
    from app.models.user import Bookmark

    stmt = (
        select(User, func.count(Bookmark.id))
        .join(Bookmark, Bookmark.user_id == User.id, isouter=True)
    )
    if q:
        stmt = stmt.where(func.lower(User.email).like(f"%{q.lower()}%"))
    stmt = stmt.group_by(User.id).order_by(User.created_at.desc()).limit(limit)
    rows = session.execute(stmt).all()
    return [
        UserAdminOut(
            id=user.id,
            email=user.email,
            display_name=user.display_name,
            role=user.role,
            country_code=user.country_code,
            preferred_currency=user.preferred_currency,
            is_active=user.is_active,
            is_banned=user.is_banned,
            created_at=user.created_at,
            last_login_at=user.last_login_at,
            bookmark_count=int(count),
        )
        for user, count in rows
    ]


@router.patch("/users/{user_id}/role", response_model=UserAdminOut)
def change_role(
    user_id: str, payload: UserRoleChange, session: SessionDep, admin: RequireAdmin
) -> UserAdminOut:
    if user_id == admin.id and payload.role != "admin":
        raise HTTPException(status_code=400, detail="You cannot demote your own account")
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    user.role = payload.role
    if payload.is_active is not None:
        user.is_active = payload.is_active
    if payload.is_banned is not None:
        user.is_banned = payload.is_banned
    session.commit()
    return [u for u in list_users(session, admin) if u.id == user_id][0]


# ------------------------------------------------------------------ reports
@router.get("/reports", response_model=list[ReportAdminOut])
def list_reports(
    session: SessionDep, _admin: RequireReviewer, status_filter: str | None = None, limit: int = 100
) -> list[ReportAdminOut]:
    stmt = select(Report, Offer).join(Offer, Report.offer_id == Offer.id, isouter=True)
    if status_filter:
        stmt = stmt.where(Report.status == status_filter)
    stmt = stmt.order_by(Report.created_at.desc()).limit(limit)
    rows = session.execute(stmt).all()
    return [
        ReportAdminOut(
            id=report.id,
            offer_id=report.offer_id,
            offer_title=offer.title if offer else None,
            reason=report.reason,
            details=report.details,
            status=report.status,
            reporter_email=report.reporter_email,
            created_at=report.created_at,
            resolved_at=report.resolved_at,
            resolution_note=report.resolution_note,
        )
        for report, offer in rows
    ]


@router.patch("/reports/{report_id}", response_model=ReportAdminOut)
def resolve_report(
    report_id: str, payload: ReportResolution, session: SessionDep, admin: RequireReviewer
) -> ReportAdminOut:
    report = session.get(Report, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    report.status = payload.status
    report.resolution_note = payload.resolution_note
    report.resolved_by_id = admin.id
    report.resolved_at = utcnow() if payload.status in ("resolved", "dismissed") else None

    if payload.mark_offer_disputed and report.offer_id:
        offer = session.get(Offer, report.offer_id)
        if offer:
            offer.status = OfferStatus.DISPUTED.value
            offer.verification_status = VerificationStatus.NEEDS_MANUAL.value

    session.commit()
    _invalidate()
    offer = session.get(Offer, report.offer_id) if report.offer_id else None
    return ReportAdminOut(
        id=report.id,
        offer_id=report.offer_id,
        offer_title=offer.title if offer else None,
        reason=report.reason,
        details=report.details,
        status=report.status,
        reporter_email=report.reporter_email,
        created_at=report.created_at,
        resolved_at=report.resolved_at,
        resolution_note=report.resolution_note,
    )


@router.get("/submissions", response_model=list[SubmissionOut])
def list_submissions(
    session: SessionDep, _admin: RequireReviewer, status_filter: str | None = "pending"
) -> list[SubmissionOut]:
    stmt = select(Submission)
    if status_filter:
        stmt = stmt.where(Submission.status == status_filter)
    rows = session.execute(stmt.order_by(Submission.created_at.desc())).scalars().all()
    return [
        SubmissionOut(
            id=s.id,
            title=s.title,
            brand_name=s.brand_name,
            official_url=s.official_url,
            category_slug=s.category_slug,
            offer_type=s.offer_type,
            notes=s.notes,
            submitter_email=s.submitter_email,
            status=s.status,
            created_at=s.created_at,
            created_offer_id=s.created_offer_id,
        )
        for s in rows
    ]


@router.post("/submissions/{submission_id}/convert", summary="Turn a submission into a draft offer")
def convert_submission(
    submission_id: str, session: SessionDep, admin: RequireReviewer
) -> dict:
    submission = session.get(Submission, submission_id)
    if submission is None:
        raise HTTPException(status_code=404, detail="Submission not found")
    category = None
    if submission.category_slug:
        category = session.execute(
            select(Category).where(Category.slug == submission.category_slug)
        ).scalars().first()
    if category is None:
        category = session.execute(select(Category).order_by(Category.sort_order.asc())).scalars().first()
    if category is None:
        raise HTTPException(status_code=400, detail="No categories exist yet")

    draft = normalise(
        DiscoveredItem(
            title=submission.title,
            description=submission.notes,
            url=submission.official_url,
            brand_name=submission.brand_name,
            category_slug=submission.category_slug,
        )
    )
    offer = create_offer_from_draft(session, _manual_source(session), draft, confidence=1.0)
    submission.status = "converted"
    submission.created_offer_id = offer.id
    submission.reviewed_by_id = admin.id
    submission.reviewed_at = utcnow()
    session.commit()
    _invalidate()
    return {"ok": True, "offer_slug": offer.slug}


def _manual_source(session) -> Source:
    source = session.execute(select(Source).where(Source.key == "manual-intake")).scalars().first()
    if source is None:
        source = Source(
            key="manual-intake",
            name="Manual intake",
            publisher="ZEXR Deal Hub editors",
            source_type="manual",
            adapter="manual",
            homepage_url="https://zexrdealhub.com/admin/offers/new",
            trust_weight=1.0,
        )
        session.add(source)
        session.flush()
    return source


# ------------------------------------------------------------------- jobs
@router.get("/jobs", response_model=list[ScheduledJobOut], summary="Scheduled background jobs")
def jobs(_admin: RequireReviewer) -> list[ScheduledJobOut]:
    from app.workers.scheduler import describe_jobs

    return describe_jobs()


@router.post("/maintenance/expiry", summary="Expire offers whose deadline has passed")
def run_expiry(session: SessionDep, _admin: RequireReviewer) -> dict:
    count = verification.expire_finished_offers(session)
    session.commit()
    _invalidate()
    return {"ok": True, "expired": count}


@router.post("/maintenance/trending", summary="Recompute trending ranks")
def run_trending(session: SessionDep, _admin: RequireReviewer) -> dict:
    analytics.bump_trending(session)
    session.commit()
    _invalidate()
    return {"ok": True}


@router.post("/maintenance/rollup", summary="Roll raw events into daily aggregates")
def run_rollup(session: SessionDep, _admin: RequireReviewer) -> dict:
    moved = analytics.rollup_events(session, days=1)
    session.commit()
    return {"ok": True, "events_rolled_up": moved}


@router.get("/search-log", summary="Recent search queries")
def search_log(
    session: SessionDep, _admin: RequireReviewer, limit: int = 50, zero_only: bool = False
) -> list[dict]:
    stmt = select(SearchQueryLog)
    if zero_only:
        stmt = stmt.where(SearchQueryLog.zero_results.is_(True))
    rows = session.execute(stmt.order_by(SearchQueryLog.created_at.desc()).limit(limit)).scalars().all()
    return [
        {
            "query": r.query,
            "intent": r.intent,
            "results": r.result_count,
            "took_ms": r.took_ms,
            "country": r.country_code,
            "zero_results": r.zero_results,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]

