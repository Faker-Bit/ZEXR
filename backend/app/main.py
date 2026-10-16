"""ZEXR Deal Hub API entrypoint."""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging import get_logger
from app.core.ratelimit import SlowAPIMiddleware, limiter, rate_limit_exceeded_handler
from app.db.base import Base
from app.db.session import engine
from app.models import *  # noqa: F401,F403  (register all tables)

log = get_logger("api")

try:  # slowapi raises its own exception type for the handler map
    from slowapi.errors import RateLimitExceeded as RateLimitExceededAny
except Exception:  # pragma: no cover
    RateLimitExceededAny = Exception  # type: ignore[misc,assignment]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    if settings.is_sqlite:
        # Dev convenience; production runs `alembic upgrade head`.
        Base.metadata.create_all(engine)
        log.info("startup.schema_created", backend="sqlite")

    scheduler = None
    if settings.scheduler_enabled:
        from app.workers.scheduler import start_scheduler

        scheduler = start_scheduler()

    log.info(
        "startup.ready",
        environment=settings.environment,
        docs=settings.docs_url if settings.debug else "disabled",
        scheduler=bool(scheduler),
    )
    try:
        yield
    finally:
        if scheduler is not None:
            scheduler.shutdown(wait=False)
        log.info("shutdown.complete")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "API for ZEXR Deal Hub — a global platform for discovering verified free trials, "
            "discounts, free credits and free online tools."
        ),
        docs_url=settings.docs_url if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        openapi_url="/openapi.json" if settings.debug else None,
        lifespan=lifespan,
        contact={"name": "ZEXR Deal Hub", "url": settings.site_url},
        license_info={"name": "Terms of use", "url": f"{settings.site_url}/terms"},
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        # Header names are HTTP tokens and cannot contain spaces.
    expose_headers=["X-Zexr-Affiliate", "X-Request-ID"],
        max_age=3600,
    )
    app.add_middleware(GZipMiddleware, minimum_size=1024)

    if limiter is not None:
        app.state.limiter = limiter
        app.add_exception_handler(RateLimitExceededAny, rate_limit_exceeded_handler)
        if SlowAPIMiddleware is not None:
            app.add_middleware(SlowAPIMiddleware)

    @app.middleware("http")
    async def request_context(request: Request, call_next: Any) -> Any:
        request_id = request.headers.get("x-request-id") or f"{int(time.time() * 1000)}"
        started = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        if settings.debug:
            elapsed = (time.perf_counter() - started) * 1000
            response.headers["X-Response-Time-Ms"] = f"{elapsed:.1f}"
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "detail": "Validation failed",
                "errors": [
                    {
                        "field": ".".join(str(p) for p in err.get("loc", [])[1:]),
                        "message": err.get("msg"),
                        "type": err.get("type"),
                    }
                    for err in exc.errors()
                ],
            },
        )

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request: Request, exc: SQLAlchemyError) -> JSONResponse:
        log.error("api.db_error", path=request.url.path, error=str(exc))
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": "The database is temporarily unavailable. Please retry."},
        )

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception) -> JSONResponse:
        log.exception("api.unhandled_error", path=request.url.path, error=str(exc))
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Something went wrong on our side."},
        )

    app.include_router(api_router, prefix=settings.api_prefix)

    @app.get("/", include_in_schema=False)
    def root() -> dict:
        return {
            "name": settings.app_name,
            "version": settings.app_version,
            "docs": settings.docs_url,
            "api": settings.api_prefix,
        }

    return app


app = create_app()