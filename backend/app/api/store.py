"""Demo storefront endpoints: products, checkout, capture/return."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.actions import paypal_dep
from app.db.base import get_db
from app.schemas.actions import CaptureRequest, CheckoutRequest
from app.services import store
from app.services.paypal_service import PayPalService

router = APIRouter(prefix="/store", tags=["store"])


@router.get("/products", summary="The four demo products")
def products() -> dict[str, object]:
    return {"items": [product.as_dict() for product in store.PRODUCTS]}


@router.post("/checkout", summary="Create a PayPal order and a PENDING_PAYMENT row")
async def checkout(
    body: CheckoutRequest,
    db: Session = Depends(get_db),
    paypal: PayPalService = Depends(paypal_dep),
) -> dict[str, object]:
    try:
        return await store.checkout(
            db,
            paypal,
            product_id=body.product_id,
            buyer_name=body.buyer_name,
            buyer_email=body.buyer_email,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.post("/capture", summary="Capture the payment after approval")
async def capture(
    body: CaptureRequest,
    db: Session = Depends(get_db),
    paypal: PayPalService = Depends(paypal_dep),
) -> dict[str, object]:
    try:
        return await store.complete(db, paypal, paypal_order_id=body.token)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/return", summary="PayPal return URL handler (captures the token)")
async def store_return(
    token: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
    paypal: PayPalService = Depends(paypal_dep),
) -> dict[str, object]:
    try:
        return await store.complete(db, paypal, paypal_order_id=token)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
