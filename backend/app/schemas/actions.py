"""Request schemas. Response shapes are documented dicts built by the services."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ProposeActionRequest(BaseModel):
    #: Deliberately a plain string, not a Literal. The allowlist check lives in
    #: the engine (services/actions.py) so that an unknown type produces the
    #: documented 422 with a list of what IS allowed, rather than a schema
    #: error that says nothing about the allowlist.
    type: str | None = Field(
        default=None,
        description="One of ADD_TRACKING, MESSAGE_BUYER, FLAG_FOR_REVIEW. Defaults to FLAG_FOR_REVIEW.",
    )
    payload: dict[str, Any] = Field(default_factory=dict)
    rationale: str = ""


class ReconcileRequest(BaseModel):
    """Returning an action to APPROVED requires an explicit confirmation."""

    confirm_not_applied: bool = False


class CheckoutRequest(BaseModel):
    product_id: str
    buyer_name: str = "Demo Buyer"
    buyer_email: str = "buyer@example.com"


class CaptureRequest(BaseModel):
    token: str


class DraftRequest(BaseModel):
    """``body`` omitted means "let the draft engine write it"."""

    body: str | None = None


class RejectRequest(BaseModel):
    reason: str = ""


class ErrorResponse(BaseModel):
    detail: str
