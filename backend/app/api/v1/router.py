"""API v1 router aggregation."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import (
    admin,
    auth,
    health,
    interactions,
    offers,
    search,
    taxonomy,
    users,
)

api_router = APIRouter()

api_router.include_router(health.router)
api_router.include_router(offers.router)
api_router.include_router(taxonomy.router)
api_router.include_router(search.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(interactions.router)
api_router.include_router(admin.router)

__all__ = ["api_router"]