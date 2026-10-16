"""RSS / Atom feed adapter.

Handles syndication feeds that publishers use to announce promotions.  Only
entries that link to a specific offer page are returned; generic blog posts are
left to the normaliser (which will usually reject them).
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import urljoin

from app.discovery.adapters.base import AdapterContext, AdapterOutcome, SourceAdapter
from app.discovery.base import FetchResult, fetcher
from app.schemas.offer import DiscoveredItem

TAG_RE = re.compile(r"<[^>]+>")
OFFER_HINT_RE = re.compile(
    r"\b(free|trial|discount|off|save|credit|deal|promo|coupon|voucher|cashback|offer)\b",
    re.IGNORECASE,
)


def strip_html(value: str | None) -> str:
    if not value:
        return ""
    text = TAG_RE.sub(" ", value)
    text = (
        text.replace("&nbsp;", " ")
        .replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&#39;", "'")
    )
    return re.sub(r"\s+", " ", text).strip()


class RSSAdapter(SourceAdapter):
    name = "rss"

    def fetch(self, ctx: AdapterContext) -> FetchResult:
        feed_url = ctx.option("feed_url") or ctx.source.feed_url or ctx.source.homepage_url
        return fetcher.fetch(
            feed_url,
            source_key=ctx.source.key,
            respect_robots=ctx.source.respect_robots,
            min_interval=ctx.source.min_request_interval_seconds,
            per_hour=ctx.source.rate_limit_per_hour,
            accept="application/rss+xml, application/atom+xml, application/xml;q=0.9, text/xml;q=0.9, */*;q=0.5",
        )

    def parse(self, ctx: AdapterContext) -> AdapterOutcome:
        outcome = AdapterOutcome()
        payload = ctx.payload
        if payload is None or not payload.text:
            outcome.warnings.append("empty feed body")
            return outcome

        try:
            import feedparser

            parsed = feedparser.parse(payload.text)
            entries: list[dict[str, Any]] = list(parsed.entries)
            if not entries:
                outcome.warnings.append("feed contained no entries")
                return outcome
        except Exception:
            entries = _fallback_parse(payload.text)

        limit = int(ctx.option("max_items", ctx.source.max_items) or 50)
        for entry in entries:
            outcome.total_seen += 1
            if len(outcome.items) >= limit:
                break
            link = entry.get("link") or entry.get("id") or ""
            if not link:
                continue
            link = urljoin(payload.url or ctx.source.homepage_url, link)
            title = strip_html(entry.get("title")) or ""
            summary = strip_html(
                entry.get("summary") or entry.get("description") or entry.get("content", [{}])[0].get("value", "")
                if entry.get("content")
                else entry.get("summary") or entry.get("description")
            )
            if not title or not OFFER_HINT_RE.search(f"{title} {summary}"):
                outcome.warnings.append(f"skipped non-offer entry: {title[:60]!r}")
                continue

            outcome.items.append(
                DiscoveredItem(
                    external_id=entry.get("id") or entry.get("guid") or link,
                    title=title[:240],
                    description=summary[:2000] or None,
                    url=link[:700],
                    published_at=_parse_date(entry.get("published") or entry.get("updated")),
                    raw={
                        "author": entry.get("author"),
                        "tags": [t.get("term") for t in entry.get("tags", []) if t.get("term")],
                        "feed_title": parsed_feed_title(payload.text),
                    },
                )
            )
        return outcome


def _fallback_parse(xml_text: str) -> list[dict[str, Any]]:
    """Minimal RSS reader for when feedparser is unavailable."""
    import xml.etree.ElementTree as ET

    entries: list[dict[str, Any]] = []
    try:
        root = ET.fromstring(xml_text.encode("utf-8", "ignore"))
    except ET.ParseError:
        return entries
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    nodes = root.findall(".//item") or root.findall(".//atom:entry", ns)
    for node in nodes:
        link_node = node.find("link")
        link = link_node.text if link_node is not None and link_node.text else ""
        if not link:
            atom_link = node.find("atom:link", ns)
            link = atom_link.get("href", "") if atom_link is not None else ""
        title_node = node.find("title")
        desc_node = node.find("description") or node.find("atom:summary", ns)
        entries.append(
            {
                "title": title_node.text if title_node is not None else "",
                "link": link,
                "summary": desc_node.text if desc_node is not None else "",
                "published": next(
                    (c.text for c in node if c.tag.endswith("pubDate") or c.tag.endswith("updated")), None
                ),
            }
        )
    return entries


def _parse_date(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None) if value.tzinfo else value
    try:
        parsed = parsedate_to_datetime(str(value))
        return parsed.replace(tzinfo=None) if parsed else None
    except (TypeError, ValueError, IndexError):
        return None


def parsed_feed_title(xml_text: str) -> str | None:
    match = re.search(r"<title[^>]*>(.*?)</title>", xml_text, re.IGNORECASE | re.DOTALL)
    return strip_html(match.group(1)) if match else None


def utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)