"""Discovery orchestration.

Flow per source:

    fetch (polite) -> adapter parse -> normalise -> dedupe -> persist

Persisted outcomes are either:
  * ``DiscoveryCandidate`` with status ``pending``  -> shows up in admin review
  * an ``Offer`` row in ``pending_review``          -> shows up in admin review

Nothing is auto-published unless ``DISCOVERY_AUTO_PUBLISH`` is explicitly set,
and even then the offer is flagged ``unverified`` until a human or a successful
verification check confirms it.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.db.base import utcnow
from app.discovery.base import api_key_for
from app.discovery.dedupe import find_duplicate, merge_into_existing
from app.discovery.normalize import NormalisedOffer, normalise, tags_from
from app.discovery.registry import AdapterContext, adapter_for_source
from app.models.enums import (
    EligibilityType,
    OfferStatus,
    SourceHealth,
    VerificationStatus,
)
from app.models.offer import Offer, OfferCountry, OfferEligibility
from app.models.source import DiscoveryCandidate, Source, SourceRun
from app.models.taxonomy import Brand, Category, Country
from app.schemas.admin import DiscoverySweepResult
from app.services import analytics
from app.services.offers import unique_slug

log = get_logger("discovery.runner")

ELIGIBILITY_LABELS = {
    EligibilityType.NEW_USERS: "New users only",
    EligibilityType.COUNTRIES: "Available in selected countries only",
    EligibilityType.GLOBAL: "Available worldwide",
    EligibilityType.STUDENTS: "Students only",
    EligibilityType.AGE_18_PLUS: "Must be 18 or older",
    EligibilityType.BUSINESS_EMAIL: "Business email address required",
    EligibilityType.INVITE_ONLY: "Invite only",
    EligibilityType.EXISTING_CUSTOMERS: "Existing customers only",
    EligibilityType.ANNUAL_BILLING: "Annual billing required",
    EligibilityType.PAYMENT_METHOD: "Payment method required",
    EligibilityType.PHONE_VERIFIED: "Phone number required",
    EligibilityType.IDENTITY_VERIFIED: "Identity verification required",
}

MIN_CONFIDENCE = 0.55


# ------------------------------------------------------------------- helpers
def _find_or_create_brand(session: Session, name: str | None, domain: str | None) -> Brand | None:
    if not name and not domain:
        return None
    if domain:
        existing = session.execute(
            select(Brand).where(Brand.domain == domain)
        ).scalars().first()
        if existing:
            return existing
    if name:
        existing = session.execute(select(Brand).where(Brand.name == name)).scalars().first()
        if existing:
            return existing
        from app.core.security import slugify

        brand = Brand(
            name=name,
            slug=unique_brand_slug(session, slugify(name)),
            domain=domain,
            website_url=f"https://{domain}" if domain else None,
        )
        session.add(brand)
        session.flush()
        return brand
    return None


def unique_brand_slug(session: Session, base: str) -> str:
    from app.core.security import slugify

    slug = slugify(base) or "brand"
    candidate, counter = slug, 2
    while session.execute(select(Brand.id).where(Brand.slug == candidate)).first():
        candidate = f"{slug}-{counter}"
        counter += 1
    return candidate


def resolve_category(session: Session, slug: str | None, text: str) -> Category | None:
    if slug:
        category = session.execute(
            select(Category).where(Category.slug == slug)
        ).scalars().first()
        if category:
            return category
    haystack = text.lower()
    best: Category | None = None
    best_hits = 0
    for category in session.execute(select(Category)).scalars():
        terms = set((category.keywords or []) + (category.aliases or []) + [category.slug])
        hits = sum(1 for term in terms if term and term.lower().replace("-", " ") in haystack)
        if hits > best_hits:
            best, best_hits = category, hits
    return best


def resolve_countries(session: Session, codes: Sequence[str]) -> list[Country]:
    if not codes:
        return []
    rows = session.execute(select(Country).where(Country.code.in_([c.upper() for c in codes]))).scalars().all()
    return list(rows)


# ---------------------------------------------------------------- persistence
def persist_candidate(
    session: Session,
    source: Source,
    run: SourceRun,
    draft: NormalisedOffer,
    raw_title: str,
    raw_description: str | None,
    raw_payload: dict[str, Any],
    fingerprint: str,
) -> DiscoveryCandidate:
    candidate = DiscoveryCandidate(
        source_id=source.id,
        external_id=fingerprint[:32],
        source_url=draft.url,
        raw_title=raw_title[:400],
        raw_description=(raw_description or "")[:4000] or None,
        raw_payload=raw_payload,
        fingerprint=fingerprint,
        status="pending",
        confidence=draft.confidence,
        seen_at=utcnow(),
    )
    session.add(candidate)
    session.flush()
    return candidate


def create_offer_from_draft(
    session: Session,
    source: Source,
    draft: NormalisedOffer,
    *,
    confidence: float,
    auto_publish: bool | None = None,
) -> Offer:
    brand = _find_or_create_brand(session, draft.brand_name, draft.domain)
    category = resolve_category(
        session, draft.category_slug, f"{draft.title} {draft.short_description}"
    )
    if category is None:
        fallback = session.execute(
            select(Category).where(Category.slug == "free-websites-utilities")
        ).scalars().first()
        if fallback is None:
            from app.core.security import slugify

            fallback = Category(
                slug="uncategorised",
                name="Uncategorised",
                tagline="Deals awaiting a category",
                sort_order=999,
            )
            session.add(fallback)
            session.flush()
        category = fallback

    now = utcnow()
    publish = settings.discovery_auto_publish if auto_publish is None else auto_publish
    status = OfferStatus.PUBLISHED if publish else OfferStatus.PENDING_REVIEW
    verification = (
        VerificationStatus.UNVERIFIED if publish else VerificationStatus.NEEDS_MANUAL
    )

    offer = Offer(
        slug=unique_slug(session, f"{draft.brand_name or draft.domain} {draft.title}"),
        title=draft.title,
        subtitle=None,
        short_description=draft.short_description[:400],
        description=draft.description,
        category_id=category.id,
        brand_id=brand.id if brand else None,
        offer_type=draft.offer_type.value,
        tags=tags_from(draft),
        currency=draft.currency,
        original_price=draft.original_price,
        promo_price=draft.promo_price,
        savings_value=draft.savings_value,
        savings_percent=draft.savings_percent,
        billing_period=draft.billing_period,
        trial_days=draft.trial_days,
        credits_amount=draft.credits_amount,
        credits_unit=draft.credits_unit,
        coupon_code=draft.coupon_code,
        starts_at=now,
        expires_at=draft.expires_at,
        is_global=draft.is_global,
        requires_payment_method=draft.requires_payment_method,
        requires_new_user=draft.requires_new_user,
        eligibility_types=[e.value for e in draft.eligibility_types],
        official_url=draft.url,
        source_id=source.id,
        discovery_confidence=confidence,
        verification_status=verification,
        status=status,
        published_at=now if publish else None,
        is_genuinely_free=draft.offer_type.value == "free",
        ends_as_paid=draft.offer_type.value != "free",
        how_to_redeem=[
            f"Open the official page for {brand.name if brand else draft.domain}.",
            "Sign in or create an account if you do not have one yet.",
            "Follow the on-page steps to activate the offer.",
        ],
        eligibility_notes="; ".join(draft.warnings) if draft.warnings else None,
        internal_notes=json_dumps(
            {
                "discovered_from": source.key,
                "warnings": draft.warnings,
                "raw": _trim(draft.raw),
            }
        ),
    )
    session.add(offer)
    session.flush()

    for country in resolve_countries(session, draft.country_codes):
        session.add(
            OfferCountry(
                offer_id=offer.id,
                country_code=country.code,
                is_available=True,
                note="Discovered from source text",
            )
        )
    for eligibility in draft.eligibility_types:
        session.add(
            OfferEligibility(
                offer_id=offer.id,
                rule=eligibility.value,
                label=ELIGIBILITY_LABELS.get(eligibility, eligibility.value.replace("_", " ").title()),
                blocking=eligibility
                in (
                    EligibilityType.INVITE_ONLY,
                    EligibilityType.STUDENTS,
                    EligibilityType.EXISTING_CUSTOMERS,
                    EligibilityType.BUSINESS_EMAIL,
                ),
                source_url=draft.url,
            )
        )

    analytics.recompute_quality(session, offer)
    analytics.recompute_popularity(session, offer)
    session.flush()
    return offer


def _trim(payload: dict[str, Any], limit: int = 2000) -> dict[str, Any]:
    trimmed: dict[str, Any] = {}
    for key, value in list(payload.items())[:25]:
        text = str(value)
        trimmed[key] = text[:200]
    return trimmed


def json_dumps(value: Any) -> str | None:
    import json

    try:
        return json.dumps(value, default=str)[:4000]
    except (TypeError, ValueError):
        return None


# -------------------------------------------------------------- source runs
def run_source(session: Session, source: Source, *, force: bool = False) -> dict[str, Any]:
    """Fetch + persist a single source. Returns a summary dict."""
    from app.discovery.base import fetcher
    from app.discovery.normalize import fingerprint_for

    started = utcnow()
    run = SourceRun(source_id=source.id, started_at=started, status="running")
    session.add(run)
    session.flush()

    summary: dict[str, Any] = {
        "source": source.key,
        "created": 0,
        "updated": 0,
        "duplicate": 0,
        "rejected": 0,
        "seen": 0,
        "skipped": None,
        "error": None,
    }

    if not source.is_active:
        run.status = "skipped"
        run.skipped_reason = "source inactive"
        run.finished_at = utcnow()
        summary["skipped"] = "source inactive"
        _finish_source(session, source, run, summary, healthy=False)
        return summary

    if not force and source.last_success_at and source.min_request_interval_seconds > 0:
        elapsed = (utcnow() - source.last_success_at).total_seconds()
        if elapsed < source.min_request_interval_seconds:
            remaining = int(source.min_request_interval_seconds - elapsed)
            run.status = "skipped"
            run.skipped_reason = f"throttled; retry in {remaining}s"
            run.finished_at = utcnow()
            summary["skipped"] = run.skipped_reason
            return summary

    if source.requires_js or source.is_paywalled:
        run.status = "skipped"
        run.skipped_reason = (
            "requires JavaScript" if source.requires_js else "behind a login/paywall"
        )
        run.finished_at = utcnow()
        summary["skipped"] = run.skipped_reason
        _finish_source(session, source, run, summary, healthy=True)
        return summary

    adapter = adapter_for_source(source)
    ctx = AdapterContext(source=source, api_key=api_key_for(source), config=dict(source.config or {}))

    try:
        outcome = adapter.run(ctx)
    except Exception as exc:  # pragma: no cover - defensive
        run.status = "failed"
        run.error = f"{type(exc).__name__}: {exc}"[:600]
        run.finished_at = utcnow()
        source.consecutive_failures += 1
        source.health = SourceHealth.FAILING.value
        session.flush()
        summary["error"] = run.error
        return summary

    run.http_status = outcome.http_status
    summary["seen"] = outcome.total_seen
    run.items_seen = outcome.total_seen

    if not outcome.items:
        run.status = "empty"
        run.error = "; ".join(outcome.warnings)[:600] or None
        run.finished_at = utcnow()
        summary["rejected"] = outcome.total_seen
        run.items_rejected = outcome.total_seen
        _finish_source(session, source, run, summary, healthy=True)
        return summary

    for item in outcome.items:
        draft = normalise(item)
        summary["seen"] = summary.get("seen", 0)
        fingerprint = fingerprint_for(draft)

        duplicate = find_duplicate(session, draft)
        if duplicate is not None:
            merge_into_existing(session, duplicate.offer, draft)
            candidate = persist_candidate(
                session, source, run, draft, item.title, item.description, item.raw, fingerprint
            )
            candidate.status = "duplicate"
            candidate.duplicate_of_id = duplicate.offer.id
            candidate.rejection_reason = f"duplicate of {duplicate.offer.slug} ({duplicate.reason})"
            summary["duplicate"] += 1
            run.items_duplicate += 1
            source.total_items_duplicate += 1
            continue

        candidate = persist_candidate(
            session, source, run, draft, item.title, item.description, item.raw, fingerprint
        )

        if draft.confidence < MIN_CONFIDENCE:
            candidate.status = "rejected"
            candidate.rejection_reason = (
                "; ".join(draft.warnings) or f"confidence {draft.confidence:.2f} below threshold"
            )[:240]
            summary["rejected"] += 1
            run.items_rejected += 1
            source.total_items_rejected += 1
            continue

        offer = create_offer_from_draft(session, source, draft, confidence=draft.confidence)
        candidate.status = "accepted"
        candidate.offer_id = offer.id
        summary["created"] += 1
        run.items_accepted += 1
        source.total_items_accepted += 1

    run.status = "success"
    run.finished_at = utcnow()
    run.duration_ms = int((run.finished_at - run.started_at).total_seconds() * 1000)
    run.raw_meta = {"warnings": outcome.warnings[:20], "truncated": outcome.truncated}
    _finish_source(session, source, run, summary, healthy=True)
    session.flush()
    return summary


def _finish_source(
    session: Session,
    source: Source,
    run: SourceRun,
    summary: dict[str, Any],
    *,
    healthy: bool,
) -> None:
    source.last_run_at = utcnow()
    if healthy:
        source.last_success_at = utcnow()
        source.consecutive_failures = 0
        source.health = SourceHealth.HEALTHY.value
    else:
        source.consecutive_failures += 1
        if source.consecutive_failures >= 5:
            source.health = SourceHealth.FAILING.value
        elif source.consecutive_failures >= 2:
            source.health = SourceHealth.DEGRADED.value
    source.total_items_seen += summary.get("seen", 0)
    session.flush()


def run_sweep(
    session: Session,
    *,
    source_keys: Sequence[str] | None = None,
    source_ids: Sequence[str] | None = None,
    force: bool = False,
    max_sources: int = 25,
) -> DiscoverySweepResult:
    result = DiscoverySweepResult(sources_checked=0)

    stmt = select(Source).where(Source.is_active.is_(True)).order_by(Source.last_success_at.asc().nulls_first())
    if source_keys:
        stmt = stmt.where(Source.key.in_(list(source_keys)))
    if source_ids:
        stmt = stmt.where(Source.id.in_(list(source_ids)))

    sources = list(session.execute(stmt.limit(max_sources)).scalars().all())
    for source in sources:
        summary = run_source(session, source, force=force)
        if summary.get("skipped"):
            result.sources_skipped += 1
            continue
        result.sources_checked += 1
        result.items_seen += summary.get("seen", 0)
        result.items_created += summary.get("created", 0)
        result.items_duplicate += summary.get("duplicate", 0)
        result.items_rejected += summary.get("rejected", 0)
        result.details.append(summary)
    result.items_updated = 0
    return result


def expire_removed_items(session: Session, source: Source, seen_fingerprints: set[str], older_than_hours: int = 72) -> int:
    """Items that vanished from a feed for several cycles are marked expired."""
    from app.models.enums import OfferStatus

    cutoff = utcnow() - timedelta(hours=older_than_hours)
    stale = session.execute(
        select(Offer).where(
            Offer.source_id == source.id,
            Offer.status == OfferStatus.PUBLISHED.value,
            Offer.updated_at < cutoff,
        )
    ).scalars().all()
    from app.discovery.normalize import NormalisedOffer, fingerprint_for

    changed = 0
    for offer in stale:
        fingerprint = fingerprint_for(
            NormalisedOffer(
                title=offer.title,
                short_description=offer.short_description,
                description=offer.description,
                offer_type=offer.offer_type,  # type: ignore[arg-type]
                url=offer.official_url,
                domain="",
                original_price=float(offer.original_price) if offer.original_price is not None else None,
                promo_price=float(offer.promo_price) if offer.promo_price is not None else None,
                coupon_code=offer.coupon_code,
            )
        )
        if fingerprint not in seen_fingerprints:
            offer.status = OfferStatus.EXPIRED.value
            offer.verification_status = VerificationStatus.NEEDS_MANUAL.value
            offer.internal_notes = (
                (offer.internal_notes or "")
                + "\nRemoved from the source feed during a discovery sweep."
            ).strip()
            changed += 1
    return changed


def ensure_categories_exist(session: Session, slugs: Sequence[str]) -> None:
    for slug in slugs:
        if session.execute(select(Category.id).where(Category.slug == slug)).first():
            continue
        session.add(Category(slug=slug, name=slug.replace("-", " ").title(), sort_order=500))
    session.flush()


__all__ = [
    "DiscoverySweepResult",
    "MIN_CONFIDENCE",
    "create_offer_from_draft",
    "ensure_categories_exist",
    "expire_removed_items",
    "fetch_fetcher",
    "run_source",
    "run_sweep",
]


def fetch_fetcher():  # type: ignore[no-untyped-def]
    from app.discovery.base import fetcher

    return fetcher