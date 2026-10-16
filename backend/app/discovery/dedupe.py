"""Duplicate detection across sources."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable
from urllib.parse import urlparse

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.base import utcnow
from app.discovery.normalize import NormalisedOffer, fingerprint_for, title_similarity
from app.models.offer import Offer

log = get_logger("dedupe")

TITLE_SIMILARITY_THRESHOLD = 0.86
URL_THRESHOLD = 0.93


@dataclass
class DuplicateMatch:
    offer: Offer
    reason: str
    score: float


def canonical_url(url: str) -> str:
    """Strip tracking parameters and trailing slashes."""
    parsed = urlparse(url)
    keep = [
        (k, v)
        for k, v in parse_query(parsed.query)
        if not k.lower().startswith(("utm_", "ref", "source", "fbclid", "gclid", "mc_"))
    ]
    query = "&".join(f"{k}={v}" for k, v in sorted(keep))
    path = parsed.path.rstrip("/") or "/"
    return f"{parsed.netloc.lower()}{path}" + (f"?{query}" if query else "")


def parse_query(query: str) -> Iterable[tuple[str, str]]:
    from urllib.parse import parse_qsl

    return parse_qsl(query)


def find_duplicate(
    session: Session,
    draft: NormalisedOffer,
    *,
    window_days: int = 120,
    ignore_offer_id: str | None = None,
) -> DuplicateMatch | None:
    """Look for an existing offer that represents the same deal."""
    canonical = canonical_url(draft.url)
    host = urlparse(draft.url).netloc.lower().removeprefix("www.")

    conditions = [Offer.created_at >= utcnow() - timedelta(days=window_days)]
    if ignore_offer_id:
        conditions.append(Offer.id != ignore_offer_id)

    exact = session.execute(
        select(Offer).where(
            *conditions,
            or_(Offer.official_url == draft.url, Offer.official_url.like(f"%{canonical}%")),
        )
    ).scalars().first()
    if exact is not None:
        return DuplicateMatch(exact, "same_url", 1.0)

    fingerprint = fingerprint_for(draft)
    candidates = list(
        session.execute(
            select(Offer)
            .where(*conditions)
            .order_by(Offer.created_at.desc())
            .limit(600)
        )
        .scalars()
        .unique()
        .all()
    )

    best: DuplicateMatch | None = None
    for candidate in candidates:
        same_host = (urlparse(candidate.official_url or "").netloc.lower().removeprefix("www.") == host)
        if not same_host:
            continue

        if fingerprint_for(
            NormalisedOffer(
                title=candidate.title,
                short_description=candidate.short_description,
                description=candidate.description,
                offer_type=candidate.offer_type,  # type: ignore[arg-type]
                url=candidate.official_url,
                domain=host,
                original_price=float(candidate.original_price) if candidate.original_price is not None else None,
                promo_price=float(candidate.promo_price) if candidate.promo_price is not None else None,
                coupon_code=candidate.coupon_code,
            )
        ) == fingerprint:
            return DuplicateMatch(candidate, "identical_terms", 1.0)

        ratio = title_similarity(candidate.title, draft.title)
        threshold = TITLE_SIMILARITY_THRESHOLD if (draft.coupon_code and draft.coupon_code == candidate.coupon_code) else TITLE_SIMILARITY_THRESHOLD
        if ratio >= threshold:
            if best is None or ratio > best.score:
                best = DuplicateMatch(candidate, "similar_title", round(ratio, 3))

    return best


def merge_into_existing(session: Session, existing: Offer, draft: NormalisedOffer) -> Offer:
    """Update an existing offer with any *newer* information we discovered."""
    from app.services import analytics

    changed = False

    if draft.expires_at and (existing.expires_at is None or draft.expires_at != existing.expires_at):
        existing.expires_at = draft.expires_at
        changed = True
    if draft.promo_price is not None and existing.promo_price != draft.promo_price:
        existing.promo_price = draft.promo_price
        changed = True
    if draft.original_price is not None and existing.original_price is None:
        existing.original_price = draft.original_price
        changed = True
    if draft.savings_percent and existing.savings_percent != draft.savings_percent:
        existing.savings_percent = draft.savings_percent
        changed = True
    if draft.savings_value and not existing.savings_value:
        existing.savings_value = draft.savings_value
        changed = True
    if draft.coupon_code and not existing.coupon_code:
        existing.coupon_code = draft.coupon_code
        changed = True
    if draft.trial_days and not existing.trial_days:
        existing.trial_days = draft.trial_days
        changed = True

    # A new expiry in the past means the offer is over.
    if existing.expires_at and existing.expires_at <= utcnow() and existing.status == "published":
        from app.models.enums import OfferStatus

        existing.status = OfferStatus.EXPIRED.value

    if changed:
        existing.last_checked_at = utcnow()
        existing.consecutive_failures = 0
        if existing.verification_status == "unverified":
            from app.models.enums import VerificationStatus

            existing.verification_status = VerificationStatus.NEEDS_MANUAL.value
        analytics.recompute_quality(session, existing)
    return existing


def suggest_duplicate_groups(session: Session, limit: int = 50) -> list[tuple[Offer, Offer, float]]:
    """Admin-facing duplicate pairs across the whole catalogue."""
    rows = list(
        session.execute(
            select(Offer).where(Offer.duplicate_of_id.is_(None)).order_by(Offer.created_at.desc()).limit(1500)
        )
        .scalars()
        .unique()
        .all()
    )
    pairs: list[tuple[Offer, Offer, float]] = []
    by_host: dict[str, list[Offer]] = {}
    for offer in rows:
        host = urlparse(offer.official_url or "").netloc.lower().removeprefix("www.")
        by_host.setdefault(host, []).append(offer)

    for host, group in by_host.items():
        if len(group) < 2:
            continue
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                ratio = title_similarity(group[i].title, group[j].title)
                if ratio >= TITLE_SIMILARITY_THRESHOLD:
                    pairs.append((group[i], group[j], round(ratio, 3)))
        pairs.sort(key=lambda p: p[2], reverse=True)
    return pairs[:limit]


def merge_offers(session: Session, primary: Offer, duplicate: Offer, *, keep_id: str | None = None) -> Offer:
    """Keep `primary`, fold `duplicate` into it and mark the duplicate."""
    winner, loser = (primary, duplicate)
    if keep_id and primary.id != keep_id:
        winner, loser = duplicate, primary

    winner.click_count = (winner.click_count or 0) + (loser.click_count or 0)
    winner.view_count = (winner.view_count or 0) + (loser.view_count or 0)
    winner.bookmark_count = (winner.bookmark_count or 0) + (loser.bookmark_count or 0)
    if loser.is_featured:
        winner.is_featured = True
    if loser.is_handpicked:
        winner.is_handpicked = True
    if not winner.official_url or winner.official_url == loser.official_url:
        winner.official_url = loser.official_url
    if not winner.expires_at and loser.expires_at:
        winner.expires_at = loser.expires_at

    transfer_bookmarks(session, loser, winner)
    loser.duplicate_of_id = winner.id
    loser.status = "archived"
    from app.services import analytics

    analytics.recompute_popularity(session, winner)
    session.flush()
    return winner


def transfer_bookmarks(session: Session, source_offer: Offer, target_offer: Offer) -> int:
    """Move saved offers across; drop collisions instead of failing."""
    from app.models.user import Bookmark

    rows = session.execute(
        select(Bookmark).where(Bookmark.offer_id == source_offer.id)
    ).scalars().all()
    existing_user_ids = {
        row[0]
        for row in session.execute(
            select(Bookmark.user_id).where(Bookmark.offer_id == target_offer.id)
        ).all()
    }
    moved = 0
    for bookmark in rows:
        if bookmark.user_id in existing_user_ids:
            session.delete(bookmark)
            continue
        bookmark.offer_id = target_offer.id
        moved += 1
    return moved


def count_duplicates(session: Session) -> int:
    return int(
        session.execute(
            select(func.count(Offer.id)).where(Offer.duplicate_of_id.isnot(None))
        ).scalar()
        or 0
    )