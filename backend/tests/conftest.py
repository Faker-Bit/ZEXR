"""Shared pytest fixtures: an isolated database per test session."""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator

import pytest

os.environ.setdefault("ENVIRONMENT", "local")
os.environ.setdefault("DISCOVERY_ENABLED", "false")
os.environ.setdefault("SCHEDULER_ENABLED", "false")
os.environ.setdefault("CACHE_ENABLED", "false")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

# Default to a throwaway SQLite file, but let CI (or a developer with a local
# Postgres) override it. Pointing DATABASE_URL at PostgreSQL is what makes
# dialect-specific bugs visible, so the harness must not silently ignore it.
if "DATABASE_URL" not in os.environ:
    os.environ["DATABASE_URL"] = "sqlite:///./test_zexrdealhub.db"
os.environ["SECRET_KEY"] = "test-secret-key-not-used-in-production-0123456789"

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core.cache import cache  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import SessionLocal, engine, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import *  # noqa: E402,F401,F403
from app.services import search as search_service  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _database() -> Iterator[None]:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def clean_tables() -> Iterator[None]:
    """Truncate between tests so ordering never matters."""
    yield
    with engine.begin() as connection:
        for table in reversed(Base.metadata.sorted_tables):
            if table.name == "alembic_version":
                continue
            connection.exec_driver_sql(f'DELETE FROM "{table.name}"')
    search_service.invalidate_vocabulary_cache()
    cache._memory._store.clear()


@pytest.fixture()
def session() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture()
def client() -> Iterator[TestClient]:
    def override_get_db() -> Iterator[Session]:
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(scope="session")
def settings():
    return get_settings()