"""Search: intent parsing, typo tolerance, portable relevance ranking.

Design goals
------------
1.  A query like *"30 days free vpn without credit card"* becomes structured
    filters (offer_type=free_trial, min_trial_days=30, category=vpn,
    requires_payment_method=false) **and** a text ranking.
2.  Everything is grounded in rows that actually exist — the interpreter only
    maps words onto taxonomy and enum values stored in the database.  Nothing is
    invented, so a mis-parse degrades to plain keyword search.
3.  Scoring is expressed with portable SQL constructs so it behaves the same on
    PostgreSQL and on the SQLite dev database.
"""

from __future__ import annotations

import difflib
import re
import time
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Iterable, Sequence

from sqlalchemy import Select, case, cast, func, literal, or_, select, Text
from sqlalchemy.orm import Session, selectinload

from app.core.logging import get_logger
from app.models.enums import EligibilityType, OfferType
from app.models.offer import Offer
from app.models.taxonomy import Brand, Category, Country
from app.schemas.offer import ParsedIntent, SearchSuggestion

log = get_logger("search")

# --------------------------------------------------------------------------
# Lexicon
# --------------------------------------------------------------------------
STOPWORDS = {
    "a", "an", "the", "for", "of", "to", "in", "on", "with", "and", "or", "best",
    "good", "great", "cheapest", "cheap", "near", "me", "my", "any", "all",
    "i", "we", "you", "is", "are", "am", "want", "need", "looking", "find",
    "get", "use", "using", "currently", "right", "now", "today", "please",
    "show", "give", "list", "top", "really", "very", "much", "more", "less",
    "website", "site", "online", "app", "thing", "stuff", "some", "somehow",
    "worth", "expiring", "soon", "new", "brand", "offer", "offers", "deals",
    "deal", "promo", "promotion", "promotions", "sale",
}

# words that express a *type* rather than a topic — excluded from the
# "must match something" requirement so "30 days free vpn" does not fail to
# match because no row contains the literal string "30 days".
TYPE_WORDS = {
    "free", "freemium", "trial", "trials", "freecredits", "credit", "credits",
    "discount", "discounts", "off", "sale", "coupon", "coupons", "promo",
    "cashback", "alternative", "alternatives", "freebie", "giveaway",
}

DURATION_WORDS = {"day", "days", "week", "weeks", "month", "months", "year", "years", "hour", "hours"}

TYPE_SYNONYMS: dict[str, list[str]] = {
    "trial": ["trial", "trials", "freemium", "preview"],
    "free": ["free", "freebie", "gratis", "nofee"],
    "credits": ["credits", "credit", "balance", "allowance", "quota"],
    "discount": ["discount", "discounts", "off", "reduced", "sale", "deals"],
    "coupon": ["coupon", "coupons", "code", "codes", "voucher", "promo"],
    "cashback": ["cashback", "cashbackoffers"],
    "alternative": ["alternative", "alternatives", "instead", "opensource"],
}

TOPIC_SYNONYMS: dict[str, list[str]] = {
    "vpn": ["vpn", "proxy", "privacy", "tunnel"],
    "hosting": ["hosting", "cloud", "server", "servers", "vps", "infrastructure"],
    "ai": ["ai", "llm", "gpt", "model", "models", "genai", "chatbot", "inference"],
    "streaming": ["streaming", "stream", "movies", "tv", "watch"],
    "gaming": ["gaming", "game", "games", "xbox", "playstation", "nintendo"],
    "design": ["design", "graphics", "photo", "video editing", "creative"],
    "shopping": ["shopping", "ecommerce", "store", "fashion", "clothing"],
    "food": ["food", "delivery", "meal", "meals", "restaurant", "grocery"],
    "travel": ["travel", "hotel", "hotels", "flight", "flights", "booking"],
    "education": ["education", "learning", "course", "courses", "student", "school"],
    "finance": ["finance", "bank", "banking", "money", "invest", "investment", "cashback"],
    "productivity": ["productivity", "notes", "task", "tasks", "project", "workspace"],
    "developer": ["developer", "api", "apis", "sdk", "code", "coding", "devtools"],
    "security": ["security", "antivirus", "password", "encryption", "privacy"],
    "email": ["email", "mail", "inbox", "marketing email"],
    "saas": ["saas", "business", "startup", "crm", "team"],
}

FREE_PHRASES = {
    "no credit card": "no_card",
    "without credit card": "no_card",
    "without a credit card": "no_card",
    "no creditcard": "no_card",
    "don't need credit card": "no_card",
    "free forever": "forever",
    "for free": "free",
    "free of charge": "free",
}

COUNTRY_ALIASES = {
    "india": "IN", "indian": "IN", "bharat": "IN",
    "usa": "US", "u.s.": "US", "us": "US", "america": "US", "united states": "US",
    "uk": "GB", "britain": "GB", "united kingdom": "GB", "england": "GB",
    "canada": "CA", "australia": "AU", "germany": "DE", "france": "FR",
    "spain": "ES", "italy": "IT", "netherlands": "NL", "dubai": "AE", "uae": "AE",
    "singapore": "SG", "japan": "JP", "china": "CN", "brazil": "BR",
    "pakistan": "PK", "bangladesh": "BD", "indonesia": "ID", "philippines": "PH",
    "poland": "PL", "sweden": "SE", "norway": "NO", "denmark": "DK",
    "mexico": "MX", "south africa": "ZA", "new zealand": "NZ", "ireland": "IE",
    "turkey": "TR", "russia": "RU", "korea": "KR", "taiwan": "TW", "hong kong": "HK",
}

CURRENCY_SYMBOLS = {
    "$": "USD", "us$": "USD", "usd": "USD", "€": "EUR", "eur": "EUR",
    "£": "GBP", "gbp": "GBP", "₹": "INR", "inr": "INR", "rs": "INR",
    "¥": "JPY", "jpy": "JPY", "a$": "AUD", "aud": "AUD", "c$": "CAD", "cad": "CAD",
}

COMPARATORS = {
    "under": "<", "below": "<", "less": "<", "fewer": "<", "cheaper": "<",
    "upto": "<=", "upto": "<=", "max": "<=", "over": ">", "above": ">",
    "more": ">", "atleast": ">=", " atleast": ">=",
}

NUMBER_RE = re.compile(r"(\d+(?:[.,]\d+)?)")

#: Phrases that mean "this product costs nothing, permanently".
STRONG_FREE_RE = re.compile(
    r"\b(free forever|permanently free|genuinely free|100% free|free to use|"
    r"free with no|free website|free websites|free tool|free tools|"
    r"free alternative|free alternatives|free resource|free resources|free utilities|"
    r"completely free|no strings)\b",
    re.IGNORECASE,
)


# --------------------------------------------------------------------------
# Vocabulary built from the database (brands, categories, countries)
# --------------------------------------------------------------------------
@dataclass
class Vocabulary:
    brands: dict[str, str] = field(default_factory=dict)      # token -> brand slug
    brand_aliases: dict[str, str] = field(default_factory=dict)
    categories: dict[str, str] = field(default_factory=dict)  # token -> category slug
    category_aliases: dict[str, str] = field(default_factory=dict)
    countries: dict[str, str] = field(default_factory=dict)
    brand_phrases: dict[str, str] = field(default_factory=dict)
    category_phrases: dict[str, str] = field(default_factory=dict)
    brand_names: dict[str, str] = field(default_factory=dict)
    category_names: dict[str, str] = field(default_factory=dict)
    all_terms: list[str] = field(default_factory=list)

    def lookup(self, token: str) -> tuple[str | None, str | None]:
        """Return (kind, slug) for a known taxonomy token.

        Categories are checked first: they are a small controlled vocabulary,
        while brand aliases are noisy ("proton vpn" must not make every query
        containing "vpn" resolve to the Proton brand).
        """
        token = token.strip().lower()
        if token in self.categories:
            return "category", self.categories[token]
        if token in self.category_aliases:
            return "category", self.category_aliases[token]
        if token in self.brands:
            return "brand", self.brands[token]
        if token in self.brand_aliases:
            return "brand", self.brand_aliases[token]
        if token in self.countries:
            return "country", self.countries[token]
        return None, None

    def lookup_phrase(self, phrase: str) -> tuple[str | None, str | None]:
        phrase = " ".join(phrase.lower().split())
        if phrase in self.brand_phrases:
            return "brand", self.brand_phrases[phrase]
        if phrase in self.category_phrases:
            return "category", self.category_phrases[phrase]
        return None, None


#: Tokens too generic to be useful as a category/brand alias on their own.
GENERIC_TAXONOMY_TOKENS = {
    "free", "tools", "tool", "app", "apps", "online", "utilities", "utility",
    "websites", "website", "services", "service", "software", "digital", "and",
    "the", "more", "other", "misc", "general",
}


def _slug_tokens(value: str) -> list[str]:
    return [t for t in re.split(r"[^a-z0-9]+", value.lower()) if t]


def _alias_tokens(value: str) -> tuple[list[str], list[str]]:
    """Split an alias into (single-word tokens, multi-word phrases).

    Multi-word aliases are kept whole: registering "proton vpn" as the token
    "vpn" would hijack every generic VPN query.
    """
    text = re.sub(r"\s+", " ", str(value).strip().lower())
    if not text:
        return [], []
    tokens = [t for t in re.split(r"[^a-z0-9]+", text) if t]
    if len(tokens) > 1:
        return [], [" ".join(tokens)]
    return tokens, []


def load_vocabulary(session: Session) -> Vocabulary:
    vocab = Vocabulary()

    for brand in session.execute(select(Brand)).scalars():
        vocab.brand_names[brand.slug] = brand.name
        for token in _slug_tokens(brand.name):
            vocab.brands.setdefault(token, brand.slug)
        for alias in brand.aliases or []:
            tokens, phrases = _alias_tokens(str(alias))
            for token in tokens:
                vocab.brand_aliases.setdefault(token, brand.slug)
            for phrase in phrases:
                vocab.brand_phrases.setdefault(phrase, brand.slug)
        if brand.domain:
            base = brand.domain.split("/")[0].split(".")[0]
            if base and base not in ("www",):
                vocab.brand_aliases.setdefault(base, brand.slug)

    for category in session.execute(select(Category)).scalars():
        vocab.category_names[category.slug] = category.name
        for token in _slug_tokens(category.name):
            if token in GENERIC_TAXONOMY_TOKENS:
                continue
            vocab.categories.setdefault(token, category.slug)
        for alias in (category.aliases or []) + (category.keywords or []):
            tokens, phrases = _alias_tokens(str(alias))
            for token in tokens:
                if token in GENERIC_TAXONOMY_TOKENS:
                    continue
                vocab.category_aliases.setdefault(token, category.slug)
            for phrase in phrases:
                vocab.category_phrases.setdefault(phrase, category.slug)
        tokens, phrases = _alias_tokens(category.slug)
        for token in tokens:
            if token in GENERIC_TAXONOMY_TOKENS:
                continue
            vocab.category_aliases.setdefault(token, category.slug)

    for country in session.execute(select(Country)).scalars():
        for token in _slug_tokens(country.name):
            vocab.countries.setdefault(token, country.code)
    vocab.countries.update(COUNTRY_ALIASES)

    vocab.all_terms = sorted(
        set(vocab.brands)
        | set(vocab.brand_aliases)
        | set(vocab.brand_phrases)
        | set(vocab.categories)
        | set(vocab.category_aliases)
        | set(vocab.category_phrases)
        | set(vocab.countries),
        key=len,
        reverse=True,
    )
    return vocab


_CACHED_VOCABULARY: Vocabulary | None = None


def get_vocabulary(session: Session) -> Vocabulary:
    """Cached taxonomy vocabulary. Invalidated whenever categories/brands change."""
    global _CACHED_VOCABULARY
    if _CACHED_VOCABULARY is None:
        _CACHED_VOCABULARY = load_vocabulary(session)
    return _CACHED_VOCABULARY


def invalidate_vocabulary_cache() -> None:
    global _CACHED_VOCABULARY
    _CACHED_VOCABULARY = None


# --------------------------------------------------------------------------
# Intent parsing
# --------------------------------------------------------------------------
def normalise(query: str) -> str:
    text = (query or "").strip().lower()
    text = text.replace("’", "'").replace("–", "-").replace("—", "-")
    text = re.sub(r"[^\w\s₹$€£¥%/\-\+']", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _expand_synonyms(tokens: Sequence[str]) -> list[str]:
    expanded = list(tokens)
    for token in tokens:
        for key, values in TOPIC_SYNONYMS.items():
            if token == key or token in values:
                expanded.extend(values)
    seen: set[str] = set()
    result: list[str] = []
    for token in expanded:
        if token not in seen and len(token) > 1:
            seen.add(token)
            result.append(token)
    return result[:12]


def parse_intent(raw: str, vocab: Vocabulary | None = None) -> ParsedIntent:
    """Translate a raw search string into structured filters + keywords."""
    vocab = vocab or Vocabulary()
    normalised = normalise(raw)
    low = normalised
    intent = ParsedIntent(
        raw=raw,
        normalised=normalised,
        intent="mixed" if normalised else "browse",
        explanation="Keyword search across every active offer.",
    )
    if not normalised:
        intent.intent = "browse"
        return intent

    reasons: list[str] = []
    remaining = low

    # ---------------------------------------------------------- free phrases
    for phrase, kind in FREE_PHRASES.items():
        if phrase in low:
            if kind == "no_card":
                intent.requires_payment_method = False
                reasons.append("no payment method required")
            if kind == "forever":
                reasons.append("long-running free offer")
            remaining = remaining.replace(phrase, " ")

    # -------------------------------------------------------------- duration
    duration_match = re.search(
        r"(\d+)\s*(day|days|week|weeks|month|months|year|years|hour|hours)", low
    )
    if duration_match:
        amount = int(duration_match.group(1))
        unit = duration_match.group(2)
        multiplier = {"hour": 1 / 24, "hours": 1 / 24, "day": 1, "days": 1,
                      "week": 7, "weeks": 7, "month": 30, "months": 30,
                      "year": 365, "years": 365}[unit]
        days = max(1, int(round(amount * multiplier)))
        if any(w in low for w in ("free", "trial", "for", "get")) or unit.startswith(("day", "week", "month", "year")):
            intent.min_trial_days = days
            reasons.append(f"at least {days} days")
            remaining = remaining.replace(duration_match.group(0), " ")
    else:
        bare = re.search(r"\b(today|tomorrow|this week|right now|currently)\b", low)
        if bare:
            reasons.append("fresh offers only")

    # ----------------------------------------------------------------- price
    price_match = re.search(
        r"(?:under|below|less than|upto|up to|max|over|above)\s*"
        r"(?:rs\.?|inr|₹|\$|usd|eur|€|gbp|£)?\s*([\d.,]+)\s*(k|m)?",
        low,
    )
    if price_match:
        raw_amount = float(price_match.group(1).replace(",", ""))
        suffix = (price_match.group(2) or "").lower()
        if suffix == "k":
            raw_amount *= 1000
        elif suffix == "m":
            raw_amount *= 1_000_000
        is_over = any(w in low[: price_match.start()] for w in ("over", "above", "more than"))
        if is_over:
            intent.min_price = raw_amount
        else:
            intent.max_price = raw_amount
        remaining = remaining.replace(price_match.group(0), " ")
        reasons.append(f"{'over' if is_over else 'under'} {raw_amount:g}")

    bare_amount = re.search(r"(?<![\w.])([\d]{1,3})\s*(?:usd|inr|eur|gbp|dollars|rupees)\b", low)
    if bare_amount and not price_match:
        intent.max_price = float(bare_amount.group(1))
        remaining = remaining.replace(bare_amount.group(0), " ")

    # ------------------------------------------------------------ offer type
    # Only *unambiguous* phrases constrain the type.  A bare "free" is far too
    # weak: most real results are trials, credits or discounts that merely
    # include something free, so it stays a keyword instead of a hard filter.
    type_map: dict[str, OfferType] = {
        "trial": OfferType.FREE_TRIAL, "trials": OfferType.FREE_TRIAL,
        "freemium": OfferType.FREEMIUM, "preview": OfferType.FREEMIUM,
        "credit": OfferType.FREE_CREDITS, "credits": OfferType.FREE_CREDITS,
        "allowance": OfferType.FREE_CREDITS, "quota": OfferType.FREE_CREDITS,
        "discount": OfferType.DISCOUNT, "discounts": OfferType.DISCOUNT,
        "off": OfferType.DISCOUNT, "sale": OfferType.DISCOUNT,
        "coupon": OfferType.COUPON, "coupons": OfferType.COUPON,
        "code": OfferType.COUPON, "codes": OfferType.COUPON, "voucher": OfferType.COUPON,
        "promo": OfferType.DISCOUNT,
        "cashback": OfferType.CASHBACK,
        "alternative": OfferType.FREE_ALTERNATIVE, "alternatives": OfferType.FREE_ALTERNATIVE,
        "opensource": OfferType.FREE_ALTERNATIVE,
    }
    tokens = normalise(remaining).split()
    matched_types: list[OfferType] = []
    saw_free = False
    for token in tokens:
        if token in ("free", "freebie", "gratis"):
            saw_free = True
            continue
        offer_type = type_map.get(token)
        if offer_type and offer_type not in matched_types:
            matched_types.append(offer_type)
    if saw_free and STRONG_FREE_RE.search(low):
        matched_types.insert(0, OfferType.FREE)
    if intent.min_trial_days and OfferType.FREE in matched_types:
        # "30 days free" describes a trial, not a permanently free product.
        matched_types = [t for t in matched_types if t is not OfferType.FREE] or [OfferType.FREE_TRIAL]
    if matched_types:
        intent.offer_types = matched_types
        reasons.append("/".join(t.value.replace("_", " ") for t in intent.offer_types))

    # ------------------------------------------------- taxonomy: brand/category
    brands: list[str] = []
    categories: list[str] = []
    countries: list[str] = []
    keywords: list[str] = []

    # multi-word taxonomy phrases first (e.g. "cloud hosting", "youtube premium")
    phrase_matched: set[str] = set()
    for phrase in sorted(_multiword_phrases(low), key=len, reverse=True):
        kind, slug = vocab.lookup_phrase(phrase)
        if kind == "brand" and slug not in brands:
            brands.append(slug)
        elif kind == "category" and slug not in categories:
            categories.append(slug)
        if kind is not None:
            phrase_matched.update(phrase.split())

    for token in tokens:
        if token in phrase_matched:
            continue
        # Words like "free" or "trial" describe the offer *type*, not a
        # category — mapping them onto the taxonomy would send every generic
        # query to the "Free Websites & Utilities" bucket.
        if token in TYPE_WORDS or token in STOPWORDS or token in DURATION_WORDS:
            continue
        kind, slug = vocab.lookup(token)
        if kind == "brand" and slug not in brands:
            brands.append(slug)
        elif kind == "category" and slug not in categories:
            categories.append(slug)
        elif kind == "country" and slug not in countries:
            countries.append(slug)

    # brand-first wording: "chatgpt plus free" -> brand token may be compounded
    intent.brand_slugs = brands[:4]
    intent.category_slugs = categories[:4]
    intent.country_codes = countries[:3]

    # ------------------------------------------------------------- keywords
    for token in tokens:
        clean = token.strip("-")
        if len(clean) < 2:
            continue
        if clean in STOPWORDS or clean in TYPE_WORDS or clean in DURATION_WORDS:
            continue
        if clean.isdigit():
            continue
        if clean in vocab.countries:
            continue
        if clean in vocab.brands or clean in vocab.brand_aliases:
            continue
        if clean in vocab.categories or clean in vocab.category_aliases:
            continue
        keywords.append(clean)
    intent.keywords = keywords[:6]

    # -------------------------------------------------------------- intent label
    if len(intent.offer_types) == 1 and not intent.keywords and not categories:
        intent.intent = "offer_type"
    elif intent.min_trial_days is not None and not intent.keywords:
        intent.intent = "duration"
    elif intent.max_price is not None and not intent.keywords:
        intent.intent = "price"
    elif brands and not keywords:
        intent.intent = "brand"
    elif categories and not keywords:
        intent.intent = "category"
    elif normalised:
        intent.intent = "mixed"

    intent.explanation = "Interpreting: " + ", ".join(reasons) if reasons else intent.explanation
    return intent


def _multiword_phrases(text: str) -> list[str]:
    found: list[str] = []
    for size in (4, 3, 2):
        words = text.split()
        for i in range(len(words) - size + 1):
            found.append(" ".join(words[i : i + size]))
    return found


# --------------------------------------------------------------------------
# Typo tolerance / did-you-mean
# --------------------------------------------------------------------------
def correct_token(token: str, vocab: Vocabulary) -> str | None:
    if len(token) < 3:
        return None
    # Short tokens need a lower similarity bar: "vpm" vs "vpn" is only a 2/3
    # character match, which any high cutoff would reject.
    cutoff = {6: 0.82, 5: 0.78, 4: 0.72, 3: 0.65}.get(len(token), 0.68)
    candidates = [t for t in vocab.all_terms if " " not in t and abs(len(t) - len(token)) <= 2]
    if not candidates:
        return None
    best, best_key = None, (0.0, 0)
    for candidate in candidates:
        ratio = difflib.SequenceMatcher(None, token, candidate).ratio()
        prefix = 0
        for a, b in zip(token, candidate):
            if a != b:
                break
            prefix += 1
        key = (round(ratio, 4), prefix)
        if key > best_key:
            best, best_key = candidate, key
    return best if best_key[0] >= cutoff else None


def correct_generic_token(token: str) -> str | None:
    """Fix typos in everyday commerce words ("dealz" -> "deals")."""
    pool = GENERIC_QUERY_WORDS
    cutoff = 0.75 if len(token) >= 5 else 0.66
    best, best_key = None, (0.0, 0)
    for candidate in pool:
        if abs(len(candidate) - len(token)) > 2:
            continue
        ratio = difflib.SequenceMatcher(None, token, candidate).ratio()
        prefix = 0
        for a, b in zip(token, candidate):
            if a != b:
                break
            prefix += 1
        key = (round(ratio, 4), prefix)
        if key > best_key:
            best, best_key = candidate, key
    return best if best_key[0] >= cutoff else None


GENERIC_QUERY_WORDS = sorted(
    STOPWORDS | TYPE_WORDS | {"deals", "deal", "sale", "offer", "offers", "tools", "tool"}
)


def did_you_mean(query: str, vocab: Vocabulary) -> str | None:
    tokens = normalise(query).split()
    if not tokens:
        return None
    corrected: list[str] = []
    changed = False
    for token in tokens:
        if token in STOPWORDS or token in TYPE_WORDS:
            corrected.append(token)
            continue
        if any(token in term for term in vocab.all_terms):
            corrected.append(token)
            continue
        suggestion = correct_token(token, vocab) or correct_generic_token(token)
        if suggestion:
            corrected.append(suggestion)
            changed = True
        else:
            corrected.append(token)
    return " ".join(corrected) if changed else None


# --------------------------------------------------------------------------
# Relevance SQL
# --------------------------------------------------------------------------
def _like(term: str) -> str:
    escaped = term.replace("%", r"\%").replace("_", r"\_")
    return f"%{escaped}%"


def _match(column: Any, term: str, weight: float) -> Any:
    return case(
        (func.lower(column).like(_like(term), escape="\\"), literal(weight)),
        else_=literal(0.0),
    )


def build_relevance(
    tokens: Sequence[str],
    *,
    required: Sequence[str] | None = None,
) -> tuple[Any, list[str]]:
    """Return (scored expression, required tokens).

    `required` tokens must match somewhere for a row to be returned.  By default
    they are derived from `tokens`, but callers pass an explicit set so that
    expansion terms (synonyms, resolved category names) boost ranking without
    becoming mandatory.
    """
    if required is None:
        meaningful = [
            t for t in tokens
            if t not in STOPWORDS and t not in TYPE_WORDS and t not in DURATION_WORDS
            and not t.isdigit() and t not in COUNTRY_ALIASES
        ]
        required = meaningful or [t for t in tokens if t not in STOPWORDS] or list(tokens)
    else:
        required = [t for t in required if t]

    score_parts: list[Any] = []
    for token in tokens:
        if len(token) < 2:
            continue
        score_parts.append(
            _match(Offer.title, token, 14.0)
            + _match(Offer.short_description, token, 6.0)
            + _match(Offer.subtitle, token, 4.0)
            + _match(Offer.description, token, 1.5)
            + _match(func.coalesce(cast(Offer.tags, Text), literal("")), token, 3.0)
            + _match(Offer.coupon_code, token, 5.0)
            + _match(func.coalesce(Brand.name, literal("")), token, 9.0)
            + _match(func.coalesce(Brand.domain, literal("")), token, 7.0)
            + _match(func.coalesce(Category.name, literal("")), token, 6.0)
            + _match(func.coalesce(cast(Category.keywords, Text), literal("")), token, 4.0)
            + _match(func.coalesce(cast(Category.aliases, Text), literal("")), token, 3.0)
        )
    if not score_parts:
        return literal(0.0), []

    total = score_parts[0]
    for part in score_parts[1:]:
        total = total + part

    # exact title match wins outright
    for token in list(required)[:3]:
        total = total + case(
            (func.lower(Offer.title) == token, literal(40.0)),
            (func.lower(func.coalesce(Brand.name, literal(""))) == token, literal(30.0)),
            else_=literal(0.0),
        )

    # quality + freshness boosts
    total = (
        total
        + case((Offer.verification_status == "verified", literal(6.0)), else_=literal(0.0))
        + case((Offer.is_featured.is_(True), literal(4.0)), else_=literal(0.0))
        + case((Offer.is_handpicked.is_(True), literal(4.0)), else_=literal(0.0))
        + (Offer.popularity_score / 400.0)
        + (func.coalesce(Offer.savings_percent, 0) / 40.0)
        + (Offer.quality_score / 200.0)
    )
    return total, required


def apply_relevance_filter(stmt: Select, score: Any, required: Sequence[str]) -> Select:
    if not required:
        return stmt
    required_score = literal(0.0)
    for token in required:
        required_score = required_score + (
            _match(Offer.title, token, 1.0)
            + _match(func.coalesce(Brand.name, literal("")), token, 1.0)
            + _match(func.coalesce(Brand.domain, literal("")), token, 1.0)
            + _match(func.coalesce(Category.name, literal("")), token, 1.0)
            + _match(func.coalesce(cast(Category.keywords, Text), literal("")), token, 1.0)
            + _match(func.coalesce(cast(Category.aliases, Text), literal("")), token, 1.0)
            + _match(Offer.short_description, token, 1.0)
            + _match(Offer.subtitle, token, 1.0)
            + _match(func.coalesce(cast(Offer.tags, Text), literal("")), token, 1.0)
            + _match(Offer.coupon_code, token, 1.0)
            + _match(Offer.description, token, 0.5)
        )
    return stmt.where(required_score > 0)


def intent_filters(intent: ParsedIntent) -> dict[str, Any]:
    """Structured filters extracted from an intent."""
    return {
        "category": intent.category_slugs,
        "brand": intent.brand_slugs,
        "type": intent.offer_types,
        "country": intent.country_codes,
        "max_price": intent.max_price,
        "min_trial_days": intent.min_trial_days,
        "requires_payment_method": intent.requires_payment_method,
        "expires_before": intent.ending_within_days,
    }


def merge_intent_into_filters(filters: Any, intent: ParsedIntent) -> Any:
    """Fold parsed intent into user-supplied filters (explicit filters win)."""
    if intent.category_slugs and not filters.category:
        filters.category = intent.category_slugs
    if intent.brand_slugs and not filters.brand:
        filters.brand = intent.brand_slugs
    if intent.offer_types and not filters.type:
        filters.type = intent.offer_types
    if intent.country_codes and not filters.country:
        filters.country = intent.country_codes
    if intent.max_price is not None and filters.max_price is None:
        filters.max_price = intent.max_price
    if intent.min_trial_days is not None and filters.min_trial_days is None:
        filters.min_trial_days = intent.min_trial_days
    if intent.requires_payment_method is not None and filters.requires_payment_method is None:
        filters.requires_payment_method = intent.requires_payment_method
    return filters


# --------------------------------------------------------------------------
# Suggestions
# --------------------------------------------------------------------------
def suggest(session: Session, raw: str, limit: int = 8) -> list[SearchSuggestion]:
    query = normalise(raw)
    if len(query) < 1:
        return []
    vocab = get_vocabulary(session)
    out: list[SearchSuggestion] = []
    like = _like(query)

    brands = (
        session.execute(
            select(Brand)
            .where(func.lower(Brand.name).like(like, escape="\\"))
            .limit(limit)
        )
        .scalars()
        .all()
    )
    for brand in brands:
        out.append(
            SearchSuggestion(
                type="brand",
                id=brand.id,
                label=brand.name,
                sublabel=brand.domain,
                slug=brand.slug,
                logo_url=brand.logo_url,
                score=1.0 - abs(len(brand.name) - len(query)) / max(len(brand.name), 1),
            )
        )

    cats = (
        session.execute(
            select(Category)
            .where(func.lower(Category.name).like(like, escape="\\"))
            .limit(limit)
        )
        .scalars()
        .all()
    )
    for category in cats:
        out.append(
            SearchSuggestion(
                type="category",
                id=category.id,
                label=category.name,
                sublabel=category.tagline,
                slug=category.slug,
                icon=category.icon,
                score=0.8,
            )
        )

    if len(out) < limit:
        offers = (
                session.execute(
                    select(Offer)
                    .options(selectinload(Offer.brand), selectinload(Offer.category))
                    .where(func.lower(Offer.title).like(like, escape="\\"))
                    .order_by(Offer.popularity_score.desc())
                    .limit(limit * 2)
                )
                .scalars()
                .unique()
                .all()
            )
        for offer in offers:
            if len(out) >= limit:
                break
            out.append(
                SearchSuggestion(
                    type="offer",
                    id=offer.id,
                    label=offer.title,
                    sublabel=offer.brand.name if offer.brand else None,
                    slug=offer.slug,
                    logo_url=offer.image_url,
                    offer_type=OfferType(offer.offer_type)
                    if offer.offer_type in OfferType._value2member_map_
                    else None,
                    score=offer.popularity_score / 100.0,
                )
            )

    out.sort(key=lambda s: s.score, reverse=True)

    # Offer a refined query built from the parsed intent.
    if query and len(out) < limit:
        intent = parse_intent(raw, vocab)
        if intent.offer_types or intent.min_trial_days or intent.category_slugs:
            label_parts = ["free" if OfferType.FREE in intent.offer_types else ""]
            label_parts = [p for p in label_parts if p]
            if intent.min_trial_days:
                label_parts.append(f"{intent.min_trial_days} days")
            label_parts.extend(intent.keywords[:2])
            refined = " ".join(label_parts).strip()
            if refined and refined != query:
                out.append(
                    SearchSuggestion(type="query", id="intent", label=refined, sublabel="Suggested search")
                )
    return out[:limit]


def record_search(
    session: Session,
    *,
    query: str,
    intent: ParsedIntent,
    result_count: int,
    took_ms: float,
    user_id: str | None = None,
    country_code: str | None = None,
    filters: dict[str, Any] | None = None,
) -> None:
    from app.models.analytics import SearchQueryLog

    session.add(
        SearchQueryLog(
            query=query[:300],
            normalised_query=intent.normalised[:300],
            intent=intent.intent,
            filters=filters or {},
            result_count=result_count,
            took_ms=took_ms,
            zero_results=result_count == 0,
            user_id=user_id,
            country_code=country_code,
        )
    )


def stopwatch() -> float:
    return time.perf_counter()


ELIGIBILITY_LABELS: dict[str, str] = {
    EligibilityType.NEW_USERS.value: "New users only",
    EligibilityType.COUNTRIES.value: "Limited countries",
    EligibilityType.GLOBAL.value: "Available worldwide",
    EligibilityType.STUDENTS.value: "Students only",
    EligibilityType.AGE_18_PLUS.value: "18+ only",
    EligibilityType.BUSINESS_EMAIL.value: "Business email required",
    EligibilityType.INVITE_ONLY.value: "Invite only",
    EligibilityType.EXISTING_CUSTOMERS.value: "Existing customers",
    EligibilityType.ANNUAL_BILLING.value: "Annual billing required",
    EligibilityType.PAYMENT_METHOD.value: "Payment method required",
    EligibilityType.PHONE_VERIFIED.value: "Phone verification required",
    EligibilityType.IDENTITY_VERIFIED.value: "ID verification required",
}


def eligibility_labels(types: Iterable[str] | None) -> list[str]:
    return [ELIGIBILITY_LABELS.get(t, t.replace("_", " ").title()) for t in (types or [])]