"""The Order model.

Every row carries the rule R5 provenance triple:

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

from sqlalchemy import Boolean, CheckConstraint, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.timeutil import utcnow
from app.db.base import Base, UtcDateTime
from app.models.enums import SourceLabel

SOURCE_VALUES = tuple(label.value for label in SourceLabel)


class Order(Base):
    """A merchant order under dispute-risk observation."""

    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint(
            "source IN ('PAYPAL_SANDBOX', 'SIMULATED', 'MOCK')",
            name="ck_orders_source_label",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    order_ref: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    buyer_name: Mapped[str] = mapped_column(String(128))
    buyer_email: Mapped[str] = mapped_column(String(255))
    item_name: Mapped[str] = mapped_column(String(255))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    status: Mapped[str] = mapped_column(String(32))

    # --- rule R5 provenance -------------------------------------------------
    source: Mapped[str] = mapped_column(String(32), index=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    demo_run_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow, onupdate=utcnow)

    def __repr__(self) -> str:  # pragma: no cover - debugging convenience
        return f"<Order id={self.id} ref={self.order_ref!r} source={self.source!r}>"
