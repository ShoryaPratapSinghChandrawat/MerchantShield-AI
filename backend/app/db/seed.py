"""Demo data: 15 hand-written story orders, reset, and the demo director.

The 15 orders are the Phase 1 specification (MASTER section 9) written as
literal, deterministic story cases - no clever generation, because the whole
point is that a human can read them and predict the score:

1  expensive laptop, no tracking, chargeback threat      (the worst case)
2  cheap cable, fully tracked, delivered                  (the best case)
3  first-time buyer, country mismatch
4  tracked but no delivery confirmation
5  calm buyer, tracking plus delivery confirmation
6  old order, no tracking (age matters)
7  old order, tracked (age must NOT be penalised)
8  buyer messages mentioning a refund without negation
9  "no refund needed" - the negation trap
10 high-value jewellery, negative buyer history
11 returning buyer, digital goods, calm
12 brand-new order, no evidence yet (low amounts of data)
13 mid-value order, partial evidence
14 buyer threatening a lawyer (negated elsewhere in the thread)
15 an everything-is-fine control case

All of them are ``source=SIMULATED, is_demo=True`` and share one demo_run_id,
so ``POST /api/demo/reset`` can remove exactly the demo and nothing else.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.timeutil import utcnow
from app.models.action import Action
from app.models.audit import AuditLog
from app.models.dispute import Dispute, DisputeDraft
from app.models.enums import SourceLabel
from app.models.order import BuyerMessage, EvidenceItem, Order
from app.services import audit

logger = logging.getLogger(__name__)

DEMO_RUN_ID = "demo-run-phase1"
SEED_BASE = datetime(2026, 11, 2, 9, 0, 0, tzinfo=timezone.utc)


@dataclass(frozen=True)
class StoryOrder:
    ref: str
    buyer_name: str
    buyer_email: str
    item: str
    amount: str
    category: str
    status: str
    days_ago: int
    buyer_country: str
    merchant_country: str
    first_time: bool
    negative: int
    tracking: str | None = None
    carrier: str | None = None
    shipped_days_ago: int | None = None
    delivered: bool = False
    description: bool = False
    policy: bool = False
    messages: tuple[tuple[str, str], ...] = field(default_factory=tuple)
    note: str = ""


STORY_ORDERS: tuple[StoryOrder, ...] = (
    StoryOrder(
        ref="MS-2001", buyer_name="Daniel Reyes", buyer_email="daniel.reyes@example.com",
        item="Aurora X2 laptop, 16GB", amount="1899.00", category="electronics",
        status="COMPLETED", days_ago=41, buyer_country="US", merchant_country="US",
        first_time=True, negative=72, description=True, policy=False,
        messages=(("BUYER", "This is a scam. I will file a chargeback with my bank."),),
        note="Worst case: expensive, untracked, angry buyer, first-timer.",
    ),
    StoryOrder(
        ref="MS-2002", buyer_name="Priya Nair", buyer_email="priya.nair@example.com",
        item="USB-C braided cable, 2m", amount="14.50", category="general",
        status="COMPLETED", days_ago=8, buyer_country="US", merchant_country="US",
        first_time=False, negative=4, tracking="1Z999AA10123456784", carrier="UPS",
        shipped_days_ago=7, delivered=True, description=True, policy=True,
        messages=(("BUYER", "Arrived, works fine, thanks!"),),
        note="Best case: cheap, tracked, delivered, returning buyer.",
    ),
    StoryOrder(
        ref="MS-2003", buyer_name="Marco Bianchi", buyer_email="marco.bianchi@example.com",
        item="Noise-cancelling headphones", amount="249.00", category="electronics",
        status="COMPLETED", days_ago=12, buyer_country="IT", merchant_country="US",
        first_time=True, negative=18, description=True,
        note="First-time buyer, country mismatch, no tracking.",
    ),
    StoryOrder(
        ref="MS-2004", buyer_name="Amelia Fox", buyer_email="amelia.fox@example.com",
        item="Ceramic pour-over set", amount="64.00", category="household",
        status="SHIPPED", days_ago=19, buyer_country="US", merchant_country="US",
        first_time=False, negative=9, tracking="9400111899223197428490", carrier="USPS",
        shipped_days_ago=16, description=True, policy=True,
        note="Tracked but no delivery confirmation on file.",
    ),
    StoryOrder(
        ref="MS-2005", buyer_name="Tomas Nowak", buyer_email="tomas.nowak@example.com",
        item="Mechanical keyboard", amount="139.00", category="electronics",
        status="COMPLETED", days_ago=15, buyer_country="US", merchant_country="US",
        first_time=False, negative=6, tracking="1Z888BB20987654321", carrier="UPS",
        shipped_days_ago=14, delivered=True, description=True, policy=True,
        messages=(("BUYER", "Got it, all good."),),
        note="Calm communication plus full evidence.",
    ),
    StoryOrder(
        ref="MS-2006", buyer_name="Hannah Schmidt", buyer_email="hannah.s@example.com",
        item="Trail running shoes", amount="128.00", category="apparel",
        status="COMPLETED", days_ago=58, buyer_country="DE", merchant_country="DE",
        first_time=False, negative=22, description=False,
        note="Old and untracked - the age penalty applies here and only here.",
    ),
    StoryOrder(
        ref="MS-2007", buyer_name="Luis Ortega", buyer_email="luis.ortega@example.com",
        item="Bluetooth speaker", amount="89.00", category="electronics",
        status="COMPLETED", days_ago=55, buyer_country="ES", merchant_country="ES",
        first_time=False, negative=10, tracking="ES123456789012", carrier="DHL",
        shipped_days_ago=54, delivered=True, description=True, policy=True,
        note="Equally old but tracked - must not be penalised for age.",
    ),
    StoryOrder(
        ref="MS-2008", buyer_name="Aiko Tanaka", buyer_email="aiko.tanaka@example.com",
        item="Tablet stand", amount="42.00", category="general",
        status="COMPLETED", days_ago=9, buyer_country="JP", merchant_country="US",
        first_time=True, negative=30, description=True,
        messages=(("BUYER", "I want a refund, this is not what I ordered."),),
        note="Explicit refund request - the chargeback language rule fires.",
    ),
    StoryOrder(
        ref="MS-2009", buyer_name="Grace Miller", buyer_email="grace.miller@example.com",
        item="Desk lamp", amount="55.00", category="household",
        status="COMPLETED", days_ago=6, buyer_country="US", merchant_country="US",
        first_time=False, negative=5, tracking="1Z777CC30111222333", carrier="UPS",
        shipped_days_ago=5, description=True, policy=True,
        messages=(("BUYER", "Thanks - no refund needed, it arrived safely."),),
        note="Negation trap: 'no refund needed' must NOT trigger the refund flag.",
    ),
    StoryOrder(
        ref="MS-2010", buyer_name="Sofia Rossi", buyer_email="sofia.rossi@example.com",
        item="Gold vermeil necklace", amount="720.00", category="jewellery",
        status="COMPLETED", days_ago=22, buyer_country="IT", merchant_country="US",
        first_time=False, negative=68, description=True, policy=False,
        messages=(("BUYER", "It never arrived. I am opening a dispute."),),
        note="High value, high negative history, dispute language, no tracking.",
    ),
    StoryOrder(
        ref="MS-2011", buyer_name="Owen Clarke", buyer_email="owen.clarke@example.com",
        item="Photo editing preset pack", amount="29.00", category="digital",
        status="COMPLETED", days_ago=4, buyer_country="GB", merchant_country="GB",
        first_time=False, negative=3, description=True, policy=True,
        messages=(("BUYER", "All downloaded, thank you."),),
        note="Digital goods, returning buyer, calm.",
    ),
    StoryOrder(
        ref="MS-2012", buyer_name="Nadia Haddad", buyer_email="nadia.haddad@example.com",
        item="Yoga mat", amount="38.00", category="general",
        status="CREATED", days_ago=0, buyer_country="US", merchant_country="US",
        first_time=True, negative=0,
        note="Brand-new order with no evidence yet - low score, big evidence gap.",
    ),
    StoryOrder(
        ref="MS-2013", buyer_name="Felix Braun", buyer_email="felix.braun@example.com",
        item="Standing desk converter", amount="312.00", category="household",
        status="SHIPPED", days_ago=17, buyer_country="DE", merchant_country="US",
        first_time=False, negative=27, tracking="DE987654321098", carrier="DHL",
        shipped_days_ago=15, description=True, policy=False,
        note="Mid-value with partial evidence.",
    ),
    StoryOrder(
        ref="MS-2014", buyer_name="Ivan Petrov", buyer_email="ivan.petrov@example.com",
        item="Camera lens adapter", amount="180.00", category="electronics",
        status="COMPLETED", days_ago=11, buyer_country="BG", merchant_country="US",
        first_time=True, negative=40, description=True,
        messages=(
            ("BUYER", "I am not going to involve a lawyer, I just need an answer."),
            ("MERCHANT", "Thanks for your patience - checking with the carrier now."),
        ),
        note="Negated lawyer threat: must not raise the keyword rule.",
    ),
    StoryOrder(
        ref="MS-2015", buyer_name="Chloe Martin", buyer_email="chloe.martin@example.com",
        item="Silk scarf", amount="76.00", category="apparel",
        status="COMPLETED", days_ago=13, buyer_country="FR", merchant_country="FR",
        first_time=False, negative=2, tracking="FR112233445566", carrier="Royal Mail",
        shipped_days_ago=12, delivered=True, description=True, policy=True,
        messages=(("BUYER", "Lovely, thank you."),),
        note="Control case: everything is in order.",
    ),
)


def _timestamps(story: StoryOrder) -> tuple[datetime, datetime | None, datetime | None]:
    created = SEED_BASE - timedelta(days=story.days_ago)
    shipped = (
        SEED_BASE - timedelta(days=story.shipped_days_ago)
        if story.shipped_days_ago is not None
        else None
    )
    delivered = shipped + timedelta(days=2) if (story.delivered and shipped) else None
    return created, shipped, delivered


def build_order(story: StoryOrder, run_id: str = DEMO_RUN_ID) -> Order:
    created, shipped, delivered = _timestamps(story)
    return Order(
        order_ref=story.ref,
        buyer_name=story.buyer_name,
        buyer_email=story.buyer_email,
        item_name=story.item,
        amount=Decimal(story.amount),
        currency="USD",
        status=story.status,
        tracking_number=story.tracking,
        carrier=story.carrier,
        shipped_at=shipped,
        delivered_at=delivered,
        delivery_confirmed=story.delivered,
        item_description_on_file=story.description,
        policy_on_file=story.policy,
        buyer_country=story.buyer_country,
        merchant_country=story.merchant_country,
        is_first_time_buyer=story.first_time,
        buyer_negative_history=story.negative,
        category=story.category,
        source=SourceLabel.SIMULATED.value,
        is_demo=True,
        demo_run_id=run_id,
        created_at=created,
        updated_at=created,
    )


def seed_orders(session: Session, run_id: str = DEMO_RUN_ID) -> int:
    """Insert the 15 story orders, their messages and evidence rows."""
    inserted = 0
    for story in STORY_ORDERS:
        order = build_order(story, run_id)
        session.add(order)
        session.flush()
        for direction, body in story.messages:
            session.add(
                BuyerMessage(
                    order_id=order.id,
                    direction=direction,
                    body=body,
                    sent_at=order.created_at + timedelta(days=1),
                    source=SourceLabel.SIMULATED.value,
                    is_demo=True,
                    demo_run_id=run_id,
                    created_at=order.created_at + timedelta(days=1),
                )
            )
        if story.tracking:
            session.add(
                EvidenceItem(
                    order_id=order.id,
                    kind="TRACKING_NUMBER",
                    value=story.tracking,
                    source=SourceLabel.SIMULATED.value,
                    is_demo=True,
                    demo_run_id=run_id,
                    created_at=order.created_at,
                )
            )
        inserted += 1
    session.commit()
    return inserted


def seed_if_needed(session: Session) -> int:
    """Seed only when DEMO_MODE=true and the database has no orders at all."""
    settings = get_settings()
    if not settings.demo_mode:
        logger.info("DEMO_MODE is false - skipping seeding.")
        return 0
    if session.scalar(select(Order.id).limit(1)) is not None:
        logger.info("Database already has orders - skipping seeding.")
        return 0
    inserted = seed_orders(session)
    audit.record(
        session,
        event="demo_seeded",
        message=f"Seeded {inserted} story orders",
        detail={"orders": inserted, "demo_run_id": DEMO_RUN_ID},
        source=SourceLabel.SIMULATED.value,
        is_demo=True,
        demo_run_id=DEMO_RUN_ID,
        commit=True,
    )
    logger.info("Seeded %d story orders (source=SIMULATED, is_demo=true).", inserted)
    return inserted


def demo_rows_filter() -> tuple[Any, ...]:
    """The ONLY definition of what "reset demo" may delete.

    Deliberately one function, used by every statement in ``reset_demo``: two
    copies of this rule could drift, and the copy that drifts is the one that
    deletes a merchant's real Sandbox order.
    """
    return (Order.is_demo.is_(True), Order.source != SourceLabel.PAYPAL_SANDBOX.value)


def reset_demo(session: Session) -> dict[str, Any]:
    """Delete ONLY demo rows that are not LIVE, in FK-safe order, in one transaction.

    A row created from a real Sandbox response (``source=PAYPAL_SANDBOX``) is
    never deleted, even if ``is_demo`` is true - and neither are its dependent
    rows. This is tested directly.
    """
    demo_order_ids = list(
        session.scalars(
            select(Order.id).where(*demo_rows_filter())
        )
    )
    live_order_ids = set(
        session.scalars(
            select(Order.id).where(
                Order.is_demo.is_(True), Order.source == SourceLabel.PAYPAL_SANDBOX.value
            )
        )
    )

    deleted = {"orders": 0, "messages": 0, "evidence": 0, "actions": 0, "disputes": 0, "audit": 0}

    if demo_order_ids:
        dispute_ids = list(
            session.scalars(select(Dispute.id).where(Dispute.order_id.in_(demo_order_ids)))
        )
        if dispute_ids:
            deleted["disputes"] = session.execute(
                delete(DisputeDraft).where(DisputeDraft.dispute_id.in_(dispute_ids))
            ).rowcount or 0
            session.execute(delete(Dispute).where(Dispute.id.in_(dispute_ids)))
        deleted["actions"] = session.execute(
            delete(Action).where(Action.order_id.in_(demo_order_ids))
        ).rowcount or 0
        deleted["messages"] = session.execute(
            delete(BuyerMessage).where(BuyerMessage.order_id.in_(demo_order_ids))
        ).rowcount or 0
        deleted["evidence"] = session.execute(
            delete(EvidenceItem).where(EvidenceItem.order_id.in_(demo_order_ids))
        ).rowcount or 0
        deleted["audit"] = session.execute(
            delete(AuditLog).where(
                AuditLog.order_id.in_(demo_order_ids),
                AuditLog.source != SourceLabel.PAYPAL_SANDBOX.value,
            )
        ).rowcount or 0
        deleted["orders"] = session.execute(
            delete(Order).where(Order.id.in_(demo_order_ids), *demo_rows_filter())
        ).rowcount or 0

    audit.record(
        session,
        event="demo_reset",
        message="Demo reset: demo and simulated rows deleted; LIVE rows kept",
        detail={"deleted": deleted, "kept_live_orders": sorted(live_order_ids)},
        source=SourceLabel.SIMULATED.value,
        is_demo=True,
        demo_run_id=DEMO_RUN_ID,
    )
    session.commit()
    return {"deleted": deleted, "kept_live_orders": sorted(live_order_ids)}


def fast_forward(session: Session, order: Order, *, days: int = 4) -> Order:
    """Move an order's timestamps back, so a fresh order ages into a story."""
    order.created_at = order.created_at - timedelta(days=days)
    if order.shipped_at is not None:
        order.shipped_at = order.shipped_at - timedelta(days=days)
    order.updated_at = utcnow()
    audit.record(
        session,
        event="demo_fast_forward",
        order_id=order.id,
        message=f"Demo: fast-forwarded {days} days",
        detail={"days": days},
        source=order.source,
        is_demo=order.is_demo,
        demo_run_id=order.demo_run_id,
        commit=True,
    )
    session.refresh(order)
    return order
