"""Dispute and dispute-draft models (Phase 6).

A dispute here is a *defence case*, not a prediction. ``evidence_strength`` is
a transparent checklist score (services/evidence_score.py), never a win
probability, and ``submit`` is SIMULATED unless a real PayPal response was
verified (see DECISIONS.md).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.timeutil import utcnow
from app.db.base import Base, UtcDateTime
from app.models.enums import DisputeStatus, DraftStatus
from app.models.jsoncol import JsonText

_SOURCE_CHECK = "source IN ('PAYPAL_SANDBOX', 'SIMULATED', 'MOCK')"


class Dispute(Base):
    __tablename__ = "disputes"
    __table_args__ = (CheckConstraint(_SOURCE_CHECK, name="ck_disputes_source"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), index=True
    )
    paypal_dispute_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    reason: Mapped[str] = mapped_column(String(64), default="MERCHANDISE_OR_SERVICE_NOT_RECEIVED")
    status: Mapped[str] = mapped_column(String(24), default=DisputeStatus.OPEN.value)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    evidence_strength: Mapped[int] = mapped_column(Integer, default=0)
    buyer_claim: Mapped[str] = mapped_column(Text, default="")
    opened_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)
    submitted_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    submit_result: Mapped[dict[str, object] | None] = mapped_column(JsonText, nullable=True)

    source: Mapped[str] = mapped_column(String(32), default="SIMULATED")
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    demo_run_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow, onupdate=utcnow)

    drafts: Mapped[list["DisputeDraft"]] = relationship(
        back_populates="dispute", cascade="all, delete-orphan", passive_deletes=True
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Dispute id={self.id} status={self.status}>"


class DisputeDraft(Base):
    """A versioned, editable response draft. Origin is always shown in the UI."""

    __tablename__ = "dispute_drafts"
    __table_args__ = (CheckConstraint(_SOURCE_CHECK, name="ck_dispute_drafts_source"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    dispute_id: Mapped[int] = mapped_column(
        ForeignKey("disputes.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[int] = mapped_column(Integer, default=1)
    body: Mapped[str] = mapped_column(Text, default="")
    #: "AI draft" or "Template draft" - rendered verbatim in the UI (MASTER 10.8).
    origin: Mapped[str] = mapped_column(String(32), default="Template draft")
    strategy_note: Mapped[str] = mapped_column(Text, default="")
    missing_evidence: Mapped[list[str] | None] = mapped_column(JsonText, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default=DraftStatus.DRAFT.value)
    submitted_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)

    source: Mapped[str] = mapped_column(String(32), default="SIMULATED")
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    demo_run_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)

    dispute: Mapped[Dispute] = relationship(back_populates="drafts")
