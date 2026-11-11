"""Order endpoints: list, detail, scan, propose, and the agent planner."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.models.order import Order
from app.schemas.actions import ProposeActionRequest
from app.services import actions as action_service
from app.services import orders as order_service

router = APIRouter(prefix="/orders", tags=["orders"])


def _get_order_or_404(session: Session, order_id: int) -> Order:
    order = session.get(Order, order_id)
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Order {order_id} not found."
        )
    return order


@router.get("", summary="All orders with their rule-based risk")
def list_orders(db: Session = Depends(get_db)) -> dict[str, object]:
    orders = list(db.scalars(select(Order).order_by(Order.id)))
    items = [order_service.summary(db, order) for order in orders]
    return {"count": len(items), "items": items}


@router.get("/{order_id}", summary="One order with risk, evidence, actions and audit")
def get_order(order_id: int, db: Session = Depends(get_db)) -> dict[str, object]:
    order = _get_order_or_404(db, order_id)
    return order_service.detail(db, order)


@router.post("/{order_id}/scan", summary="Re-run the rule scan")
def scan_order(order_id: int, db: Session = Depends(get_db)) -> dict[str, object]:
    order = _get_order_or_404(db, order_id)
    return order_service.scan(db, order)


@router.post("/{order_id}/agent", summary="Let the planner propose the next actions")
def run_agent(order_id: int, db: Session = Depends(get_db)) -> dict[str, object]:
    order = _get_order_or_404(db, order_id)
    return order_service.trigger_agent(db, order)


@router.post(
    "/{order_id}/propose-action",
    status_code=status.HTTP_201_CREATED,
    summary="Propose an action (duplicate open proposals return the existing one with 200)",
)
def propose_action(
    order_id: int,
    body: ProposeActionRequest | None = None,
    response: Response = None,  # type: ignore[assignment]
    db: Session = Depends(get_db),
) -> dict[str, object]:
    order = _get_order_or_404(db, order_id)
    request = body or ProposeActionRequest()
    action, created = action_service.propose(
        db,
        order=order,
        action_type=request.type or "FLAG_FOR_REVIEW",
        payload=request.payload,
        rationale=request.rationale,
    )
    if not created and response is not None:
        response.status_code = status.HTTP_200_OK
    return {**action_service.as_dict(action), "created": created}
