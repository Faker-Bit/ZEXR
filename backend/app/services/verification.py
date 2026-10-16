"""Offer verification.

Rules of the house
------------------
* An offer is only marked ``verified`` when we could actually reach the official
  page *and* the page still contains the offer's own fingerprint terms.
* A source that requires JavaScript, a login or a paywall is never fetched —
  those offers are flagged ``needs_manual`` instead of being guessed at.
* Every check writes an ``OfferVerification`` row so the UI can show history.
"""

from __future__ import annotations

import asyncio
import hashlib
import re
from datetime import datetime, timedelta
from typing import Any, Iterable, Sequence
from urllib.parse import urlparse

import httpx
from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.db.base import utcnow
from app.models.enums import OfferStatus, VerificationResult, VerificationStatus
from app.models.offer import Offer, OfferVerification
from app.models.source import Source
from app.schemas.admin import VerificationSweepResult

log = get_logger("verification")

USER_AGENT = settings.discovery_user_agent

# 403/429 => back off hard; 5xx => retry; everything else is a hard failure.
RETRY_STATUSES = {408, 425, 429, 500, 502, 503, 504}

BLOCK_MARKERS = (
    "access denied",
    "are you a robot",
    "captcha",
    "cf-challenge",
    "please verify you are human",
    "sign in to continue",
    "enable javascript",
    "403 forbidden",
)

STRONG_SIGNALS = (
    "free trial", "free for", "days free", "month free", "free credit",
    "no credit card", "limited time", "offer ends", "promotion", "% off",
    "free plan", "start free", "claim", "redeem", "discount",
)

IGNORED_PRICE_TOKENS = {"view", "plans", "pricing", "all", "compare", "faq", "login"}


def fingerprint_terms(offer: Offer) -> list[str]:
    """Terms that must still appear on the destination page for the offer to
    still be believable.  Kept conservative — over-strict checks would mark
    perfectly good offers as broken."""
    terms: list[str] = []
    if offer.brand is not None and offer.brand.name:
        terms.append(offer.brand.name)
    if offer.coupon_code:
        terms.append(offer.coupon_code)
    for token in re.split(r"\W+", (offer.title or ""))[:6]:
        if len(token) > 4 and token.lower() not in IGNORED_PRICE_TOKENS:
            terms.append(token)
    return [t for t in dict.fromkeys(terms)][:8]


def extract_prices(html: str, currency_hint: str = "USD") -> dict[str, float | None]:
    """Promotional / original prices found on a page.

    Delegates to the discovery normaliser so a price is parsed the exact same
    way when an offer is first scraped and every time it is re-checked.
    """
    if not html:
        return {"promo_price": None, "original_price": None}
    from app.discovery.normalize import extract_prices as parse

    text = strip_tags(html)
    original, promo, _currency, _kind = parse(text)
    return {"promo_price": promo, "original_price": original}


def strip_tags(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html or ""))


def content_hash(html: str) -> str:
    cleaned = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html or ""))[:4000]
    return hashlib.sha256(cleaned.encode("utf-8", "ignore")).hexdigest()[:32]


def classify_body(html: str) -> tuple[bool, str | None]:
    lowered = (html or "")[:4000].lower()
    for marker in BLOCK_MARKERS:
        if marker in lowered:
            return True, f"blocked by anti-bot marker: {marker}"
    return False, None


# ------------------------------------------------------------------ async IO
async def fetch_offer_page(
    client: httpx.AsyncClient,
    offer: Offer,
    *,
    timeout: float | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "ok": False,
        "result": VerificationResult.FAILED.value,
        "http_status": None,
        "final_url": None,
        "html": "",
        "message": None,
    }
    url = offer.official_url
    try:
        response = await client.get(
            url,
            follow_redirects=True,
            timeout=timeout or settings.discovery_default_timeout,
            headers={"User-Agent": USER_AGENT, "Accept-Language": "en;q=0.9,*;q=0.5"},
        )
    except httpx.TimeoutException:
        result["result"] = VerificationResult.TIMEOUT.value
        result["message"] = "Request timed out"
        return result
    except httpx.HTTPError as exc:
        result["result"] = VerificationResult.FAILED.value
        result["message"] = str(exc)[:200]
        return result

    result["http_status"] = response.status_code
    result["final_url"] = str(response.url)
    result["html"] = response.text

    if response.status_code in (404, 410):
        result["result"] = VerificationResult.NOT_FOUND.value
        result["message"] = f"HTTP {response.status_code}"
        return result
    if response.status_code == 429 or response.status_code in RETRY_STATUSES:
        result["result"] = VerificationResult.SERVER_ERROR.value
        result["message"] = f"HTTP {response.status_code}"
        return result
    if response.status_code >= 400:
        result["result"] = VerificationResult.FAILED.value
        result["message"] = f"HTTP {response.status_code}"
        return result

    blocked, reason = classify_body(response.text)
    if blocked:
        result["result"] = VerificationResult.BLOCKED.value
        result["message"] = reason
        return result

    if len((response.text or "").strip()) < 200:
        result["result"] = VerificationResult.CONTENT_CHANGED.value
        result["message"] = "Page returned almost no content (likely JS-rendered)"
        return result

    result["ok"] = True
    result["result"] = VerificationResult.OK.value
    if str(response.url).rstrip("/") != url.rstrip("/"):
        result["result"] = VerificationResult.REDIRECTED.value
        result["message"] = f"Redirected to {response.url}"
    return result


def evaluate_offer(offer: Offer, payload: dict[str, Any]) -> VerificationResult:
    """Decide whether a successful fetch still supports the offer."""
    html = payload.get("html", "")
    terms = fingerprint_terms(offer)
    lowered = (html or "").lower()
    if terms and not any(term.lower() in lowered for term in terms):
        return VerificationResult.CONTENT_CHANGED

    prices = extract_prices(html)
    found_promo = prices["promo_price"]
    if found_promo is not None and found_promo > 0:
        # Compare against the advertised price and, when the offer was free,
        # against its list price too.  Only *material* changes are flagged: a
        # page that lists many prices will always surface an unrelated figure
        # (a credit amount, a renewal price), so a small mismatched number on
        # its own is treated as noise.
        expected_values = [
            float(value)
            for value in (offer.promo_price, offer.original_price)
            if value is not None and float(value) > 0
        ]
        for expected in expected_values:
            drift = abs(found_promo - expected)
            if drift <= max(1.0, expected * 0.05):
                continue
            if found_promo > expected * 1.5 or found_promo >= expected * 0.5:
                return VerificationResult.PRICE_CHANGED
    return VerificationResult(payload["result"])


# ---------------------------------------------------------------- sync runner
def verify_offer(session: Session, offer: Offer, *, client: httpx.Client | None = None) -> VerificationResult:
    """Synchronous verification used by workers, CLI and the admin panel."""
    source = offer.source
    if source is not None and (source.requires_js or source.is_paywalled):
        return _record(
            session,
            offer,
            VerificationResult.SKIPPED,
            message="Source requires JavaScript or a login — manual verification required",
            method="policy",
        )

    owns_client = client is None
    http_client = client or httpx.Client(follow_redirects=True, timeout=settings.discovery_default_timeout)
    try:
        payload = _fetch_sync(http_client, offer)
    finally:
        if owns_client:
            http_client.close()

    if not payload or not payload.get("ok"):
        return _record(
            session,
            offer,
            VerificationResult(payload["result"] if payload else VerificationResult.SKIPPED),
            http_status=payload.get("http_status") if payload else None,
            final_url=payload.get("final_url") if payload else None,
            message=payload.get("message") if payload else "No response",
            method="policy" if not payload else "http",
        )

    result = evaluate_offer(offer, payload)
    prices = extract_prices(payload.get("html", ""))
    return _record(
        session,
        offer,
        result,
        http_status=payload.get("http_status"),
        final_url=payload.get("final_url"),
        message=payload.get("message"),
        price_found=prices["promo_price"],
        original_price_found=prices["original_price"],
        details={"content_hash": content_hash(payload.get("html", ""))},
    )


def _fetch_sync(client: httpx.Client, offer: Offer) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ok": False,
        "result": VerificationResult.FAILED.value,
        "http_status": None,
        "final_url": None,
        "html": "",
        "message": None,
    }
    try:
        response = client.get(
            offer.official_url,
            headers={"User-Agent": USER_AGENT, "Accept-Language": "en;q=0.9,*;q=0.5"},
        )
    except httpx.TimeoutException:
        payload["result"] = VerificationResult.TIMEOUT.value
        payload["message"] = "Request timed out"
        return payload
    except httpx.HTTPError as exc:
        payload["message"] = str(exc)[:200]
        return payload

    payload["http_status"] = response.status_code
    payload["final_url"] = str(response.url)
    payload["html"] = response.text

    if response.status_code in (404, 410):
        payload["result"] = VerificationResult.NOT_FOUND.value
        payload["message"] = f"HTTP {response.status_code}"
    elif response.status_code >= 400:
        payload["result"] = VerificationResult.SERVER_ERROR.value if response.status_code in RETRY_STATUSES else VerificationResult.FAILED.value
        payload["message"] = f"HTTP {response.status_code}"
    else:
        blocked, reason = classify_body(response.text)
        if blocked:
            payload["result"] = VerificationResult.BLOCKED.value
            payload["message"] = reason
        elif len((response.text or "").strip()) < 200:
            payload["result"] = VerificationResult.CONTENT_CHANGED.value
            payload["message"] = "Page returned almost no content (likely JS-rendered)"
        else:
            payload["ok"] = True
            payload["result"] = (
                VerificationResult.REDIRECTED.value
                if str(response.url).rstrip("/") != offer.official_url.rstrip("/")
                else VerificationResult.OK.value
            )
            payload["message"] = payload["result"] == VerificationResult.REDIRECTED.value and str(response.url)
    return payload


def _run_async(coro: Any) -> Any:  # pragma: no cover - safety net
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    except Exception:
        return None
    finally:
        try:
            loop.close()
        except Exception:
            pass


def _record(
    session: Session,
    offer: Offer,
    result: VerificationResult,
    *,
    http_status: int | None = None,
    final_url: str | None = None,
    message: str | None = None,
    method: str = "http",
    price_found: float | None = None,
    original_price_found: float | None = None,
    details: dict[str, Any] | None = None,
) -> VerificationResult:
    now = utcnow()
    offer.last_checked_at = now
    offer.verifications.append(
        OfferVerification(
            result=result.value,
            http_status=http_status,
            final_url=final_url,
            checked_at=now,
            method=method,
            price_found=price_found,
            original_price_found=original_price_found,
            message=(message or "")[:500] or None,
            details=details,
        )
    )

    if result in (VerificationResult.OK, VerificationResult.REDIRECTED):
        offer.consecutive_failures = 0
        offer.verification_status = VerificationStatus.VERIFIED.value
        if final_url and final_url != offer.official_url:
            # Keep the original offer URL; record the redirect in history only.
            pass
        if offer.status == OfferStatus.DRAFT.value:
            offer.status = OfferStatus.PENDING_REVIEW.value
    elif result == VerificationResult.SKIPPED:
        offer.verification_status = VerificationStatus.NEEDS_MANUAL.value
    elif result in (VerificationResult.PRICE_CHANGED, VerificationResult.CONTENT_CHANGED):
        offer.consecutive_failures += 1
        offer.verification_status = VerificationStatus.NEEDS_MANUAL.value
        if offer.status == OfferStatus.PUBLISHED.value:
            offer.status = OfferStatus.DISPUTED.value
    elif result in (VerificationResult.NOT_FOUND, VerificationResult.BLOCKED):
        offer.consecutive_failures += 1
        offer.verification_status = VerificationStatus.NEEDS_MANUAL.value
        if offer.consecutive_failures >= settings.verify_broken_link_threshold:
            # Repeatedly unreachable — stop showing it as a live deal.
            offer.status = OfferStatus.EXPIRED.value
    else:
        offer.consecutive_failures += 1
        offer.verification_status = VerificationStatus.FAILED.value

    return result


# ------------------------------------------------------------------- sweeps
def offers_needing_verification(session: Session, limit: int = 200, hours: int | None = None) -> list[Offer]:
    hours = hours if hours is not None else settings.verify_interval_hours
    cutoff = utcnow() - timedelta(hours=hours)
    stmt = (
        select(Offer)
        .where(
            Offer.status.in_(
                [OfferStatus.PUBLISHED.value, OfferStatus.DISPUTED.value, OfferStatus.DRAFT.value]
            ),
            or_(Offer.last_checked_at.is_(None), Offer.last_checked_at < cutoff),
        )
        .order_by(Offer.last_checked_at.asc().nulls_first())
        .limit(limit)
    )
    return list(session.execute(stmt).scalars().unique().all())


def run_verification_sweep(
    session: Session,
    *,
    limit: int = 50,
    offer_ids: Sequence[str] | None = None,
    only_stale: bool = True,
) -> VerificationSweepResult:
    result = VerificationSweepResult(checked=0)
    if not settings.verify_enabled:
        for row in result.details:
            row["skipped"] = "verification disabled"
        return result

    if offer_ids:
        stmt = select(Offer).where(Offer.id.in_(list(offer_ids)))
        targets = list(session.execute(stmt).scalars().unique().all())
    elif only_stale:
        targets = offers_needing_verification(session, limit=limit)
    else:
        targets = list(
            session.execute(
                select(Offer)
                .where(Offer.status == OfferStatus.PUBLISHED.value)
                .order_by(Offer.published_at.desc())
                .limit(limit)
            )
            .scalars()
            .unique()
            .all()
        )

    with httpx.Client(follow_redirects=True, timeout=settings.discovery_default_timeout) as client:
        for offer in targets:
            result.checked += 1
            try:
                outcome = verify_offer(session, offer, client=client)
            except Exception as exc:  # pragma: no cover - defensive
                log.warning("verification.error", offer=offer.slug, error=str(exc))
                result.failed += 1
                continue
            result.details.append({"slug": offer.slug, "result": outcome.value})
            if outcome in (VerificationResult.OK, VerificationResult.REDIRECTED):
                result.ok += 1
            elif outcome in (VerificationResult.PRICE_CHANGED, VerificationResult.CONTENT_CHANGED):
                result.changed += 1
            elif outcome in (VerificationResult.NOT_FOUND, VerificationResult.BLOCKED):
                result.broken += 1
            elif outcome == VerificationResult.SKIPPED:
                result.skipped += 1
            else:
                result.failed += 1

    session.flush()
    return result


def expire_finished_offers(session: Session) -> int:
    now = utcnow()
    stmt = select(Offer.id).where(
        Offer.status == OfferStatus.PUBLISHED.value,
        Offer.expires_at.isnot(None),
        Offer.expires_at <= now,
    )
    ids = [row[0] for row in session.execute(stmt).all()]
    if ids:
        session.execute(
            update(Offer)
            .where(Offer.id.in_(ids))
            .values(status=OfferStatus.EXPIRED.value, trending_rank=None)
        )
    return len(ids)


def purge_old_verifications(session: Session, keep_days: int = 120) -> int:
    cutoff = utcnow() - timedelta(days=keep_days)
    rows = session.execute(
        select(OfferVerification.id).where(OfferVerification.checked_at < cutoff)
    ).all()
    if not rows:
        return 0
    ids = [r[0] for r in rows]
    session.query(OfferVerification).filter(OfferVerification.id.in_(ids)).delete(
        synchronize_session=False
    )
    return len(ids)


def source_for_offer(session: Session, offer: Offer) -> Source | None:
    if offer.source_id:
        return session.get(Source, offer.source_id)
    return None


def domain_of(url: str) -> str:
    return urlparse(url).netloc.lower()


def offers_for_source(session: Session, source: Source, limit: int = 100) -> list[Offer]:
    return list(
        session.execute(
            select(Offer).where(Offer.source_id == source.id).limit(limit)
        )
        .scalars()
        .unique()
        .all()
    )


def batch_verification_stats(session: Session) -> dict[str, int]:
    rows = session.execute(
        select(Offer.verification_status, func.count(Offer.id)).group_by(Offer.verification_status)
    ).all()
    return {status: count for status, count in rows}


def due_for_verification(session: Session) -> Iterable[Offer]:
    return offers_needing_verification(session, limit=500)


def now() -> datetime:
    return utcnow()
