"""Audit trail endpoint with filters. Append-only by construction: no writes here."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.models.audit import AuditLog
from app.services.orders import audit_row_dict

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", summary="Audit rows, newest first")
def list_audit(
    event: str | None = None,
    order_id: int | None = None,
    action_id: int | None = None,
    actor: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    stmt = select(AuditLog).order_by(AuditLog.id.desc()).limit(limit)
    if event:
        stmt = stmt.where(AuditLog.event == event)
    if order_id is not None:
        stmt = stmt.where(AuditLog.order_id == order_id)
    if action_id is not None:
        stmt = stmt.where(AuditLog.action_id == action_id)
    if actor:
        stmt = stmt.where(AuditLog.actor == actor.upper())
    rows = list(db.scalars(stmt))
    return {"count": len(rows), "items": [audit_row_dict(row) for row in rows]}
