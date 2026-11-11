"""Audit log - the append-only record of everything that happened.

Every proposal, approval, rejection, claim, execution, failure, retry, reconcile,
demo reset, scan and LLM call writes exactly one row here. ``detail`` is
deterministic JSON so a story run produces identical evidence every time.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.timeutil import utcnow
from app.db.base import Base, UtcDateTime
from app.models.enums import Actor
from app.models.jsoncol import JsonText


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Nullable foreign keys with ON DELETE CASCADE so a demo reset can remove
    # a demo order's history in one transaction without orphaning rows.
    order_id: Mapped[int | None] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), nullable=True, index=True
    )
    action_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    dispute_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)

    actor: Mapped[str] = mapped_column(String(16), default=Actor.SYSTEM.value)
    event: Mapped[str] = mapped_column(String(64), index=True)
    detail: Mapped[dict[str, object] | None] = mapped_column(JsonText, nullable=True)
    message: Mapped[str] = mapped_column(Text, default="")

    #: Provenance of the event itself. A LIVE execution writes one row with
    #: source=PAYPAL_SANDBOX; that row must survive a demo reset.
    source: Mapped[str] = mapped_column(String(32), default="SIMULATED", index=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    demo_run_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow, index=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AuditLog id={self.id} event={self.event} actor={self.actor}>"
