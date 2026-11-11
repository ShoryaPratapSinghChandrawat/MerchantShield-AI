"""Order read models, scanning, and the narrative the UI renders.

Nothing here computes a new truth: the rule score comes from
``services/risk_rules.py``, the checklist from ``services/evidence_score.py``
and the ML number from ``services/risk_model.py``. This module only assembles
them, caches the band on the row, and writes the audit trail.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.timeutil import to_z, utcnow
from app.models.action import Action
from app.models.audit import AuditLog
from app.models.dispute import Dispute
from app.models.enums import ActionStatus, Actor, RiskLevel
from app.models.order import BuyerMessage, EvidenceItem, Order
from app.services import actions as action_service
from app.services import audit, evidence_score, risk_model, risk_rules

logger = logging.getLogger(__name__)


def message_texts(session: Session, order_id: int) -> list[str]:
    return list(
        session.scalars(
            select(BuyerMessage.body).where(BuyerMessage.order_id == order_id).order_by(BuyerMessage.id)
        )
    )


def assess(session: Session, order: Order) -> risk_rules.RiskAssessment:
    """Pure rule assessment over the persisted order."""
    return risk_rules.assess(
        amount=order.amount,
        currency=order.currency,
        created_at=order.created_at,
        tracking_number=order.tracking_number,
        carrier=order.carrier,
        shipped_at=order.shipped_at,
        delivered_at=order.delivered_at,
        delivery_confirmed=order.delivery_confirmed,
        item_description_on_file=order.item_description_on_file,
        policy_on_file=order.policy_on_file,
        buyer_country=order.buyer_country,
        merchant_country=order.merchant_country,
        is_first_time_buyer=order.is_first_time_buyer,
        buyer_negative_history=order.buyer_negative_history,
        category=order.category,
        message_texts=message_texts(session, order.id),
    )


def scan(session: Session, order: Order, *, write_audit: bool = True) -> dict[str, Any]:
    """Score an order, cache the band, audit the scan, return the full payload."""
    assessment = assess(session, order)
    order.risk_score = assessment.score
    order.risk_level = assessment.level
    order.updated_at = utcnow()
    if write_audit:
        audit.record(
            session,
            event="order_scanned",
            order_id=order.id,
            message=f"Rule scan: {assessment.level} ({assessment.points}/100 points)",
            detail={
                "risk_score": assessment.score,
                "risk_level": assessment.level,
                "points": assessment.points,
            },
            source=order.source,
            is_demo=order.is_demo,
            demo_run_id=order.demo_run_id,
        )
    session.commit()

    return {
        **assessment.as_dict(),
        "ml_risk_estimate": risk_model.predict(order),
        "evidence_strength": evidence_score.score_from_checks(assessment.missing_evidence).as_dict(),
    }


def serialise_order(order: Order) -> dict[str, Any]:
    """The flat order shape used by lists, drawers and the audit page."""
    return {
        "id": order.id,
        "order_ref": order.order_ref,
        "buyer_name": order.buyer_name,
        "buyer_email": order.buyer_email,
        "item_name": order.item_name,
        "amount": f"{order.amount:.2f}",
        "currency": order.currency,
        "status": order.status,
        "tracking_number": order.tracking_number,
        "carrier": order.carrier,
        "shipped_at": to_z(order.shipped_at) if order.shipped_at else None,
        "delivered_at": to_z(order.delivered_at) if order.delivered_at else None,
        "delivery_confirmed": order.delivery_confirmed,
        "item_description_on_file": order.item_description_on_file,
        "policy_on_file": order.policy_on_file,
        "buyer_country": order.buyer_country,
        "merchant_country": order.merchant_country,
        "is_first_time_buyer": order.is_first_time_buyer,
        "buyer_negative_history": order.buyer_negative_history,
        "category": order.category,
        "flagged_for_review": order.flagged_for_review,
        "paypal_order_id": order.paypal_order_id,
        "risk_score": float(order.risk_score) if order.risk_score is not None else None,
        "risk_level": order.risk_level,
        "source": order.source,
        "is_demo": order.is_demo,
        "demo_run_id": order.demo_run_id,
        "created_at": to_z(order.created_at),
        "updated_at": to_z(order.updated_at),
    }


def summary(session: Session, order: Order) -> dict[str, Any]:
    """One row for the orders grid and the dashboard's needs-attention list."""
    assessment = assess(session, order)
    missing = [item.label for item in assessment.missing_evidence if not item.present]
    open_actions = session.scalars(
        select(Action).where(
            Action.order_id == order.id,
            Action.status.in_([ActionStatus.PENDING.value, ActionStatus.APPROVED.value]),
        )
    ).all()
    return {
        **serialise_order(order),
        "risk_score": assessment.score,
        "risk_level": assessment.level,
        "reasons": [reason.as_dict() for reason in assessment.reasons],
        "missing_evidence": missing,
        "open_actions": len(open_actions),
        "evidence_strength": evidence_score.score_from_checks(
            assessment.missing_evidence
        ).score,
    }


def detail(session: Session, order: Order) -> dict[str, Any]:
    """Everything the order drawer needs, in one payload."""
    assessment = assess(session, order)
    actions = list(
        session.scalars(
            select(Action).where(Action.order_id == order.id).order_by(Action.id.desc())
        )
    )
    messages = list(
        session.scalars(
            select(BuyerMessage)
            .where(BuyerMessage.order_id == order.id)
            .order_by(BuyerMessage.sent_at)
        )
    )
    evidence = list(
        session.scalars(select(EvidenceItem).where(EvidenceItem.order_id == order.id))
    )
    audit_rows = list(
        session.scalars(
            select(AuditLog)
            .where(AuditLog.order_id == order.id)
            .order_by(AuditLog.id.desc())
            .limit(50)
        )
    )
    disputes = list(
        session.scalars(select(Dispute).where(Dispute.order_id == order.id).order_by(Dispute.id))
    )

    return {
        "order": serialise_order(order),
        "risk": assessment.as_dict(),
        "ml_risk_estimate": risk_model.predict(order),
        "evidence_strength": evidence_score.score_from_checks(
            assessment.missing_evidence
        ).as_dict(),
        "actions": [action_service.as_dict(a) for a in actions],
        "messages": [
            {
                "id": m.id,
                "direction": m.direction,
                "body": m.body,
                "sent_at": to_z(m.sent_at),
                "intent": m.intent,
                "source": m.source,
            }
            for m in messages
        ],
        "evidence_items": [
            {"id": e.id, "kind": e.kind, "value": e.value, "source": e.source} for e in evidence
        ],
        "audit": [audit_row_dict(row) for row in audit_rows],
        "disputes": [
            {
                "id": d.id,
                "reason": d.reason,
                "status": d.status,
                "amount": f"{d.amount:.2f}",
                "evidence_strength": d.evidence_strength,
                "source": d.source,
            }
            for d in disputes
        ],
    }


def audit_row_dict(row: AuditLog) -> dict[str, Any]:
    return {
        "id": row.id,
        "order_id": row.order_id,
        "action_id": row.action_id,
        "dispute_id": row.dispute_id,
        "actor": row.actor,
        "event": row.event,
        "message": row.message,
        "detail": row.detail or {},
        "source": row.source,
        "is_demo": row.is_demo,
        "demo_run_id": row.demo_run_id,
        "created_at": to_z(row.created_at),
    }


def dashboard(session: Session) -> dict[str, Any]:
    """Measured facts only: counts, sums and bands. No fabricated percentages."""
    orders = list(session.scalars(select(Order).order_by(Order.id)))
    bands = {RiskLevel.LOW.value: 0, RiskLevel.MEDIUM.value: 0, RiskLevel.HIGH.value: 0}
    flagged_value = 0.0
    needs_attention: list[dict[str, Any]] = []

    for order in orders:
        assessment = assess(session, order)
        bands[assessment.level] += 1
        if assessment.level in {RiskLevel.HIGH.value, RiskLevel.MEDIUM.value}:
            flagged_value += float(order.amount)
            if assessment.level == RiskLevel.HIGH.value:
                needs_attention.append(summary(session, order))

    needs_attention.sort(key=lambda row: (-row["risk_score"], row["id"]))
    actions_rows = list(session.scalars(select(Action)))
    pending = sum(1 for a in actions_rows if a.status == ActionStatus.PENDING.value)
    executed = sum(1 for a in actions_rows if a.status == ActionStatus.EXECUTED.value)

    return {
        "orders_total": len(orders),
        "risk_bands": bands,
        "order_value_flagged": round(flagged_value, 2),
        "actions_pending": pending,
        "actions_executed": executed,
        "needs_attention": needs_attention[:6],
        "measured_note": (
            "Every number here is a count or a sum of your own order data. There "
            "is no win probability and no money-protected figure anywhere."
        ),
    }


def trigger_agent(session: Session, order: Order, *, actor: Actor = Actor.AGENT) -> dict[str, Any]:
    """Run the planner and create PENDING proposals. It can never do more."""
    from app.services import agent

    assessment = assess(session, order)
    steps = agent.plan(order, assessment)
    created: list[dict[str, Any]] = []
    for step in steps:
        action, was_created = action_service.propose(
            session,
            order=order,
            action_type=step["type"],
            payload=step["payload"],
            rationale=step["rationale"],
            actor=actor,
            source=order.source,
        )
        created.append({**action_service.as_dict(action), "created": was_created})
    audit.record(
        session,
        event="agent_planned",
        actor=actor,
        order_id=order.id,
        message=f"Planner proposed {len(created)} step(s); all PENDING",
        detail={"steps": [c["type"] for c in created]},
        source=order.source,
        is_demo=order.is_demo,
        demo_run_id=order.demo_run_id,
        commit=True,
    )
    return {"note": agent.policy_note(assessment), "proposals": created}
