"""Cache abstraction.

Uses Redis when configured, otherwise an in-process TTL cache so the app runs
with zero infrastructure in development.  All caching is best-effort: a cache
failure must never break a request.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from typing import Any, Callable

from pydantic_core import to_jsonable_python

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger("cache")

_PREFIX = "zexrdealhub:"


class _MemoryCache:
    def __init__(self) -> None:
        self._store: dict[str, tuple[float, str]] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> str | None:
        async with self._lock:
            item = self._store.get(key)
            if not item:
                return None
            expires_at, value = item
            if expires_at < time.time():
                self._store.pop(key, None)
                return None
            return value

    async def set(self, key: str, value: str, ttl: int) -> None:
        async with self._lock:
            if len(self._store) > 10_000:
                self._store = {
                    k: v for k, v in self._store.items() if v[0] >= time.time()
                }
            self._store[key] = (time.time() + ttl, value)

    async def delete(self, key: str) -> None:
        async with self._lock:
            self._store.pop(key, None)

    async def clear_prefix(self, prefix: str) -> None:
        async with self._lock:
            for key in [k for k in self._store if k.startswith(prefix)]:
                self._store.pop(key, None)


class Cache:
    def __init__(self) -> None:
        self._memory = _MemoryCache()
        self._redis: Any | None = None
        self._healthy = False
        if settings.cache_enabled:
            self._init_redis()

    def _init_redis(self) -> None:
        try:
            import redis.asyncio as aioredis

            client = aioredis.from_url(
                settings.redis_url, encoding="utf-8", decode_responses=True,
                socket_connect_timeout=1.5, socket_timeout=1.5,
            )
            self._redis = client
            self._healthy = True
            log.info("cache.backend", backend="redis", url=settings.redis_url.split("@")[-1])
        except Exception as exc:  # pragma: no cover
            log.warning("cache.redis_unavailable", error=str(exc))
            self._redis = None
            self._healthy = False

    @staticmethod
    def make_key(*parts: Any, namespace: str = "") -> str:
        raw = "|".join(str(p) for p in parts)
        digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:20]
        return f"{_PREFIX}{namespace}:{digest}"

    async def get_json(self, key: str) -> Any | None:
        try:
            raw = await self._get(key)
            return json.loads(raw) if raw else None
        except Exception:
            return None

    async def _get(self, key: str) -> str | None:
        if self._redis is not None and self._healthy:
            try:
                return await self._redis.get(key)
            except Exception as exc:
                log.warning("cache.get_failed", error=str(exc))
                self._healthy = False
        return await self._memory.get(key)

    async def set_json(self, key: str, value: Any, ttl: int | None = None) -> None:
        # `json.dumps(..., default=str)` silently turns Pydantic models into
        # their `repr()`. Cached payloads are then served back as strings, so a
        # warm cache returns `[<OfferCard id=... >, ...]` instead of objects —
        # which looks like working data until the client touches a field.
        # Normalising with Pydantic first converts models, datetimes, enums and
        # Decimals into JSON-native types; `default=str` stays as a last resort
        # for genuinely unknown objects.
        payload = json.dumps(
            to_jsonable_python(value, fallback=str), default=str, ensure_ascii=False
        )
        await self.set(key, payload, ttl)

    async def set(self, key: str, value: str, ttl: int | None = None) -> None:
        ttl = ttl or settings.cache_ttl_seconds
        if self._redis is not None and self._healthy:
            try:
                await self._redis.set(key, value, ex=ttl)
                return
            except Exception as exc:
                log.warning("cache.set_failed", error=str(exc))
                self._healthy = False
        await self._memory.set(key, value, ttl)

    async def delete(self, *keys: str) -> None:
        for key in keys:
            if self._redis is not None and self._healthy:
                try:
                    await self._redis.delete(key)
                except Exception:
                    self._healthy = False
            await self._memory.delete(key)

    async def clear_namespace(self, namespace: str) -> None:
        if self._redis is not None and self._healthy:
            try:
                async for key in self._redis.scan_iter(match=f"{_PREFIX}{namespace}:*"):
                    await self._redis.delete(key)
            except Exception:
                self._healthy = False
        await self._memory.clear_prefix(f"{_PREFIX}{namespace}:")

    async def cached_json(
        self, namespace: str, parts: tuple[Any, ...], producer: Callable[[], Any], ttl: int | None = None
    ) -> Any:
        key = self.make_key(*parts, namespace=namespace)
        hit = await self.get_json(key)
        if hit is not None:
            return hit
        value = producer()
        if value is not None:
            await self.set_json(key, value, ttl)
        return value

    async def close(self) -> None:
        if self._redis is not None:
            with contextlib_suppress():
                await self._redis.aclose()


class contextlib_suppress:
    def __enter__(self) -> None:
        return None

    def __exit__(self, *exc: Any) -> bool:
        return True


cache = Cache()


async def invalidate_offers_cache() -> None:
    await cache.clear_namespace("offers")
    await cache.clear_namespace("search")
    await cache.clear_namespace("stats")