"""Aggregate API router. Everything lives under ``/api``."""

from __future__ import annotations

from fastapi import APIRouter

from app.api import actions, audit, about, demo, disputes, health, orders, store

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(orders.router)
api_router.include_router(actions.router)
api_router.include_router(audit.router)
api_router.include_router(demo.router)
api_router.include_router(store.router)
api_router.include_router(disputes.router)
api_router.include_router(about.router)

__all__ = ["api_router"]
