"""Request rate limiting.

Uses slowapi when enabled, otherwise a no-op limiter so development never
fails because of a missing Redis connection.
"""

from __future__ import annotations

from typing import Any

from fastapi import Request

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger("ratelimit")

try:  # pragma: no cover - optional dependency path
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    from slowapi.middleware import SlowAPIMiddleware
    from slowapi.util import get_remote_address

    _SLOWAPI = True
except Exception:  # pragma: no cover
    _SLOWAPI = False
    Limiter = None  # type: ignore[assignment]
    RateLimitExceeded = Exception  # type: ignore[assignment,misc]


def rate_key(request: Request) -> str:
    """Identify callers by user when signed in, falling back to IP."""
    try:
        user_id = getattr(request.state, "user_id", None)
        if user_id:
            return f"user:{user_id}"
    except Exception:
        pass
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return f"ip:{forwarded.split(',')[0].strip()}"
    client = request.client
    return f"ip:{client.host if client else 'unknown'}"


if _SLOWAPI:  # pragma: no branch
    limiter: Any = Limiter(
        key_func=rate_key,
        default_limits=[settings.rate_limit_default],
        enabled=settings.rate_limit_enabled,
        headers_enabled=True,
    )
    rate_limit_exceeded_handler = _rate_limit_exceeded_handler
    SlowAPIMiddleware = SlowAPIMiddleware  # type: ignore[misc]
else:  # pragma: no cover
    limiter = None

    async def rate_limit_exceeded_handler(request: Request, exc: Exception) -> Any:  # type: ignore[misc]
        from fastapi.responses import JSONResponse

        return JSONResponse({"detail": "Rate limit exceeded"}, status_code=429)

    SlowAPIMiddleware = None  # type: ignore[assignment]


def limit(limit_string: str):  # type: ignore[no-untyped-def]
    """No-op decorator when slowapi is unavailable."""
    if limiter is None:
        def _decorator(func):  # type: ignore[no-untyped-def]
            return func

        return _decorator
    return limiter.limit(limit_string)