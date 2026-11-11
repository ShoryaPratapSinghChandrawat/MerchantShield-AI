"""The demo storefront: 4 products, a real (or mocked) PayPal checkout.

The flow MASTER asks for:

1. the buyer picks a product;
2. the server creates a PayPal order and hands back the approval link;
3. the buyer approves at PayPal (or on the clearly-labelled MOCK screen);
4. the browser returns to ``/store/return`` and the app CAPTURES the payment;
5. only then is the order recorded - ``source=PAYPAL_SANDBOX`` (LIVE) when
   PayPal really answered, ``source=MOCK`` when the mock adapter did.

The order row is created at step 2 with ``status=PENDING_PAYMENT`` so an
abandoned checkout is visible and does not pretend to be a paid order.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.timeutil import utcnow
from app.models.enums import SourceLabel
from app.models.order import Order
from app.services import audit
from app.services.paypal_service import PayPalService

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Product:
    id: str
    name: str
    price: str
    category: str
    blurb: str
    high_value: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "price": self.price,
            "category": self.category,
            "blurb": self.blurb,
            "high_value": self.high_value,
        }


PRODUCTS: tuple[Product, ...] = (
    Product(
        "P-100",
        "Aurora X2 laptop, 16GB",
        "1899.00",
        "electronics",
        "The high-value item: the case where a dispute actually hurts.",
        high_value=True,
    ),
    Product(
        "P-200",
        "Noise-cancelling headphones",
        "249.00",
        "electronics",
        "Mid-value electronics, the most common dispute category.",
    ),
    Product(
        "P-300",
        "USB-C braided cable, 2m",
        "14.50",
        "general",
        "Cheap accessory - low risk, still worth tracking.",
    ),
    Product(
        "P-400",
        "Silk scarf",
        "76.00",
        "apparel",
        "Apparel, where 'not as described' claims are common.",
    ),
)


def find_product(product_id: str) -> Product | None:
    return next((p for p in PRODUCTS if p.id == product_id), None)


def _source_for(paypal: PayPalService) -> str:
    return SourceLabel.PAYPAL_SANDBOX.value if paypal.mode == "live-sandbox" else SourceLabel.MOCK.value


async def checkout(
    session: Session,
    paypal: PayPalService,
    *,
    product_id: str,
    buyer_name: str,
    buyer_email: str,
) -> dict[str, Any]:
    """Create the PayPal order and the PENDING_PAYMENT row. No capture yet."""
    product = find_product(product_id)
    if product is None:
        raise ValueError(f"unknown product {product_id!r}")

    settings = get_settings()
    request_id = f"checkout-{uuid.uuid4()}"
    return_url = f"{settings.app_base_url}/store/return"
    cancel_url = f"{settings.app_base_url}/store?cancelled=1"

    result = await paypal.create_order(
        amount=product.price,
        currency="USD",
        return_url=return_url,
        cancel_url=cancel_url,
        request_id=request_id,
    )
    if result.outcome != "EXECUTED":
        audit.record(
            session,
            event="checkout_failed",
            message="PayPal order creation failed; nothing was charged",
            detail={"error": result.error, "source": result.source},
            source=result.source,
            commit=True,
        )
        raise RuntimeError(result.error or "PayPal order creation failed")

    paypal_order_id = str(result.detail.get("order_id") or "")
    order = Order(
        order_ref=f"MS-{uuid.uuid4().hex[:8].upper()}",
        buyer_name=buyer_name or "Demo Buyer",
        buyer_email=buyer_email or "buyer@example.com",
        item_name=product.name,
        amount=Decimal(product.price),
        currency="USD",
        status="PENDING_PAYMENT",
        category=product.category,
        buyer_country="US",
        merchant_country="US",
        is_first_time_buyer=True,
        buyer_negative_history=0,
        item_description_on_file=True,
        policy_on_file=True,
        paypal_order_id=paypal_order_id,
        source=_source_for(paypal),
        is_demo=False,
    )
    session.add(order)
    session.flush()
    audit.record(
        session,
        event="checkout_created",
        order_id=order.id,
        message=f"PayPal order created for {product.name} ({result.source})",
        detail={
            "paypal_order_id": paypal_order_id,
            "approval_url": result.detail.get("approval_url"),
            "source": result.source,
        },
        source=order.source,
    )
    session.commit()

    # In MOCK mode the "approval" is a clearly-labelled fake screen inside this
    # app, never a PayPal URL. Saying otherwise would imply a PayPal page.
    approval_url = result.detail.get("approval_url")
    if result.source == "MOCK":
        approval_url = f"{settings.app_base_url}/store/mock-approve?token={paypal_order_id}"

    return {
        "order_id": order.id,
        "order_ref": order.order_ref,
        "paypal_order_id": paypal_order_id,
        "approval_url": approval_url,
        "source": order.source,
        "mock": result.source == "MOCK",
        "product": product.as_dict(),
    }


async def complete(
    session: Session, paypal: PayPalService, *, paypal_order_id: str
) -> dict[str, Any]:
    """Capture the payment and mark the order paid."""
    order = session.scalars(
        select(Order).where(Order.paypal_order_id == paypal_order_id)
    ).first()
    if order is None:
        raise ValueError("no order is waiting for that PayPal order id")

    result = await paypal.capture_order(
        order_id=paypal_order_id, request_id=f"capture-{paypal_order_id}"
    )
    if result.outcome != "EXECUTED":
        audit.record(
            session,
            event="capture_failed",
            order_id=order.id,
            message="Capture did not succeed; the order stays unpaid",
            detail={"error": result.error, "source": result.source, "outcome": result.outcome},
            source=order.source,
            commit=True,
        )
        return {
            "captured": False,
            "outcome": result.outcome,
            "error": result.error,
            "order_id": order.id,
            "source": result.source,
        }

    order.status = "COMPLETED"
    order.source = _source_for(paypal)
    order.updated_at = utcnow()
    order.created_at = utcnow()
    audit.record(
        session,
        event="payment_captured",
        order_id=order.id,
        message=f"Payment captured and confirmed ({order.source})",
        detail={"paypal_order_id": paypal_order_id, "source": order.source},
        source=order.source,
    )
    session.commit()
    return {
        "captured": True,
        "outcome": result.outcome,
        "order_id": order.id,
        "order_ref": order.order_ref,
        "source": order.source,
        "note": (
            "LIVE: this record came from a real PayPal Sandbox response."
            if order.source == SourceLabel.PAYPAL_SANDBOX.value
            else "MOCK: no PayPal account was contacted. This is a stand-in."
        ),
    }
