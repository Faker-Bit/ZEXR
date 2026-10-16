"""Normalisation: raw upstream items -> validated, classified offer drafts.

The single most important rule in this module:

    If a field is not present in the source payload, it stays ``None``.
    We never invent a price, a discount percentage, a trial length or a code.

Instead, low-confidence extractions are dropped and the confidence score drops,
which pushes the offer into the human review queue with a *needs manual
verification* label.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Sequence
from urllib.parse import urlparse

from app.db.base import utcnow
from app.models.enums import EligibilityType, OfferType
from app.schemas.offer import DiscoveredItem

# ---------------------------------------------------------------- patterns
#: Any single price figure that carries an explicit currency or symbol.
PRICE_SINGLE_RE = re.compile(
    r"(?:(USD|EUR|GBP|INR|CAD|AUD|JPY|SGD|AED)\s*|([$€£₹])\s*)(\d[\d,]*(?:\.\d{1,2})?)"
)

#: A bare number right after a currency word, e.g. "20 USD".
PRICE_TRAILING_RE = re.compile(
    r"(\d[\d,]*(?:\.\d{1,2})?)\s*(USD|EUR|GBP|INR|CAD|AUD|JPY|SGD|AED)\b"
)

#: Words that separate an original price from its promotional price.
PRICE_CONNECTOR_RE = re.compile(
    r"\b(?:was|were|originally|list price|previously|reduced from|from|now|instead|but"
    r"|value for|down to|just)\b"
    r"|(?:→|->)",
    re.IGNORECASE,
)

#: Connectors where the figure that FOLLOWS the word is the original price.
ORIGINAL_AFTER_CONNECTORS = {
    "was", "were", "originally", "list price", "previously", "reduced from", "from",
}

PERCENT_RE = re.compile(r"(\d{1,3})\s*%\s*(?:off|discount|reduction)", re.IGNORECASE)

DURATION_RE = re.compile(
    r"(\d{1,4})\s*[- ]?\s*(day|week|month|year|hour)s?\b", re.IGNORECASE
)

COUPON_RE = re.compile(
    r"\b(?:code|coupon|voucher|promo code)\s*[:\-]?\s*([A-Z0-9][A-Z0-9\-_]{2,24})\b",
    re.IGNORECASE,
)

TYPE_PATTERNS: list[tuple[OfferType, re.Pattern[str]]] = [
    (OfferType.FREE_CREDITS, re.compile(r"\b(\$\s?\d[\d,.]*\s*(?:in )?credits?|free credits?|\d+\s*(?:api\s*)?credits?)\b", re.I)),
    (OfferType.CASHBACK, re.compile(r"\bcash\s?back\b", re.I)),
    (OfferType.COUPON, re.compile(r"\b(coupon code|promo code|voucher code|coupon)\b", re.I)),
    (OfferType.FREE_TRIAL, re.compile(r"\b(free trial|trial for free|days free|free for \d+ days?|trial)\b", re.I)),
    (OfferType.FREEMIUM, re.compile(r"\b(freemium|free (?:plan|tier))\b", re.I)),
    (OfferType.FREE_ALTERNATIVE, re.compile(r"\b(free alternative|open[- ]source alternative|instead of)\b", re.I)),
    (OfferType.DISCOUNT, re.compile(r"\b(\d{1,3}\s*%\s*off|special (?:price|offer)|discount)\b", re.I)),
    (OfferType.FREE, re.compile(r"\b(free (?:forever|to use|for everyone|no strings)|100% free|free plan)\b", re.I)),
]

ELIGIBILITY_PATTERNS: list[tuple[EligibilityType, re.Pattern[str]]] = [
    (EligibilityType.NEW_USERS, re.compile(r"\bnew (?:users?|customers?|sign-?ups?) only\b", re.I)),
    (EligibilityType.NEW_USERS, re.compile(r"\bnot (?:available to|for) existing (?:users?|subscribers?)\b", re.I)),
    (EligibilityType.STUDENTS, re.compile(r"\bstudents? only\b|\bvalid student\b|\bwith (?:a )?(?:valid )?student\b", re.I)),
    (EligibilityType.AGE_18_PLUS, re.compile(r"\b(18\+|18 years or older|must be 18)\b", re.I)),
    (EligibilityType.BUSINESS_EMAIL, re.compile(r"\bbusiness email (?:required|needed)\b", re.I)),
    (EligibilityType.INVITE_ONLY, re.compile(r"\binvite[- ]only\b|\bby invitation\b", re.I)),
    (EligibilityType.EXISTING_CUSTOMERS, re.compile(r"\bexisting (?:subscribers?|customers?|members?)\b", re.I)),
    (EligibilityType.ANNUAL_BILLING, re.compile(r"\bannual (?:plan|billing|subscription) (?:required|only)\b", re.I)),
    (EligibilityType.PAYMENT_METHOD, re.compile(r"\b(?:credit|debit) card (?:required|needed)\b", re.I)),
    (EligibilityType.PHONE_VERIFIED, re.compile(r"\bphone (?:number|verification) required\b", re.I)),
    (EligibilityType.IDENTITY_VERIFIED, re.compile(r"\bidentity (?:verification|check) required\b", re.I)),
]

NEGATIVE_PAYMENT_RE = re.compile(
    r"\bno (?:credit )?card (?:required|needed)\b|\bwithout (?:a )?credit card\b", re.I
)

COUNTRY_PATTERNS: dict[str, re.Pattern[str]] = {
    "IN": re.compile(r"\b(india|indian|rupees?|\binr\b|\brs\.?\s?\d)\b", re.I),
    "US": re.compile(r"\b(united states|\busa?\b|\busd\b|\bdollars?\b)\b", re.I),
    "GB": re.compile(r"\b(united kingdom|\buk\b|\bgbp\b|\bpounds? sterling)\b", re.I),
    "CA": re.compile(r"\b(canada|\bcad\b)\b", re.I),
    "AU": re.compile(r"\b(australia|\baud\b)\b", re.I),
    "AE": re.compile(r"\b(uae|dubai|\baed\b|dirham)\b", re.I),
    "SG": re.compile(r"\b(singapore|\bsgd\b)\b", re.I),
    "DE": re.compile(r"\b(germany|\bdeutschland\b|\beur\b)\b", re.I),
    "FR": re.compile(r"\b(france)\b", re.I),
    "JP": re.compile(r"\b(japan|\bjpy\b|\byen\b)\b", re.I),
    "BR": re.compile(r"\b(brazil|\bbrl\b|reais)\b", re.I),
}

CURRENCY_HINTS: dict[str, str] = {
    "USD": "USD", "$": "USD", "EUR": "EUR", "€": "EUR", "GBP": "GBP", "£": "GBP",
    "INR": "INR", "₹": "INR", "CAD": "CAD", "AUD": "AUD", "JPY": "JPY",
    "SGD": "SGD", "AED": "AED", "BRL": "BRL",
}

BADGE_NOISE_RE = re.compile(
    r"\b(read more|learn more|view deals?|see all|terms (?:and|&) conditions|"
    r"while supplies last|see terms|apply now|shop now|start shopping)\b",
    re.I,
)


@dataclass
class NormalisedOffer:
    """Ready-to-persist draft. Every optional field is honestly `None`."""

    title: str
    short_description: str
    description: str
    offer_type: OfferType
    url: str
    domain: str
    brand_name: str | None = None
    category_slug: str | None = None
    original_price: float | None = None
    promo_price: float | None = None
    currency: str = "USD"
    savings_percent: int = 0
    savings_value: float = 0
    billing_period: str | None = None
    trial_days: int | None = None
    credits_amount: float | None = None
    credits_unit: str | None = None
    coupon_code: str | None = None
    expires_at: datetime | None = None
    is_global: bool = True
    country_codes: list[str] = field(default_factory=list)
    eligibility_types: list[EligibilityType] = field(default_factory=list)
    requires_payment_method: bool = False
    requires_new_user: bool = True
    tags: list[str] = field(default_factory=list)
    confidence: float = 0.0
    warnings: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)


def classify_offer_type(text: str, explicit: OfferType | None = None) -> OfferType:
    if explicit is not None:
        return explicit
    for offer_type, pattern in TYPE_PATTERNS:
        if pattern.search(text):
            return offer_type
    return OfferType.FREE_TRIAL


def _price_figures(text: str) -> list[tuple[int, float, str]]:
    """Every price that carries an explicit currency code or symbol."""
    figures: list[tuple[int, float, str]] = []
    for match in PRICE_SINGLE_RE.finditer(text):
        value = _to_float(match.group(3))
        if value is None:
            continue
        currency = match.group(1) or match.group(2) or "USD"
        figures.append((match.start(), value, CURRENCY_HINTS.get(currency.upper(), "USD")))
    for match in PRICE_TRAILING_RE.finditer(text):
        if PRICE_SINGLE_RE.match(text, match.start()):
            continue
        value = _to_float(match.group(1))
        if value is None:
            continue
        figures.append((match.start(), value, CURRENCY_HINTS.get(match.group(2).upper(), "USD")))
    return sorted(figures)


def extract_prices(text: str) -> tuple[float | None, float | None, str, str | None]:
    """Return (original_price, promo_price, currency, discount_kind).

    Only figures that appear verbatim in the source text are returned — the
    function never estimates or invents a price.  A pair is produced when a
    connector word ("was", "now", "→", ...) separates two explicit prices, or
    when a "N% off" percentage makes the original derivable.
    """
    figures = _price_figures(text)
    if len(figures) >= 2:
        first_at = figures[0][0]
        last_at = figures[-1][0]
        connector = None
        for candidate in PRICE_CONNECTOR_RE.finditer(text):
            # Only connectors sitting *between* two prices describe a pair.
            if first_at < candidate.start() and candidate.end() < last_at:
                connector = candidate
                break

        if connector is not None:
            before = [f for f in figures if f[0] < connector.start()][-1]
            after = [f for f in figures if f[0] >= connector.end()][0]
            word = connector.group(0).strip().lower()
            if word in ORIGINAL_AFTER_CONNECTORS and after[1] > before[1]:
                # "$50 off, was $100" -> promo 50, original 100
                return after[1], before[1], after[2], "percent"
            # "$20 now $10" / "20 USD was 15 USD" -> original 20, promo 15
            return before[1], after[1], before[2], "percent"

    percent = PERCENT_RE.search(text)
    if percent and figures:
        _, value, currency = figures[0]
        discount = int(percent.group(1))
        if 0 < discount < 100:
            return round(value / (1 - discount / 100), 2), value, currency, "percent"
        return None, value, currency, None

    if figures:
        _, value, currency = figures[0]
        return None, value, currency, None
    return None, None, "USD", None


def extract_duration(text: str) -> tuple[int | None, str | None]:
    match = DURATION_RE.search(text)
    if not match:
        return None, None
    amount = int(match.group(1))
    unit = match.group(2).lower()
    days = {"hour": 0.0417, "day": 1, "week": 7, "month": 30, "year": 365}[unit]
    return max(1, int(round(amount * days))), unit


def extract_coupon(text: str) -> str | None:
    match = COUPON_RE.search(text)
    return match.group(1).upper() if match else None


def extract_expiry(text: str, now: datetime | None = None) -> datetime | None:
    """Only accept an explicit, parseable deadline that lies in the future."""
    now = now or utcnow()
    patterns = [
        r"(?:ends?|expires?|valid|until|through|offer ends)\s+(?:on\s+)?([0-9]{1,2}[/-][0-9]{1,2}[/-][0-9]{2,4})",
        r"(?:ends?|expires?|valid|until|through)\s+([A-Z][a-z]+ \d{1,2},? \d{4})",
        r"(?:ends?|expires?|valid|until|through)\s+in (\d+) (day|week|month)s?",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            continue
        if match.lastindex and match.lastindex == 3:
            amount, unit = int(match.group(2)), match.group(3).lower()
            delta = {"day": 1, "week": 7, "month": 30}[unit]
            return now + timedelta(days=amount * delta)
        from app.discovery.adapters.json_api import parse_datetime

        parsed = parse_datetime(match.group(1))
        if parsed and parsed > now:
            return parsed
    return None


def detect_eligibility(text: str) -> tuple[list[EligibilityType], bool]:
    types: list[EligibilityType] = []
    for eligibility, pattern in ELIGIBILITY_PATTERNS:
        if pattern.search(text):
            types.append(eligibility)
    if types and EligibilityType.NEW_USERS not in types:
        types.append(EligibilityType.NEW_USERS)
    if types:
        types.append(EligibilityType.GLOBAL if "worldwide" in text.lower() or "everywhere" in text.lower() else EligibilityType.COUNTRIES)
    requires_payment = any(
        eligibility is EligibilityType.PAYMENT_METHOD for eligibility in types
    ) and not NEGATIVE_PAYMENT_RE.search(text)
    return list(dict.fromkeys(types)), requires_payment


def detect_countries(text: str) -> list[str]:
    found = [code for code, pattern in COUNTRY_PATTERNS.items() if pattern.search(text)]
    if re.search(r"\b(worldwide|globally|everywhere|any country|all countries)\b", text, re.I):
        return []
    return found


def tidy_title(raw_title: str) -> str:
    title = (raw_title or "").strip()
    title = BADGE_NOISE_RE.sub("", title)
    title = re.sub(r"\s{2,}", " ", title).strip(" -–—|:")
    # strip a trailing site name like " - Example.com"
    title = re.sub(r"\s+[-–—]\s+[A-Za-z0-9.]+\.(com|net|org|io|co|ai)$", "", title)
    return title[:240] or "Untitled offer"


def estimate_confidence(item: DiscoveredItem, draft: NormalisedOffer) -> float:
    """How much we trust this extraction (0-1). Anything < 0.55 goes to review."""
    score = 0.25
    if item.url and item.url.startswith("http"):
        score += 0.15
    if item.title and len(item.title) > 12:
        score += 0.1
    if item.description and len(item.description or "") > 40:
        score += 0.1
    if draft.original_price is not None and draft.promo_price is not None:
        score += 0.15
    elif draft.promo_price is not None:
        score += 0.08
    if draft.trial_days:
        score += 0.08
    if draft.expires_at:
        score += 0.08
    if draft.coupon_code:
        score += 0.05
    if item.brand_name:
        score += 0.05
    if item.category_slug:
        score += 0.04
    if item.offer_type is not None:
        score += 0.06
    if urlparse(item.url).netloc.count(".") >= 1:
        score += 0.03
    score -= 0.1 * len(draft.warnings)
    return max(0.0, min(1.0, round(score, 3)))


def normalise(item: DiscoveredItem) -> NormalisedOffer:
    title = tidy_title(item.title)
    body = " ".join(filter(None, [item.title, item.description or ""]))
    domain = urlparse(item.url).netloc.lower().removeprefix("www.")

    offer_type = classify_offer_type(body, item.offer_type)
    original, promo, currency, discount_kind = extract_prices(body)
    if item.original_price is not None:
        original = item.original_price
    if item.promo_price is not None:
        promo = item.promo_price
    if item.currency:
        currency = item.currency.upper()

    trial_days, unit = extract_duration(body)
    if item.trial_days:
        trial_days = item.trial_days
        unit = unit or "day"

    coupon = item.coupon_code or extract_coupon(body)
    expires_at = item.expires_at or extract_expiry(body)
    eligibility, requires_payment = detect_eligibility(body)
    countries = item.country_codes or detect_countries(body)

    percent = PERCENT_RE.search(body)
    savings_percent = int(percent.group(1)) if percent else 0
    savings_value = 0.0
    if original is not None and promo is not None and promo < original:
        savings_value = round(original - promo, 2)
        if not savings_percent:
            savings_percent = int(round((1 - promo / original) * 100))
    elif promo == 0 and original:
        savings_value = round(original, 2)
        savings_percent = 100

    billing_period = None
    if re.search(r"\bper (?:month|mo)\b|\bmonthly\b", body, re.I):
        billing_period = "monthly"
    elif re.search(r"\bper (?:year|yr)\b|\bannually\b|\byearly\b", body, re.I):
        billing_period = "yearly"
    elif re.search(r"\blifetime\b|\bone[- ]time\b", body, re.I):
        billing_period = "lifetime"

    credits_amount, credits_unit = None, None
    if offer_type is OfferType.FREE_CREDITS:
        credit_match = re.search(r"(\$?\s?\d[\d,.]*)\s*(api|cloud|compute|token|credit)?s?\s*credits?", body, re.I)
        if credit_match:
            credits_amount = _to_float(credit_match.group(1).replace("$", ""))
            credits_unit = (credit_match.group(2) or "credit").strip().lower()

    # A permanently free offer has, by definition, no price and no end date, and
    # most feeds never publish an expiry at all.  Flagging those absences as
    # warnings pushed genuinely-good free tiers ("10,000 free neurons/day",
    # "free Serverless tier") below the confidence threshold.  Confidence should
    # measure whether we can believe the offer *exists* — real vendor URL, clear
    # title, substantive description — not whether the payload is fully enriched.
    # So: warn about a missing price only where a price is genuinely expected.
    PRICED_TYPES = (OfferType.DISCOUNT, OfferType.COUPON, OfferType.CASHBACK)

    warnings: list[str] = []
    if promo is None and original is None and offer_type in PRICED_TYPES:
        warnings.append("no price found in source payload")
    if discount_kind and original and promo and promo >= original:
        warnings.append("extracted promo price is not lower than the original")

    short = (item.description or title).strip()
    short = re.sub(r"\s+", " ", short)[:380]

    draft = NormalisedOffer(
        title=title,
        short_description=short or title,
        description=(item.description or title).strip()[:8000],
        offer_type=offer_type,
        url=item.url,
        domain=domain,
        brand_name=item.brand_name,
        category_slug=item.category_slug,
        original_price=original,
        promo_price=promo,
        currency=currency or "USD",
        savings_percent=savings_percent,
        savings_value=savings_value,
        billing_period=billing_period,
        trial_days=trial_days,
        credits_amount=credits_amount,
        credits_unit=credits_unit,
        coupon_code=coupon,
        expires_at=expires_at,
        is_global=not countries,
        country_codes=countries,
        eligibility_types=eligibility,
        requires_payment_method=requires_payment,
        requires_new_user=any(e is EligibilityType.NEW_USERS for e in eligibility),
        tags=item.tags[:10],
        warnings=warnings,
        raw=item.raw,
    )
    draft.confidence = estimate_confidence(item, draft)
    return draft


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).replace(",", "").replace("$", "").strip())
    except (TypeError, ValueError):
        return None


def fingerprint_for(draft: NormalisedOffer) -> str:
    """Stable hash used for duplicate detection."""
    import hashlib

    key = "|".join(
        [
            re.sub(r"[^a-z0-9]+", "", (draft.title or "").lower())[:60],
            (draft.domain or ""),
            (draft.coupon_code or ""),
            draft.original_price and f"{draft.original_price}" or "",
            draft.promo_price and f"{draft.promo_price}" or "",
        ]
    )
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def title_similarity(a: str, b: str) -> float:
    from difflib import SequenceMatcher

    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def tags_from(draft: NormalisedOffer) -> list[str]:
    tags = set(t.lower() for t in draft.tags if t)
    if draft.offer_type is OfferType.FREE_CREDITS and draft.credits_amount:
        tags.add(f"{int(draft.credits_amount)} credits")
    if draft.coupon_code:
        tags.add("coupon code")
    if not draft.requires_payment_method and draft.offer_type in (
        OfferType.FREE,
        OfferType.FREE_CREDITS,
    ):
        tags.add("no credit card")
    if draft.savings_percent >= 50:
        tags.add(f"{draft.savings_percent}% off")
    return sorted(tags)[:12]