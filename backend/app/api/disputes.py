"""Dispute defence endpoints: list, packet, versioned drafts, approve, submit."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.models.dispute import Dispute
from app.models.order import Order
from app.schemas.actions import DraftRequest
from app.services import disputes as dispute_service

router = APIRouter(prefix="/disputes", tags=["disputes"])


def _get_dispute_or_404(session: Session, dispute_id: int) -> Dispute:
    dispute = session.get(Dispute, dispute_id)
    if dispute is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Dispute {dispute_id} not found."
        )
    return dispute


@router.get("", summary="All disputes")
def list_disputes(db: Session = Depends(get_db)) -> dict[str, object]:
    rows = list(db.scalars(select(Dispute).order_by(Dispute.id)))
    items = [dispute_service.serialise(row, db) for row in rows]
    return {"count": len(items), "items": items}


@router.get("/{dispute_id}", summary="One dispute with its drafts")
def get_dispute(dispute_id: int, db: Session = Depends(get_db)) -> dict[str, object]:
    return dispute_service.serialise(_get_dispute_or_404(db, dispute_id), db)


@router.get("/{dispute_id}/packet", summary="Evidence packet (checklist, not a prediction)")
def get_packet(dispute_id: int, db: Session = Depends(get_db)) -> dict[str, object]:
    return dispute_service.packet(db, _get_dispute_or_404(db, dispute_id))


@router.post("/{dispute_id}/drafts", status_code=status.HTTP_201_CREATED, summary="Create the next draft version")
async def create_draft(
    dispute_id: int, body: DraftRequest | None = None, db: Session = Depends(get_db)
) -> dict[str, object]:
    dispute = _get_dispute_or_404(db, dispute_id)
    draft = await dispute_service.create_draft(db, dispute, body=(body.body if body else None))
    return dispute_service.draft_payload(draft)


@router.post("/{dispute_id}/drafts/{draft_id}/approve", summary="Approve a draft")
def approve_draft(dispute_id: int, draft_id: int, db: Session = Depends(get_db)) -> dict[str, object]:
    dispute = _get_dispute_or_404(db, dispute_id)
    draft = next((d for d in dispute.drafts if d.id == draft_id), None)
    if draft is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found.")
    try:
        approved = dispute_service.approve_draft(db, draft)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    # Return the SAME shape as POST /drafts. A shorter payload here was a real
    # bug: the frontend's strict mapper rejected it and the approval silently
    # failed to refresh the card.
    return dispute_service.draft_payload(approved)


@router.post("/{dispute_id}/submit", summary="Submit the approved draft (SIMULATED unless verified)")
def submit(dispute_id: int, db: Session = Depends(get_db)) -> dict[str, object]:
    dispute = _get_dispute_or_404(db, dispute_id)
    try:
        return dispute_service.submit(db, dispute)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post(
    "/orders/{order_id}/open",
    status_code=status.HTTP_201_CREATED,
    summary="Open (or fetch) the demo dispute for an order",
)
def open_dispute(order_id: int, db: Session = Depends(get_db)) -> dict[str, object]:
    order = db.get(Order, order_id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Order {order_id} not found.")
    dispute = dispute_service.ensure_seeded(db, order)
    return dispute_service.serialise(dispute, db)
