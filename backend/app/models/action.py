"""Action model - the human-approval execution engine's persisted state.

The columns mirror MASTER 4.4 exactly: a conditional claim
(``claim_token`` + ``claimed_at``) guards the transition to EXECUTING, and the
before/after diff plus the sanitised result are only written after a CONFIRMED
external success.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.timeutil import utcnow
from app.db.base import Base, UtcDateTime
from app.models.enums import ActionStatus, ActionType
from app.models.jsoncol import JsonText

_SOURCE_CHECK = "source IN ('PAYPAL_SANDBOX', 'SIMULATED', 'MOCK')"
_STATUS_CHECK = (
    "status IN ('PENDING','APPROVED','REJECTED','EXECUTING','EXECUTED','FAILED','UNKNOWN')"
)
_TYPE_CHECK = "type IN ('ADD_TRACKING','MESSAGE_BUYER','FLAG_FOR_REVIEW')"


class Action(Base):
    """A proposed merchant action and its execution state."""

    __tablename__ = "actions"
    __table_args__ = (
        CheckConstraint(_SOURCE_CHECK, name="ck_actions_source"),
        CheckConstraint(_STATUS_CHECK, name="ck_actions_status"),
        CheckConstraint(_TYPE_CHECK, name="ck_actions_type"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), index=True
    )

    type: Mapped[str] = mapped_column(String(32), default=ActionType.FLAG_FOR_REVIEW.value)
    status: Mapped[str] = mapped_column(
        String(16), default=ActionStatus.PENDING.value, index=True
    )
    payload: Mapped[dict[str, object] | None] = mapped_column(JsonText, nullable=True)
    rationale: Mapped[str] = mapped_column(Text, default="")
    proposed_by: Mapped[str] = mapped_column(String(16), default="MERCHANT")

    # --- claim protocol ----------------------------------------------------
    claim_token: Mapped[str | None] = mapped_column(String(64), nullable=True)
    claimed_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)

    # --- outcome -----------------------------------------------------------
    executed_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    before_diff: Mapped[dict[str, object] | None] = mapped_column(JsonText, nullable=True)
    after_diff: Mapped[dict[str, object] | None] = mapped_column(JsonText, nullable=True)
    result: Mapped[dict[str, object] | None] = mapped_column(JsonText, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    reconcile_outcome: Mapped[str | None] = mapped_column(String(24), nullable=True)

    # --- provenance --------------------------------------------------------
    source: Mapped[str] = mapped_column(String(32), default="SIMULATED")
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    demo_run_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow, onupdate=utcnow)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Action id={self.id} type={self.type} status={self.status}>"
