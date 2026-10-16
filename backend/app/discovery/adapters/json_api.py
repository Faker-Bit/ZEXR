"""Generic JSON / REST feed adapter.

Configured entirely from the `config` JSON column on the source row, so adding
a new API integration requires **no code change and no migration**:

```json
{
  "url": "https://partner.example.com/v2/offers",
  "auth": {"type": "header", "name": "X-Api-Key", "prefix": ""},
  "query": {"status": "active"},
  "items_path": "data.offers",
  "fields": {
    "id": "id",
    "title": "name",
    "description": "summary",
    "url": "landing_url",
    "offer_type": "promotion.type",
    "original_price": "pricing.list_price",
    "promo_price": "pricing.sale_price",
    "currency": "pricing.currency",
    "trial_days": "promotion.trial_days",
    "expires_at": "promotion.ends_at",
    "coupon_code": "promotion.code",
    "brand_name": "merchant.name",
    "category_slug": "category.slug",
    "countries": "availability.countries"
  }
}
```

Dotted paths are supported.  A missing field yields ``None`` — the adapter never
guesses a price or a date.

Two extra formats are supported via ``"format"``:

* ``"json"`` (default) — a JSON array, or an object addressed by ``items_path``
* ``"jsonl"`` / ``"ndjson"`` — newline-delimited JSON, the format most static
  open datasets ship in (e.g. ``data/deals.jsonl`` on GitHub)
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

from app.discovery.adapters.base import AdapterContext, AdapterOutcome, SourceAdapter
from app.discovery.base import FetchResult, fetcher
from app.schemas.offer import DiscoveredItem

MAX_DESCRIPTION = 2000


def _fmt(config: dict[str, Any]) -> str:
    """Normalised payload format: ``json`` (default) or ``jsonl``."""
    value = str((config or {}).get("format", "json") or "json").strip().lower()
    return "jsonl" if value in ("jsonl", "ndjson", "jsonlines") else "json"


def dig(data: Any, path: str | str | None) -> Any:
    """Fetch `a.b.c` from nested dicts/lists. Returns None when absent."""
    if not path:
        return None
    current = data
    for part in str(path).split("."):
        if current is None:
            return None
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, list):
            try:
                current = current[int(part)]
            except (ValueError, IndexError):
                return None
        else:
            return None
    return current


def parse_number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "")
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    return float(match.group(0)) if match else None


def parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).replace(tzinfo=None) if value.tzinfo else value
    if isinstance(value, (int, float)):
        seconds = value / 1000 if value > 10_000_000_000 else value
        try:
            return datetime.fromtimestamp(seconds, tz=timezone.utc).replace(tzinfo=None)
        except (OverflowError, OSError, ValueError):
            return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        pass
    for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%d-%m-%y", "%d/%m/%y", "%B %d, %Y", "%b %d, %Y", "%d %B %Y"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    try:
        from email.utils import parsedate_to_datetime

        parsed = parsedate_to_datetime(text)
        return parsed.replace(tzinfo=None) if parsed else None
    except (TypeError, ValueError, IndexError):
        return None


def parse_jsonl(text: str) -> list[Any]:
    """Parse newline-delimited JSON, skipping blank and malformed lines.

    Static open datasets are often committed as JSONL and occasionally contain a
    stray bad line; dropping one bad row is better than losing the whole file.
    """
    rows: list[Any] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def coerce_tags(value: Any, limit: int = 10) -> list[str]:
    """Normalise a tags field.

    Sources publish tags either as a list or as a delimited string
    (``"ai,llm,api"``).  Treating a string as an iterable would yield one tag per
    character, so split on the usual delimiters instead.
    """
    if not value:
        return []
    if isinstance(value, str):
        parts = re.split(r"[,;|]", value)
    elif isinstance(value, (list, tuple, set)):
        parts = [str(v) for v in value]
    else:
        parts = [str(value)]
    out: list[str] = []
    for part in parts:
        cleaned = part.strip()[:40]
        if cleaned and cleaned not in out:
            out.append(cleaned)
        if len(out) >= limit:
            break
    return out


def matches_rules(row: Any, rules: list[dict[str, Any]]) -> bool:
    """Evaluate a list of `{"field", "op", "value"}` rules against a row (AND).

    Lets a source select a subset of a large payload — e.g. keep only the
    zero-priced models out of a full catalogue — without writing an adapter.
    Supported ops: ``equals`` (default), ``contains``, ``gt``, ``lt``, ``exists``.
    """
    for rule in rules or []:
        if not isinstance(rule, dict):
            continue
        value = dig(row, str(rule.get("field", "")))
        op = str(rule.get("op", "equals")).strip().lower()
        expected = rule.get("value")

        if op == "exists":
            if bool(value) is not bool(expected):
                return False
        elif op == "contains":
            if str(expected).lower() not in str(value or "").lower():
                return False
        elif op in ("gt", "lt"):
            left, right = parse_number(value), parse_number(expected)
            if left is None or right is None:
                return False
            if op == "gt" and not left > right:
                return False
            if op == "lt" and not left < right:
                return False
        else:
            # Compare as text, but keep 0/False meaningful: `expected or ""`
            # would silently turn an expected numeric 0 into an empty string.
            left_text = "" if value is None else str(value).strip().lower()
            right_text = "" if expected is None else str(expected).strip().lower()
            if left_text != right_text:
                return False
    return True


def render_template(template: str, row: Any) -> str | None:
    """Fill a `{field}` / `{a.b}` template from a row.

    Needed when the payload has no link field but the canonical URL is derivable
    from an id, e.g. Steam's ``https://store.steampowered.com/app/{id}``.
    """
    values: dict[str, str] = {}

    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in values:
            value = dig(row, key)
            values[key] = "" if value is None else str(value)
        return values[key]

    rendered = re.sub(r"\{([^}]+)\}", replace, template)
    return rendered if "{" not in rendered else None


def build_url(config: dict[str, Any], api_key: str | None) -> str:
    url = str(config.get("url", ""))
    query = config.get("query") or {}
    if query and url:
        from urllib.parse import urlencode

        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}{urlencode(query)}"
    if api_key and config.get("api_key_in_url"):
        from urllib.parse import quote

        url = url.replace("{api_key}", quote(api_key, safe=""))
    return url


class JsonApiAdapter(SourceAdapter):
    name = "json_api"

    def fetch(self, ctx: AdapterContext) -> FetchResult:
        config = ctx.config or {}
        url = build_url(config, ctx.api_key)
        if not url:
            return FetchResult(False, error="source config is missing 'url'")
        headers = dict(config.get("headers") or {})
        auth = config.get("auth") or {}
        if ctx.api_key and auth.get("type") == "header":
            headers[auth.get("name", "Authorization")] = f"{auth.get('prefix', '')}{ctx.api_key}".strip()
        if ctx.api_key and auth.get("type") == "bearer":
            headers["Authorization"] = f"Bearer {ctx.api_key}"

        result = fetcher.fetch(
            url,
            source_key=ctx.source.key,
            respect_robots=ctx.source.respect_robots,
            min_interval=ctx.source.min_request_interval_seconds,
            per_hour=ctx.source.rate_limit_per_hour,
            accept="application/json" if _fmt(config) == "json" else "text/plain",
        )
        if not result.ok or not result.text:
            return result

        # JSONL is handed to parse() untouched; re-encoding it as JSON would be
        # pointless work over the whole file.
        if _fmt(config) == "jsonl":
            return FetchResult(
                True,
                result.status_code,
                result.url,
                result.text,
                result.headers,
                elapsed_ms=result.elapsed_ms,
            )

        try:
            data = json.loads(result.text)
        except json.JSONDecodeError as exc:
            return FetchResult(False, result.status_code, result.url, error=f"invalid JSON: {exc}")

        return FetchResult(
            True,
            result.status_code,
            result.url,
            json.dumps(data),
            result.headers,
            elapsed_ms=result.elapsed_ms,
        )

    def parse(self, ctx: AdapterContext) -> AdapterOutcome:
        outcome = AdapterOutcome()
        payload = ctx.payload
        if payload is None:
            return outcome

        items_path = ctx.option("items_path")
        if _fmt(ctx.config or {}) == "jsonl":
            if items_path:
                outcome.warnings.append("items_path is ignored for jsonl sources")
            rows: Any = parse_jsonl(payload.text)
        else:
            try:
                data = json.loads(payload.text)
            except json.JSONDecodeError as exc:
                outcome.warnings.append(f"invalid JSON: {exc}")
                return outcome
            rows = dig(data, items_path) if items_path else data

        if isinstance(rows, dict):
            rows = [rows]
        if not isinstance(rows, list):
            outcome.warnings.append(f"items_path {items_path!r} did not resolve to a list")
            return outcome

        fields: dict[str, str] = ctx.option("fields", {}) or {}
        limit = int(ctx.option("max_items", ctx.source.max_items) or 50)
        url_field = fields.get("url", "url")
        title_field = fields.get("title", "title")
        url_template = ctx.option("url_template")
        # Some stores quote money in minor units (Steam returns cents).
        price_divisor = float(ctx.option("price_divisor", 1) or 1)
        rules = ctx.option("filter", []) or []

        def price(field: str) -> float | None:
            value = parse_number(dig(row, fields.get(field, "")))
            return round(value / price_divisor, 2) if value is not None and price_divisor else value

        for row in rows:
            outcome.total_seen += 1
            if len(outcome.items) >= limit:
                break
            if not isinstance(row, dict):
                continue
            if rules and not matches_rules(row, rules):
                outcome.filtered += 1
                continue
            url = dig(row, url_field) if url_field else None
            if not url and url_template:
                url = render_template(url_template, row)
            title = dig(row, title_field)
            if not url or not title:
                outcome.warnings.append("entry missing url or title")
                continue
            countries = dig(row, fields.get("countries", "")) or []
            if isinstance(countries, str):
                countries = [countries]
            outcome.items.append(
                DiscoveredItem(
                    external_id=str(dig(row, fields.get("id", "")) or url)[:300],
                    title=str(title)[:240],
                    description=(str(dig(row, fields.get("description", "")) or "")[:MAX_DESCRIPTION] or None),
                    url=str(url)[:700],
                    offer_type=_map_type(dig(row, fields.get("offer_type", "")))
                    or _map_type(ctx.option("offer_type", "")),
                    brand_name=dig(row, fields.get("brand_name", "")),
                    # A root-level `category_slug` is a literal; inside `fields` it
                # is a path into the row. Literals belong at the root.
                category_slug=ctx.option("category_slug") or dig(row, fields.get("category_slug", "")),
                    original_price=price("original_price"),
                    promo_price=price("promo_price"),
                    currency=str(dig(row, fields.get("currency", "")) or "USD").upper()[:3],
                    trial_days=int(parse_number(dig(row, fields.get("trial_days", ""))) or 0) or None,
                    expires_at=parse_datetime(dig(row, fields.get("expires_at", ""))),
                    coupon_code=dig(row, fields.get("coupon_code", "")),
                    country_codes=[str(c).upper()[:2] for c in countries][:50],
                    published_at=parse_datetime(dig(row, fields.get("published_at", ""))),
                    tags=coerce_tags(dig(row, fields.get("tags", ""))),
                    raw={k: v for k, v in row.items() if isinstance(v, (str, int, float, bool, type(None)))},
                )
            )
        return outcome


TYPE_ALIASES = {
    "free": "free",
    "trial": "free_trial",
    "free_trial": "free_trial",
    "freemium": "freemium",
    "credit": "free_credits",
    "credits": "free_credits",
    "discount": "discount",
    "sale": "discount",
    "coupon": "coupon",
    "promo": "coupon",
    "cashback": "cashback",
    "alternative": "free_alternative",
}


def _map_type(value: Any) -> str | None:
    if not value:
        return None
    return TYPE_ALIASES.get(str(value).strip().lower().replace(" ", "_"))