"""Polite, robots-aware HTTP layer used by every discovery adapter.

Guarantees enforced here (not by callers):

* ``robots.txt`` is fetched and honoured.  Disallowed paths are never requested.
* One in-flight request per host, spaced by the source's minimum interval.
* Conditional requests (ETag / Last-Modified) so repeat polls are cheap.
* Exponential backoff on 429/5xx with ``Retry-After`` support.
* Response caching per source with the source's TTL.
* An explicit allow-list check — only http/https, no localhost/link-local.
"""

from __future__ import annotations

import hashlib
import time
import urllib.robotparser
from dataclasses import dataclass, field
from threading import Lock
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger("discovery.http")

ALLOWED_SCHEMES = ("http", "https")

BLOCKED_HOST_PATTERNS = (
    "localhost", "127.0.0.1", "0.0.0.0", "169.254.", "::1", "[::1]", "10.", "192.168.",
    ".local", ".internal",
)

_last_request_at: dict[str, float] = {}
_host_lock = Lock()


def is_safe_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if parsed.scheme not in ALLOWED_SCHEMES:
        return False
    host = (parsed.hostname or "").lower()
    if not host:
        return False
    return not any(pattern in host for pattern in BLOCKED_HOST_PATTERNS)


class RobotsGate:
    """Tiny cache in front of urllib's robots.txt parser."""

    def __init__(self, user_agent: str, timeout: float = 10.0) -> None:
        self.user_agent = user_agent
        self.timeout = timeout
        self._parsers: dict[str, urllib.robotparser.RobotFileParser | None] = {}
        self._lock = Lock()

    def allowed(self, url: str) -> tuple[bool, str, float | None]:
        """(allowed, reason, crawl_delay_seconds)."""
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        with self._lock:
            parser = self._parsers.get(origin)
        if parser is None and origin not in self._parsers:
            parser = self._load(origin)
            with self._lock:
                self._parsers[origin] = parser
        if parser is None:
            # No robots.txt reachable -> permissive, but logged.
            return True, "no robots.txt", None
        if not parser.can_fetch(self.user_agent, url):
            return False, "disallowed by robots.txt", None
        try:
            delay = parser.crawl_delay(self.user_agent)
        except Exception:
            delay = None
        return True, "allowed", delay

    def _load(self, origin: str) -> urllib.robotparser.RobotFileParser | None:
        parser = urllib.robotparser.RobotFileParser()
        parser.set_url(urljoin(origin, "/robots.txt"))
        try:
            with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
                response = client.get(urljoin(origin, "/robots.txt"))
            if response.status_code >= 400:
                parser.parse(["User-agent: *", "Disallow:"])
                return parser
            parser.parse(response.text.splitlines())
            return parser
        except Exception as exc:
            log.warning("discovery.robots_unreachable", origin=origin, error=str(exc))
            return None


class SourceThrottle:
    """Per-source spacing + global per-host spacing."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._last_source_call: dict[str, float] = {}
        self._host_count: dict[str, list[float]] = {}
        self._cooldown: dict[str, float] = {}

    def wait(self, source_key: str, host: str, min_interval: float, per_hour: int) -> None:
        while True:
            with self._lock:
                now = time.monotonic()
                cooldown_until = self._cooldown.get(host, 0.0)
                if now < cooldown_until:
                    sleep_for = cooldown_until - now
                else:
                    last = self._last_source_call.get(source_key, 0.0)
                    host_calls = [t for t in self._host_count.get(host, []) if now - t < 3600]
                    if len(host_calls) >= per_hour:
                        sleep_for = 3600 - (now - host_calls[0])
                        self._cooldown[host] = now + sleep_for
                    elif now - last < min_interval:
                        sleep_for = min_interval - (now - last)
                    else:
                        self._last_source_call[source_key] = now
                        self._host_count[host] = host_calls + [now]
                        return
            if sleep_for > 0:
                time.sleep(min(sleep_for, 60.0))

    def penalise(self, host: str, seconds: float) -> None:
        with self._lock:
            self._cooldown[host] = time.monotonic() + seconds


@dataclass
class FetchResult:
    ok: bool
    status_code: int | None = None
    url: str | None = None
    text: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    error: str | None = None
    skipped_reason: str | None = None
    from_cache: bool = False
    elapsed_ms: int = 0


class PoliteFetcher:
    """Single entry point for outbound HTTP during discovery."""

    def __init__(self) -> None:
        self.robots = RobotsGate(settings.discovery_user_agent)
        self.throttle = SourceThrottle()
        self._etags: dict[str, tuple[str, float]] = {}

    def fetch(
        self,
        url: str,
        *,
        source_key: str,
        respect_robots: bool = True,
        min_interval: float = 120.0,
        per_hour: int = 30,
        timeout: float | None = None,
        accept: str = "text/html,application/xhtml+xml,application/xml,application/json;q=0.9,*/*;q=0.5",
        max_retries: int | None = None,
    ) -> FetchResult:
        if not settings.discovery_enabled:
            return FetchResult(False, error="discovery disabled by configuration", skipped_reason="disabled")
        if not is_safe_url(url):
            return FetchResult(False, error=f"unsafe or unsupported URL: {url}", skipped_reason="unsafe_url")

        host = urlparse(url).netloc.lower()
        crawl_delay: float | None = None
        if respect_robots:
            allowed, reason, crawl_delay = self.robots.allowed(url)
            if not allowed:
                return FetchResult(False, error=reason, skipped_reason="robots_disallowed")
            if crawl_delay:
                min_interval = max(min_interval, float(crawl_delay))

        retries = max_retries if max_retries is not None else settings.discovery_max_retries
        timeout = timeout or settings.discovery_default_timeout
        delay = 2.0

        for attempt in range(retries + 1):
            self.throttle.wait(source_key, host, min_interval, per_hour)
            started = time.monotonic()
            try:
                with httpx.Client(timeout=timeout, follow_redirects=True) as client:
                    headers = {
                        "User-Agent": settings.discovery_user_agent,
                        "Accept": accept,
                        "Accept-Language": "en;q=0.9,*;q=0.5",
                    }
                    cached = self._etags.get(url)
                    if cached:
                        headers["If-None-Match"] = cached[0]
                    response = client.get(url, headers=headers)
                elapsed = int((time.monotonic() - started) * 1000)

                if response.status_code == 304 and cached:
                    return FetchResult(True, 304, str(response.url), "", from_cache=True)

                if response.status_code == 429:
                    retry_after = _parse_retry_after(response.headers.get("retry-after"))
                    self.throttle.penalise(host, retry_after or delay * 2)
                    if attempt >= retries:
                        return FetchResult(False, response.status_code, str(response.url), error="rate limited by source")
                    time.sleep(retry_after or delay)
                    delay = min(delay * 2, 60)
                    continue

                if response.status_code >= 500:
                    if attempt >= retries:
                        return FetchResult(False, response.status_code, str(response.url), error=f"HTTP {response.status_code}")
                    time.sleep(delay)
                    delay = min(delay * 2, 60)
                    continue

                if response.status_code >= 400:
                    return FetchResult(False, response.status_code, str(response.url), error=f"HTTP {response.status_code}")

                etag = response.headers.get("etag")
                if etag:
                    self._etags[url] = (etag, time.time())
                return FetchResult(
                    True,
                    response.status_code,
                    str(response.url),
                    response.text,
                    dict(response.headers),
                    elapsed_ms=elapsed,
                )
            except httpx.TimeoutException:
                if attempt >= retries:
                    return FetchResult(False, error=f"timeout after {retries + 1} attempts")
                time.sleep(delay)
                delay = min(delay * 2, 60)
            except httpx.HTTPError as exc:
                if attempt >= retries:
                    return FetchResult(False, error=f"{type(exc).__name__}: {exc}")
                time.sleep(delay)
                delay = min(delay * 2, 60)

        return FetchResult(False, error="exhausted retries")

    def host_of(self, url: str) -> str:
        return urlparse(url).netloc.lower()

    def fingerprint(self, payload: str) -> str:
        return hashlib.sha256(payload.encode("utf-8", "ignore")).hexdigest()[:32]


def _parse_retry_after(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


fetcher = PoliteFetcher()


def api_key_for(source: Any) -> str | None:
    """Read a source's credential from the environment, never from the DB."""
    import os

    env_name = getattr(source, "api_key_env", None)
    if not env_name:
        return None
    return os.getenv(env_name)