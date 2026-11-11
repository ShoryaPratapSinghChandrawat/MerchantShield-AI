"""The action engine: propose, approve, reject, execute, retry, reconcile.

This module is the safety-critical part of MerchantShield, so it follows
MASTER 4.4 to the letter:

* a **conditional UPDATE** claims the action (``WHERE id=? AND status='APPROVED'``)
  and only the caller whose update changed exactly one row goes on to make an
  external call;
* EXECUTED is only ever written after a CONFIRMED success, together with the
  before/after diff, the sanitised result and the audit row, in ONE transaction;
* FAILED means "known not to have happened", UNKNOWN means "may have happened";
  UNKNOWN never auto-retries and can only leave that state through Reconcile;
* an idempotency key derived from the action id is reused on retry.

Regressions here are covered by ``tests/test_actions.py`` and by the Phase 2
mutations in ``scripts/mutation_check.py``.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.timeutil import to_z, utcnow
from app.models.action import Action
from app.models.enums import (
    ACTION_ALLOWLIST,
    ActionStatus,
    ActionType,
    Actor,
    ReconcileOutcome,
)
from app.models.order import BuyerMessage, Order
from app.services import audit
from app.services.paypal_service import CallResult, PayPalService

logger = logging.getLogger(__name__)

#: A claim older than this is presumed dead and may be marked UNKNOWN.
STALE_CLAIM_SECONDS = 300

#: Tracking numbers: alphanumeric with optional dashes/spaces, 6-40 chars.
TRACKING_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9\- ]{4,38}[A-Za-z0-9]$")

KNOWN_CARRIERS = ("UPS", "USPS", "FEDEX", "DHL", "Royal Mail", "Australia Post", "Other")


class ActionError(Exception):
    """Base class for engine errors the API turns into 4xx responses."""

    status_code = 400


class InvalidActionType(ActionError):
    status_code = 422


class ActionConflict(ActionError):
    status_code = 409


class TrackingNumberInvalid(ActionError):
    status_code = 422


@dataclass
class ExecuteResult:
    action: Action
    already_executed: bool = False


# --------------------------------------------------------------------- helpers
def idempotency_key_for(action: Action) -> str:
    """Stable per action: a retry must reuse it (MASTER 4.4)."""
    return f"merchantshield-action-{action.id}"


def _payload_dict(action: Action) -> dict[str, Any]:
    payload = action.payload
    return dict(payload) if isinstance(payload, dict) else {}


def validate_payload(action_type: str, payload: dict[str, Any]) -> None:
    """Local validation. A failure here means nothing was ever sent -> FAILED."""
    if action_type == ActionType.ADD_TRACKING.value:
        number = str(payload.get("tracking_number", "")).strip()
        if not TRACKING_RE.match(number):
            raise TrackingNumberInvalid(
                "tracking_number must be 6-40 characters, letters, digits, dashes "
                "or spaces, starting and ending with a letter or digit"
            )
        carrier = str(payload.get("carrier", "")).strip()
        if not carrier:
            raise TrackingNumberInvalid("carrier is required to add tracking")
    if action_type == ActionType.MESSAGE_BUYER.value:
        body = str(payload.get("body", "")).strip()
        if not body:
            raise TrackingNumberInvalid("body is required to message the buyer")
        if len(body) > 2000:
            raise TrackingNumberInvalid("body must be 2000 characters or fewer")


def _snapshot(order: Order) -> dict[str, Any]:
    """The fields an action can change. Anything absent from here is not a diff."""
    return {
        "tracking_number": order.tracking_number,
        "carrier": order.carrier,
        "shipped_at": to_z(order.shipped_at) if order.shipped_at else None,
        "flagged_for_review": order.flagged_for_review,
        "status": order.status,
        "merchant_messages": sum(
            1 for message in order.messages if message.direction == "MERCHANT"
        ),
    }


def _diff(before: dict[str, Any], after: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return ONLY the fields that actually changed, in before/after form."""
    changed_before: dict[str, Any] = {}
    changed_after: dict[str, Any] = {}
    for key, old in before.items():
        new = after.get(key)
        if old != new:
            changed_before[key] = old
            changed_after[key] = new
    return changed_before, changed_after


# ------------------------------------------------------------------- proposing
def propose(
    session: Session,
    *,
    order: Order,
    action_type: str,
    payload: dict[str, Any] | None = None,
    rationale: str = "",
    actor: Actor | str = Actor.MERCHANT,
    source: str | None = None,
) -> tuple[Action, bool]:
    """Create a PENDING proposal. Returns (action, created).

    A duplicate *open* proposal of the same type returns the existing row with
    200 semantics (``created=False``) rather than piling up duplicates.
    """
    if action_type not in ACTION_ALLOWLIST:
        raise InvalidActionType(
            f"{action_type!r} is not an allowed action type. Allowed: "
            + ", ".join(sorted(ACTION_ALLOWLIST))
        )

    existing = session.scalars(
        select(Action)
        .where(
            Action.order_id == order.id,
            Action.type == action_type,
            Action.status.in_([ActionStatus.PENDING.value, ActionStatus.APPROVED.value]),
        )
        .order_by(Action.id)
    ).first()
    if existing is not None:
        return existing, False

    action = Action(
        order_id=order.id,
        type=action_type,
        status=ActionStatus.PENDING.value,
        payload=payload or {},
        rationale=rationale,
        proposed_by=actor.value if isinstance(actor, Actor) else actor,
        source=source or order.source,
        is_demo=order.is_demo,
        demo_run_id=order.demo_run_id,
    )
    session.add(action)
    session.flush()
    action.idempotency_key = idempotency_key_for(action)
    audit.record(
        session,
        event="action_proposed",
        actor=actor,
        order_id=order.id,
        action_id=action.id,
        message=f"Proposed {action_type}",
        detail={"type": action_type, "payload": payload or {}, "rationale": rationale},
        source=action.source,
        is_demo=order.is_demo,
        demo_run_id=order.demo_run_id,
    )
    session.commit()
    return action, True


# -------------------------------------------------------------------- approve
def approve(session: Session, action: Action, *, actor: Actor = Actor.MERCHANT) -> Action:
    """PENDING -> APPROVED. Re-approving APPROVED is a 200 no-op."""
    if action.status == ActionStatus.APPROVED.value:
        return action
    if action.status == ActionStatus.EXECUTED.value:
        raise ActionConflict("Action has already been executed.")
    if action.status == ActionStatus.FAILED.value:
        raise ActionConflict("A failed action must be retried explicitly, not re-approved.")
    if action.status == ActionStatus.UNKNOWN.value:
        raise ActionConflict("Outcome is not confirmed. Reconcile it instead of re-approving.")
    if action.status != ActionStatus.PENDING.value:
        raise ActionConflict(f"Cannot approve an action in state {action.status}.")

    action.status = ActionStatus.APPROVED.value
    action.updated_at = utcnow()
    audit.record(
        session,
        event="action_approved",
        actor=actor,
        order_id=action.order_id,
        action_id=action.id,
        message="Merchant approved the action",
        detail={"type": action.type},
        source=action.source,
        is_demo=action.is_demo,
        demo_run_id=action.demo_run_id,
    )
    session.commit()
    return action


def reject(session: Session, action: Action, *, actor: Actor = Actor.MERCHANT) -> Action:
    if action.status != ActionStatus.PENDING.value:
        raise ActionConflict(f"Cannot reject an action in state {action.status}.")
    action.status = ActionStatus.REJECTED.value
    action.updated_at = utcnow()
    audit.record(
        session,
        event="action_rejected",
        actor=actor,
        order_id=action.order_id,
        action_id=action.id,
        message="Merchant rejected the action",
        detail={"type": action.type},
        source=action.source,
        is_demo=action.is_demo,
        demo_run_id=action.demo_run_id,
    )
    session.commit()
    return action


# -------------------------------------------------------------------- execute
def _claim(session: Session, action_id: int) -> tuple[str, Action | None]:
    """Conditional claim. Returns (token, action-or-None-if-claim-lost)."""
    token = str(uuid.uuid4())
    result = session.execute(
        update(Action)
        .where(Action.id == action_id, Action.status == ActionStatus.APPROVED.value)
        .values(
            status=ActionStatus.EXECUTING.value,
            claim_token=token,
            claimed_at=utcnow(),
            attempts=Action.attempts + 1,
            updated_at=utcnow(),
        )
        .execution_options(synchronize_session=False)
    )
    session.commit()
    if result.rowcount != 1:
        session.expire_all()
        return token, None
    session.expire_all()
    action = session.get(Action, action_id)
    return token, action


def _apply_effects(session: Session, action: Action, order: Order) -> dict[str, Any]:
    """Apply the local change. Runs only after a confirmed external success."""
    payload = _payload_dict(action)
    if action.type == ActionType.ADD_TRACKING.value:
        order.tracking_number = str(payload["tracking_number"]).strip()
        order.carrier = str(payload["carrier"]).strip()
        if order.shipped_at is None:
            order.shipped_at = utcnow()
        if order.status in {"CREATED", "PENDING"}:
            order.status = "SHIPPED"
        return {"applied": ["tracking_number", "carrier", "shipped_at"]}
    if action.type == ActionType.MESSAGE_BUYER.value:
        session.add(
            BuyerMessage(
                order_id=order.id,
                direction="MERCHANT",
                body=str(payload.get("body", "")).strip(),
                sent_at=utcnow(),
                intent="merchant_followup",
                source=action.source,
                is_demo=order.is_demo,
                demo_run_id=order.demo_run_id,
            )
        )
        session.flush()
        # The order's relationship was already loaded when the "before"
        # snapshot was taken, so expire it, or the "after" snapshot would
        # silently reuse the stale list and report no change.
        session.expire(order, ["messages"])
        return {"applied": ["merchant_message"]}
    if action.type == ActionType.FLAG_FOR_REVIEW.value:
        order.flagged_for_review = True
        return {"applied": ["flagged_for_review"]}
    return {"applied": []}


async def execute(
    session: Session, action_id: int, paypal: PayPalService, *, actor: Actor = Actor.MERCHANT
) -> ExecuteResult:
    """Claim, act, and only then record EXECUTED. See MASTER 4.4."""
    action = session.get(Action, action_id)
    if action is None:
        raise ActionConflict("Action not found.")

    if action.status == ActionStatus.EXECUTED.value:
        return ExecuteResult(action=action, already_executed=True)

    if action.status == ActionStatus.EXECUTING.value:
        # A live claim by another caller, or a stale one. Never execute twice.
        claimed_at = action.claimed_at
        if claimed_at is not None and utcnow() - claimed_at > timedelta(seconds=STALE_CLAIM_SECONDS):
            action.status = ActionStatus.UNKNOWN.value
            action.error = "stale claim recovered: outcome not confirmed"
            audit.record(
                session,
                event="action_unknown",
                actor=Actor.SYSTEM,
                order_id=action.order_id,
                action_id=action.id,
                message="Stale EXECUTING claim marked UNKNOWN; never re-executed",
                detail={"claim_age_seconds": int((utcnow() - claimed_at).total_seconds())},
                source=action.source,
                is_demo=action.is_demo,
                demo_run_id=action.demo_run_id,
                commit=True,
            )
            raise ActionConflict("Action was claimed by another caller; outcome not confirmed.")
        raise ActionConflict("Action is already being executed by another caller.")

    if action.status == ActionStatus.UNKNOWN.value:
        raise ActionConflict("Outcome is not confirmed. Reconcile before doing anything else.")
    if action.status != ActionStatus.APPROVED.value:
        raise ActionConflict(f"Execute requires APPROVED; action is {action.status}.")

    token, claimed = _claim(session, action_id)
    if claimed is None:
        current = session.get(Action, action_id)
        if current is not None and current.status == ActionStatus.EXECUTED.value:
            return ExecuteResult(action=current, already_executed=True)
        raise ActionConflict("Another caller won the claim; no external call was made.")

    action = claimed
    order = session.get(Order, action.order_id)
    if order is None:  # pragma: no cover - FK prevents this
        raise ActionConflict("Action has no order.")

    payload = _payload_dict(action)
    before = _snapshot(order)

    # --- local validation: nothing is sent, so a failure here is FAILED ------
    try:
        validate_payload(action.type, payload)
    except ActionError as exc:
        action.status = ActionStatus.FAILED.value
        action.error = f"validation: {exc}"
        action.claim_token = None
        action.updated_at = utcnow()
        audit.record(
            session,
            event="action_failed",
            actor=actor,
            order_id=order.id,
            action_id=action.id,
            message="Local validation failed before anything was sent",
            detail={"error": str(exc), "classification": "FAILED"},
            source=action.source,
            is_demo=action.is_demo,
            demo_run_id=action.demo_run_id,
        )
        session.commit()
        raise

    # --- external call -------------------------------------------------------
    external: CallResult | None = None
    if action.type == ActionType.ADD_TRACKING.value:
        external = await paypal.add_tracking(
            order_id=order.paypal_order_id or order.order_ref,
            tracking_number=str(payload["tracking_number"]).strip(),
            carrier=str(payload["carrier"]).strip(),
        )

    if external is not None and external.outcome != "EXECUTED":
        action.status = (
            ActionStatus.FAILED.value if external.outcome == "FAILED" else ActionStatus.UNKNOWN.value
        )
        action.error = external.error or external.outcome
        action.result = {"detail": external.detail, "source": external.source}
        action.claim_token = None
        action.updated_at = utcnow()
        action.source = external.source if external.source == "PAYPAL_SANDBOX" else action.source
        audit.record(
            session,
            event="action_failed" if external.outcome == "FAILED" else "action_unknown",
            actor=actor,
            order_id=order.id,
            action_id=action.id,
            message=(
                "External call known to have failed"
                if external.outcome == "FAILED"
                else "External call may have succeeded - outcome not confirmed"
            ),
            detail={"classification": external.outcome, "detail": external.detail},
            source=action.source,
            is_demo=action.is_demo,
            demo_run_id=action.demo_run_id,
        )
        session.commit()
        session.refresh(action)
        return ExecuteResult(action=action)

    # --- confirmed: commit state, diff, result and audit together ------------
    applied = _apply_effects(session, action, order)
    after = _snapshot(order)
    changed_before, changed_after = _diff(before, after)

    action.status = ActionStatus.EXECUTED.value
    action.executed_at = utcnow()
    action.claim_token = None
    action.error = None
    action.before_diff = changed_before
    action.after_diff = changed_after
    action.result = {
        "applied": applied.get("applied", []),
        # `source` is the label the UI must draw for this action: the adapter
        # that served the external call when there was one, and otherwise the
        # action's own provenance (SIMULATED, because nothing external exists).
        "source": external.source if external else action.source,
        # Whether an external system was actually contacted. FLAG_FOR_REVIEW and
        # MESSAGE_BUYER are handled entirely inside this app; without this flag
        # the API shape alone let the UI imply that a local action had been
        # served by PayPal (BUG-0020).
        "external_call": external is not None,
        "external": (external.detail if external else {"note": "local action, no external call"}),
    }
    action.updated_at = utcnow()
    if external is not None and external.source == "PAYPAL_SANDBOX":
        action.source = "PAYPAL_SANDBOX"
        order.source = "PAYPAL_SANDBOX"
    audit.record(
        session,
        event="action_executed",
        actor=actor,
        order_id=order.id,
        action_id=action.id,
        message=f"{action.type} executed and confirmed",
        detail={
            "before": changed_before,
            "after": changed_after,
            "source": action.result["source"],
        },
        source=action.source,
        is_demo=action.is_demo,
        demo_run_id=action.demo_run_id,
    )
    session.commit()
    session.refresh(action)
    return ExecuteResult(action=action)


# ---------------------------------------------------------------------- retry
def retry(session: Session, action: Action, *, actor: Actor = Actor.MERCHANT) -> Action:
    """FAILED -> APPROVED, by explicit human action only. UNKNOWN is refused."""
    if action.status == ActionStatus.UNKNOWN.value:
        raise ActionConflict("Outcome is not confirmed. Reconcile it; do not retry.")
    if action.status != ActionStatus.FAILED.value:
        raise ActionConflict(f"Retry is only allowed from FAILED, not {action.status}.")

    action.status = ActionStatus.APPROVED.value
    action.error = None
    action.claim_token = None
    action.updated_at = utcnow()
    audit.record(
        session,
        event="action_retried",
        actor=actor,
        order_id=action.order_id,
        action_id=action.id,
        message="Merchant retried a failed action; the idempotency key is reused",
        detail={"idempotency_key": action.idempotency_key or idempotency_key_for(action)},
        source=action.source,
        is_demo=action.is_demo,
        demo_run_id=action.demo_run_id,
    )
    session.commit()
    return action


# ------------------------------------------------------------------ reconcile
async def reconcile(
    session: Session,
    action: Action,
    paypal: PayPalService,
    *,
    confirm_not_applied: bool = False,
    actor: Actor = Actor.MERCHANT,
) -> dict[str, Any]:
    """Exactly one outcome: APPLIED, NOT_APPLIED or INDETERMINATE."""
    if action.status != ActionStatus.UNKNOWN.value:
        raise ActionConflict(f"Reconcile is only for UNKNOWN actions, not {action.status}.")

    order = session.get(Order, action.order_id)
    if order is None:  # pragma: no cover
        raise ActionConflict("Action has no order.")

    state, number = await paypal.read_tracking(order_id=order.paypal_order_id or order.order_ref)
    expected = str(_payload_dict(action).get("tracking_number", "")).strip()

    if state == "FOUND" and (not expected or number == expected):
        action.status = ActionStatus.EXECUTED.value
        action.executed_at = utcnow()
        action.reconcile_outcome = ReconcileOutcome.APPLIED.value
        action.result = {
            "reconciled": "APPLIED",
            "read_back_tracking_number": number,
            "source": paypal.source_label,
        }
        action.error = None
        order.tracking_number = number or expected
        order.carrier = order.carrier or str(_payload_dict(action).get("carrier", "") or "") or None
        if order.shipped_at is None:
            order.shipped_at = utcnow()
        audit.record(
            session,
            event="action_reconciled",
            actor=actor,
            order_id=order.id,
            action_id=action.id,
            message="Reconcile: APPLIED - PayPal's read-back shows the tracking number",
            detail={"outcome": "APPLIED", "tracking_number": number},
            source=action.source,
            is_demo=action.is_demo,
            demo_run_id=action.demo_run_id,
        )
        session.commit()
        return {"outcome": "APPLIED", "tracking_number": number, "action_status": action.status}

    if state == "ABSENT":
        if not confirm_not_applied:
            audit.record(
                session,
                event="action_reconcile_refused",
                actor=actor,
                order_id=order.id,
                action_id=action.id,
                message="NOT_APPLIED requires an explicit confirmation flag",
                detail={"outcome": "NOT_APPLIED", "confirmed": False},
                source=action.source,
                is_demo=action.is_demo,
                demo_run_id=action.demo_run_id,
                commit=True,
            )
            raise ActionConflict(
                "The effect appears to be absent, but returning the action to APPROVED "
                "requires {\"confirm_not_applied\": true}."
            )
        action.status = ActionStatus.APPROVED.value
        action.reconcile_outcome = ReconcileOutcome.NOT_APPLIED.value
        action.error = None
        action.claim_token = None
        audit.record(
            session,
            event="action_reconciled",
            actor=actor,
            order_id=order.id,
            action_id=action.id,
            message="Reconcile: NOT_APPLIED confirmed by a human; action is APPROVED again",
            detail={"outcome": "NOT_APPLIED", "confirmed": True},
            source=action.source,
            is_demo=action.is_demo,
            demo_run_id=action.demo_run_id,
        )
        session.commit()
        return {"outcome": "NOT_APPLIED", "action_status": action.status}

    action.reconcile_outcome = ReconcileOutcome.INDETERMINATE.value
    audit.record(
        session,
        event="action_reconciled",
        actor=actor,
        order_id=order.id,
        action_id=action.id,
        message="Reconcile: INDETERMINATE - the outcome could not be established",
        detail={"outcome": "INDETERMINATE"},
        source=action.source,
        is_demo=action.is_demo,
        demo_run_id=action.demo_run_id,
        commit=True,
    )
    return {"outcome": "INDETERMINATE", "action_status": action.status}


def as_dict(action: Action, session: Session | None = None) -> dict[str, Any]:
    """Serialise an action for the API. Payload is always visible (it is the point)."""
    data: dict[str, Any] = {
        "id": action.id,
        "order_id": action.order_id,
        "type": action.type,
        "status": action.status,
        "payload": _payload_dict(action),
        "rationale": action.rationale,
        "proposed_by": action.proposed_by,
        "executed_at": to_z(action.executed_at)
        if action.executed_at
        else None,
        "claimed_at": to_z(action.claimed_at)
        if action.claimed_at
        else None,
        "before": action.before_diff or {},
        "after": action.after_diff or {},
        "result": action.result or {},
        "error": action.error,
        "reconcile_outcome": action.reconcile_outcome,
        "attempts": action.attempts,
        "idempotency_key": action.idempotency_key,
        "source": action.source,
        "is_demo": action.is_demo,
        "demo_run_id": action.demo_run_id,
        "created_at": to_z(action.created_at),
        "updated_at": to_z(action.updated_at),
        "can_execute": action.status == ActionStatus.APPROVED.value,
        "can_retry": action.status == ActionStatus.FAILED.value,
        "can_reconcile": action.status == ActionStatus.UNKNOWN.value,
    }
    return data


def as_dict_list(session: Session, order_id: int) -> list[dict[str, Any]]:
    """Every action for one order, oldest first, in API shape."""
    rows = session.scalars(
        select(Action).where(Action.order_id == order_id).order_by(Action.id)
    ).all()
    return [as_dict(row) for row in rows]


def dump_json(value: Any) -> str:  # pragma: no cover - debugging helper
    return json.dumps(value, default=str, sort_keys=True)


def _unused_guard() -> None:  # pragma: no cover
    """Keeps ``datetime`` imported for type checkers without a runtime cost."""
    _ = datetime
