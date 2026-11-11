"""Order, buyer message and evidence models.

Every row carries the provenance triple (rule R5):

``source``       PAYPAL_SANDBOX | SIMULATED | MOCK
``is_demo``      whether the row belongs to a demo walkthrough
``demo_run_id``  which walkthrough, or NULL

Demo membership is independent of source. A row created from a real Sandbox
response is ``source=PAYPAL_SANDBOX, is_demo=False`` even if it was produced
during a demo, and ``POST /api/demo/reset`` must never delete it.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.timeutil import utcnow
from app.db.base import Base, UtcDateTime
from app.models.enums import SourceLabel

SOURCE_VALUES = tuple(label.value for label in SourceLabel)
_SOURCE_CHECK = "source IN ('PAYPAL_SANDBOX', 'SIMULATED', 'MOCK')"


class Order(Base):
    """A merchant order under dispute-risk observation."""

    __tablename__ = "orders"
    __table_args__ = (CheckConstraint(_SOURCE_CHECK, name="ck_orders_source_label"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    order_ref: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    # --- buyer / item ------------------------------------------------------
    buyer_name: Mapped[str] = mapped_column(String(128))
    buyer_email: Mapped[str] = mapped_column(String(255))
    item_name: Mapped[str] = mapped_column(String(255))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    status: Mapped[str] = mapped_column(String(32))

    # --- shipping evidence -------------------------------------------------
    tracking_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    carrier: Mapped[str | None] = mapped_column(String(64), nullable=True)
    shipped_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    delivery_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)

    # --- merchant policy / listing evidence --------------------------------
    item_description_on_file: Mapped[bool] = mapped_column(Boolean, default=False)
    policy_on_file: Mapped[bool] = mapped_column(Boolean, default=False)

    # --- risk inputs (all synthetic in the demo) ---------------------------
    buyer_country: Mapped[str | None] = mapped_column(String(2), nullable=True)
    merchant_country: Mapped[str | None] = mapped_column(String(2), nullable=True)
    is_first_time_buyer: Mapped[bool] = mapped_column(Boolean, default=False)
    buyer_negative_history: Mapped[int] = mapped_column(Integer, default=0)
    category: Mapped[str] = mapped_column(String(32), default="general")

    # --- flags -------------------------------------------------------------
    flagged_for_review: Mapped[bool] = mapped_column(Boolean, default=False)
    paypal_order_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    # --- cached rule score (recomputed on demand; never authoritative) -----
    risk_score: Mapped[float | None] = mapped_column(Numeric(5, 3), nullable=True)
    risk_level: Mapped[str | None] = mapped_column(String(16), nullable=True)

    # --- rule R5 provenance ------------------------------------------------
    source: Mapped[str] = mapped_column(String(32), index=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    demo_run_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow, onupdate=utcnow)

    messages: Mapped[list["BuyerMessage"]] = relationship(
        back_populates="order", cascade="all, delete-orphan", passive_deletes=True
    )
    evidence: Mapped[list["EvidenceItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan", passive_deletes=True
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging convenience
        return f"<Order id={self.id} ref={self.order_ref!r} source={self.source!r}>"


class BuyerMessage(Base):
    """A buyer or merchant message logged against an order.

    Merchant messages are what ``MESSAGE_BUYER`` writes, so the "buyer
    communication logged" checklist item becomes true once the action runs.
    """

    __tablename__ = "buyer_messages"
    __table_args__ = (CheckConstraint(_SOURCE_CHECK, name="ck_buyer_messages_source"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), index=True
    )
    direction: Mapped[str] = mapped_column(String(16))  # BUYER | MERCHANT
    body: Mapped[str] = mapped_column(Text)
    sent_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)
    intent: Mapped[str | None] = mapped_column(String(32), nullable=True)

    source: Mapped[str] = mapped_column(String(32))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    demo_run_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)

    order: Mapped[Order] = relationship(back_populates="messages")


class EvidenceItem(Base):
    """A piece of evidence attached to an order (tracking, delivery, policy...)."""

    __tablename__ = "evidence_items"
    __table_args__ = (CheckConstraint(_SOURCE_CHECK, name="ck_evidence_items_source"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(48))
    value: Mapped[str] = mapped_column(Text, default="")
    present: Mapped[bool] = mapped_column(Boolean, default=True)

    source: Mapped[str] = mapped_column(String(32))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    demo_run_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)

    order: Mapped[Order] = relationship(back_populates="evidence")
