"""Health endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from app.core.config import get_settings
from app.core.timeutil import utcnow
from app.schemas.health import HealthResponse

router = APIRouter(tags=["health"])

PHASE = "7"


@router.get("/health", response_model=HealthResponse, summary="Liveness and honest mode flags")
def health() -> HealthResponse:
    """Return liveness plus the non-secret flags the UI needs.

    ``paypal_credentials_present`` is a boolean on purpose - the frontend must
    be able to say "running without PayPal credentials" without ever receiving
    the credentials themselves (rule R10).
    """
    settings = get_settings()
    return HealthResponse(
        status="ok",
        phase=PHASE,
        demo_mode=settings.demo_mode,
        paypal_mode=settings.paypal_mode,
        paypal_credentials_present=settings.has_paypal_credentials,
        llm_provider=settings.llm_provider,
        server_time=utcnow(),
    )
