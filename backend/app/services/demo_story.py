"""The demo director: one call that plays the whole V1 story.

``POST /api/demo/run-story`` walks: checkout -> order appears -> fast-forward
4 days -> scan -> proposals -> approve -> execute (with its LIVE/MOCK/
SIMULATED chip) -> diff + audit -> dispute -> packet + draft -> approve ->
submit (labelled SIMULATED).

It is repeatable: each run creates a NEW simulated order, so the previous run's
evidence stays visible instead of being overwritten. It uses the mock PayPal
adapter unless real credentials are configured, and every step reports its
source so the UI can chip it.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models.action import Action
from app.models.enums import ActionStatus, Actor
from app.models.order import Order
from app.services import actions as action_service
from app.services import audit, disputes as dispute_service, orders as order_service, store
from app.services.paypal_service import PayPalService

logger = logging.getLogger(__name__)

STORY_PRODUCT_ID = "P-200"
STORY_DAYS_FAST_FORWARD = 4


async def run_story(session: Session, paypal: PayPalService) -> dict[str, Any]:
    steps: list[dict[str, Any]] = []
    product = store.find_product(STORY_PRODUCT_ID)
    assert product is not None

    # 1 - checkout -----------------------------------------------------------
    checkout = await store.checkout(
        session,
        paypal,
        product_id=STORY_PRODUCT_ID,
        buyer_name="Jordan Blake",
        buyer_email="jordan.blake@example.com",
    )
    steps.append(
        {
            "step": "checkout",
            "title": "Buyer checks out",
            "detail": f"PayPal order {checkout['paypal_order_id']} created for {product.name}",
            "source": checkout["source"],
        }
    )

    # 2 - capture ------------------------------------------------------------
    capture = await store.complete(session, paypal, paypal_order_id=checkout["paypal_order_id"])
    steps.append(
        {
            "step": "captured",
            "title": "Payment captured",
            "detail": capture.get("note", ""),
            "source": capture["source"],
        }
    )

    order = session.get(Order, checkout["order_id"])
    assert order is not None

    # 3 - fast-forward -------------------------------------------------------
    from app.db.seed import fast_forward

    fast_forward(session, order, days=STORY_DAYS_FAST_FORWARD)
    steps.append(
        {
            "step": "fast_forward",
            "title": f"Fast-forward {STORY_DAYS_FAST_FORWARD} days",
            "detail": "The order now looks like a parcel that should have arrived.",
            "source": order.source,
        }
    )

    # 4 - scan ---------------------------------------------------------------
    scan = order_service.scan(session, order)
    steps.append(
        {
            "step": "scan",
            "title": f"Risk scan: {scan['risk_level']}",
            "detail": (
                f"{scan['risk_points']}/100 points, "
                f"{sum(1 for m in scan['missing_evidence'] if not m['present'])} evidence items missing"
            ),
            "source": order.source,
        }
    )

    # 5 - proposals ----------------------------------------------------------
    planned = order_service.trigger_agent(session, order)
    steps.append(
        {
            "step": "proposals",
            "title": f"{len(planned['proposals'])} proposal(s) waiting",
            "detail": planned["note"],
            "source": order.source,
        }
    )

    # 6 - approve + execute --------------------------------------------------
    proposals = [
        a
        for a in action_service.as_dict_list(session, order.id)
        if a["status"] == ActionStatus.PENDING.value
    ]
    executed_ids: list[int] = []
    for proposal in proposals[:2]:
        action = session.get(Action, proposal["id"])
        if action is None:
            continue
        action_service.approve(session, action, actor=Actor.MERCHANT)
        result = await action_service.execute(session, action.id, paypal, actor=Actor.MERCHANT)
        executed_ids.append(result.action.id)
        steps.append(
            {
                "step": "execute",
                "title": f"{result.action.type} -> {result.action.status}",
                "detail": f"Before {result.action.before_diff} / after {result.action.after_diff}",
                "source": result.action.source,
            }
        )

    # 7 - dispute, packet, draft, approve, submit ----------------------------
    dispute = dispute_service.ensure_seeded(session, order)
    packet = dispute_service.packet(session, dispute)
    steps.append(
        {
            "step": "dispute_packet",
            "title": f"Evidence packet: {packet['evidence_strength']['score']}/100",
            "detail": "Checklist of documents held - not a prediction.",
            "source": dispute.source,
        }
    )

    draft = await dispute_service.create_draft(session, dispute)
    steps.append(
        {
            "step": "draft",
            "title": f"Draft v{draft.version} ({draft.origin})",
            "detail": draft.strategy_note,
            "source": dispute.source,
        }
    )
    dispute_service.approve_draft(session, draft)
    submitted = dispute_service.submit(session, dispute)
    steps.append(
        {
            "step": "submit",
            "title": f"Submitted ({submitted['submission_mode']})",
            "detail": submitted["note"],
            "source": submitted["source"],
        }
    )

    audit.record(
        session,
        event="demo_story_run",
        message="Demo director finished",
        detail={"steps": [s["step"] for s in steps], "order_id": order.id},
        order_id=order.id,
        source=order.source,
        is_demo=order.is_demo,
        demo_run_id=order.demo_run_id,
        commit=True,
    )

    return {
        "run_id": f"story-{uuid.uuid4().hex[:8]}",
        "order_id": order.id,
        "order_ref": order.order_ref,
        "steps": steps,
        "executed_action_ids": executed_ids,
        "dispute_id": dispute.id,
        "note": (
            "Every source chip above is the real one for that step. Nothing here "
            "claims a PayPal success that was not confirmed."
        ),
    }
