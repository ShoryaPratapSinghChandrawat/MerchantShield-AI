"""Health endpoint schema."""

from __future__ import annotations

from pydantic import BaseModel

from app.schemas.common import UtcZDatetime


class HealthResponse(BaseModel):
    """Liveness + the few non-secret facts the frontend needs to render honestly."""

    status: str
    phase: str
    demo_mode: bool
    paypal_mode: str
    paypal_credentials_present: bool
    llm_provider: str = "none"
    server_time: UtcZDatetime
