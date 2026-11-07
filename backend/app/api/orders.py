"""Order endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.models.order import Order
from app.schemas.order import ErrorResponse, OrderRead

router = APIRouter(prefix="/orders", tags=["orders"])


@router.get(
    "/{order_id}",
    response_model=OrderRead,
    responses={status.HTTP_404_NOT_FOUND: {"model": ErrorResponse}},
    summary="Fetch a single order by its database id",
)
def get_order(order_id: int, db: Session = Depends(get_db)) -> Order:
    order = db.get(Order, order_id)
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order {order_id} not found.",
        )
    return order
