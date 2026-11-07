"""Aggregate API router. Everything lives under ``/api``."""

from __future__ import annotations

from fastapi import APIRouter

from app.api import health, orders

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(orders.router)

__all__ = ["api_router"]
