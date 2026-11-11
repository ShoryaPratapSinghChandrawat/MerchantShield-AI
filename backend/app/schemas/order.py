"""Order API schemas."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.models.enums import SourceLabel
from app.schemas.common import MoneyStr, UtcZDatetime


class OrderRead(BaseModel):
    """An order as returned by ``GET /api/orders/{id}``."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    order_ref: str
    buyer_name: str
    buyer_email: str
    item_name: str
    amount: MoneyStr
    currency: str
    status: str

    # rule R5 - always present, never inferred by the UI
    source: SourceLabel
    is_demo: bool
    demo_run_id: str | None

    created_at: UtcZDatetime
    updated_at: UtcZDatetime


class ErrorResponse(BaseModel):
    """Uniform error body."""

    detail: str
