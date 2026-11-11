"""Audit-log writer. One place, so no code path can forget to record an event."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.models.enums import Actor

logger = logging.getLogger(__name__)


def record(
    session: Session,
    *,
    event: str,
    actor: Actor | str = Actor.SYSTEM,
    message: str = "",
    detail: dict[str, Any] | None = None,
    order_id: int | None = None,
    action_id: int | None = None,
    dispute_id: int | None = None,
    source: str = "SIMULATED",
    is_demo: bool = False,
    demo_run_id: str | None = None,
    commit: bool = False,
) -> AuditLog:
    """Append one audit row.

    ``commit=False`` by default: callers that already own a transaction (the
    execution engine commits the state change, diff, result and audit row in
    ONE transaction, per MASTER 4.4) must not have it committed underneath them.
    """
    row = AuditLog(
        event=event,
        actor=actor.value if isinstance(actor, Actor) else actor,
        message=message,
        detail=detail or {},
        order_id=order_id,
        action_id=action_id,
        dispute_id=dispute_id,
        source=source,
        is_demo=is_demo,
        demo_run_id=demo_run_id,
    )
    session.add(row)
    if commit:
        session.commit()
    logger.info("audit %s actor=%s order=%s action=%s", event, row.actor, order_id, action_id)
    return row
