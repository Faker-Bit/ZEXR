"""Tiny synchronous bridge around the async cache used by read-only routes.

FastAPI runs `def` (non-async) endpoints in a threadpool, so we cannot await the
async cache.  Running a one-shot loop is cheap and keeps the hot read path free
of `await` plumbing.  Any failure is swallowed: caching is never load bearing.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from app.core.cache import cache


def _run(coro: Any) -> Any:
    try:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()
    except Exception:
        return None


def _sync_cache_get(key: str) -> Any | None:
    raw = _run(cache._get(key))
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return None


def _sync_cache_put(key: str, value: Any, ttl: int = 120) -> None:
    try:
        _run(cache.set_json(key, value, ttl))
    except Exception:
        pass


def cache_get(key: str) -> Any | None:
    return _sync_cache_get(key)


def cache_put(key: str, value: Any, ttl: int = 120) -> None:
    _sync_cache_put(key, value, ttl)


def cache_drop(namespace: str) -> None:
    try:
        _run(cache.clear_namespace(namespace))
    except Exception:
        pass