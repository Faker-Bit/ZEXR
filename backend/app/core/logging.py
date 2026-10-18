"""Structured logging setup."""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog

from app.core.config import settings


def _force_utf8(stream: Any) -> Any:
    """Make a text stream UTF-8 so logging cannot depend on the console codepage.

    On Windows a redirected stream inherits the ANSI codepage (cp1252 here).
    Any log line containing a character outside it - a rupee sign, an em dash,
    a box-drawing glyph - raises UnicodeEncodeError, and because structlog
    writes straight to stdout that exception propagates out of whatever was
    logging. That is how a scheduled APScheduler job taking an exception took
    the whole API down: log.exception() itself blew up mid-write.

    The stream may already be wrapped (colorama installs an AnsiToWin32 proxy
    on Windows), and reconfiguring the wrapper is a no-op or an error, so the
    whole chain is walked down to the real TextIOWrapper.

    ``errors="backslashreplace"`` keeps output lossy-but-safe rather than
    raising if a byte sequence is somehow still unencodable.
    """
    seen = 0
    current = stream
    while current is not None and seen < 8:
        try:
            current.reconfigure(encoding="utf-8", errors="backslashreplace")
        except (AttributeError, ValueError, OSError):
            # Not a reconfigurable TextIOBase: either a plain proxy such as
            # colorama's AnsiToWin32, or a closed stream. Keep descending.
            pass
        else:
            # Reconfigured the real stream; nothing further to do.
            return stream
        current = getattr(current, "__wrapped__", None)
        seen += 1
    return stream


def configure_logging() -> None:
    level = logging.DEBUG if settings.debug else logging.INFO

    _force_utf8(sys.stdout)
    _force_utf8(sys.stderr)

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=level,
        force=True,
    )
    for noisy in ("uvicorn.access", "httpx", "httpcore", "celery.utils.functional"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
    ]
    if settings.is_production:
        processors.append(structlog.processors.format_exc_info)
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=True))

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(file=_force_utf8(sys.stdout)),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> Any:
    return structlog.get_logger(name)


configure_logging()
log = get_logger("zexrdealhub")