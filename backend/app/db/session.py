"""Database engine / session management."""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from typing import Any

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger("db")

_engine_kwargs: dict[str, Any] = {
    "echo": settings.db_echo,
    "future": True,
    "pool_pre_ping": True,
}

if settings.is_sqlite:
    # SQLite (dev only) - check_same_thread off so FastAPI's threadpool works.
    connect_args = {"check_same_thread": False}
    engine = create_engine(
        settings.database_url,
        connect_args=connect_args,
        **({"echo": settings.db_echo} | {}),
    )

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_connection, _record):  # type: ignore[no-untyped-def]
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

else:  # pragma: no cover - exercised in production environments
    engine = create_engine(
        settings.database_url,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_recycle=1800,
        pool_pre_ping=True,
        echo=settings.db_echo,
        future=True,
    )


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_engine() -> Engine:
    return engine


@contextlib.contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional scope for scripts, workers and tests."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db() -> Iterator[Session]:
    """FastAPI dependency."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()