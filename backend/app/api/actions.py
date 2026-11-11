"""Action endpoints - the whole 4.4 protocol, exposed."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.models.action import Action
from app.schemas.actions import ReconcileRequest
from app.services import actions as action_service
from app.services.paypal_service import PayPalService, get_paypal_service

router = APIRouter(prefix="/actions", tags=["actions"])


def paypal_dep() -> PayPalService:
    """Dependency indirection so tests can override it with app.dependency_overrides."""
    return get_paypal_service()


def _get_action_or_404(session: Session, action_id: int) -> Action:
    action = session.get(Action, action_id)
    if action is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Action {action_id} not found."
        )
    return action


@router.get("", summary="List actions, optionally filtered")
def list_actions(
    status_filter: str | None = None,
    order_id: int | None = None,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    stmt = select(Action).order_by(Action.id.desc())
    if status_filter:
        stmt = stmt.where(Action.status == status_filter.upper())
    if order_id is not None:
        stmt = stmt.where(Action.order_id == order_id)
    rows = list(db.scalars(stmt))
    return {"count": len(rows), "items": [action_service.as_dict(row) for row in rows]}


@router.get("/{action_id}", summary="One action")
def get_action(action_id: int, db: Session = Depends(get_db)) -> dict[str, object]:
    return action_service.as_dict(_get_action_or_404(db, action_id))


@router.post("/{action_id}/approve", summary="Approve a PENDING action")
def approve(action_id: int, db: Session = Depends(get_db)) -> dict[str, object]:
    action = _get_action_or_404(db, action_id)
    return action_service.as_dict(action_service.approve(db, action))


@router.post("/{action_id}/reject", summary="Reject a PENDING action")
def reject(action_id: int, db: Session = Depends(get_db)) -> dict[str, object]:
    action = _get_action_or_404(db, action_id)
    return action_service.as_dict(action_service.reject(db, action))


@router.post("/{action_id}/execute", summary="Claim and execute an APPROVED action")
async def execute(
    action_id: int,
    db: Session = Depends(get_db),
    paypal: PayPalService = Depends(paypal_dep),
) -> dict[str, object]:
    action = _get_action_or_404(db, action_id)
    result = await action_service.execute(db, action.id, paypal)
    payload = action_service.as_dict(result.action)
    payload["already_executed"] = result.already_executed
    return payload


@router.post("/{action_id}/retry", summary="Retry a FAILED action (never an UNKNOWN one)")
def retry(action_id: int, db: Session = Depends(get_db)) -> dict[str, object]:
    action = _get_action_or_404(db, action_id)
    return action_service.as_dict(action_service.retry(db, action))


@router.post(
    "/{action_id}/reconcile",
    summary="Resolve an UNKNOWN action: APPLIED, NOT_APPLIED or INDETERMINATE",
)
async def reconcile(
    action_id: int,
    body: ReconcileRequest | None = None,
    db: Session = Depends(get_db),
    paypal: PayPalService = Depends(paypal_dep),
) -> dict[str, object]:
    action = _get_action_or_404(db, action_id)
    request = body or ReconcileRequest()
    return await action_service.reconcile(
        db, action, paypal, confirm_not_applied=request.confirm_not_applied
    )
