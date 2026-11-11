"""Dispute defence: evidence packet, versioned draft, approve, submit.

Submission is **SIMULATED** unless a real PayPal response was verified. The API
says so in the payload (``"submission_mode": "SIMULATED"``) and the UI says so
in words, because a merchant has to be able to tell the difference.

The draft's ``origin`` ("AI draft" / "Template draft") is stored per draft, not
recomputed at render time, so the label cannot drift from what actually
produced the text.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.timeutil import to_z, utcnow
from app.models.dispute import Dispute, DisputeDraft
from app.models.enums import Actor, DisputeStatus, DraftStatus, SourceLabel
from app.models.order import Order
from app.services import evidence_score, llm, orders as order_service, risk_rules
from app.services import audit

logger = logging.getLogger(__name__)

SUBMISSION_MODE = "SIMULATED"


def ensure_seeded(session: Session, order: Order) -> Dispute:
    """Create the demo dispute for an order if it does not exist."""
    existing = session.scalars(
        select(Dispute).where(Dispute.order_id == order.id).order_by(Dispute.id)
    ).first()
    if existing is not None:
        return existing

    assessment = order_service.assess(session, order)
    dispute = Dispute(
        order_id=order.id,
        paypal_dispute_id=None,
        reason="MERCHANDISE_OR_SERVICE_NOT_RECEIVED"
        if not order.delivery_confirmed
        else "ITEM_NOT_AS_DESCRIBED",
        status=DisputeStatus.OPEN.value,
        amount=order.amount,
        currency=order.currency,
        evidence_strength=evidence_score.score_from_checks(assessment.missing_evidence).score,
        buyer_claim=(
            "The buyer says the order did not arrive as expected and has asked "
            "for a refund."
        ),
        source=SourceLabel.SIMULATED.value,
        is_demo=order.is_demo,
        demo_run_id=order.demo_run_id,
    )
    session.add(dispute)
    session.flush()
    audit.record(
        session,
        event="dispute_opened",
        order_id=order.id,
        dispute_id=dispute.id,
        message="SIMULATED dispute opened for the demo",
        detail={"reason": dispute.reason, "source": dispute.source},
        source=dispute.source,
        is_demo=dispute.is_demo,
        demo_run_id=dispute.demo_run_id,
    )
    session.commit()
    return dispute


def packet(session: Session, dispute: Dispute) -> dict[str, Any]:
    """The evidence packet: what we can prove, what we cannot, and what to upload."""
    order = session.get(Order, dispute.order_id)
    if order is None:  # pragma: no cover - FK prevents this
        raise ValueError("dispute has no order")

    assessment = order_service.assess(session, order)
    score = evidence_score.score_from_checks(assessment.missing_evidence)
    dispute.evidence_strength = score.score
    session.commit()

    return {
        "dispute_id": dispute.id,
        "order_ref": order.order_ref,
        "reason": dispute.reason,
        "status": dispute.status,
        "amount": f"{dispute.amount:.2f}",
        "buyer_claim": dispute.buyer_claim,
        "evidence_strength": score.as_dict(),
        "evidence": [
            {
                "kind": check.kind,
                "label": check.label,
                "present": check.present,
                "value": check.value,
                "what_to_do": check.what_to_do,
            }
            for check in assessment.missing_evidence
        ],
        "timeline": [
            {"label": "Order created", "at": to_z(order.created_at)},
            *(
                [{"label": "Shipped", "at": to_z(order.shipped_at)}]
                if order.shipped_at
                else []
            ),
            *(
                [{"label": "Delivered", "at": to_z(order.delivered_at)}]
                if order.delivered_at
                else []
            ),
        ],
        "source": dispute.source,
        "note": (
            "An evidence checklist, not a prediction. It counts documents you "
            "hold; it does not estimate any outcome."
        ),
    }


def facts_for_draft(session: Session, dispute: Dispute) -> dict[str, Any]:
    """The ONLY facts a draft is allowed to use."""
    order = session.get(Order, dispute.order_id)
    assert order is not None
    assessment = order_service.assess(session, order)
    missing = [item.label for item in assessment.missing_evidence if not item.present]

    def _summary(prefix: str, value: str | None) -> str | None:
        return f"{prefix}: {value}" if value else None

    return {
        "order_ref": order.order_ref,
        "buyer_name": order.buyer_name,
        "item_name": order.item_name,
        "amount": f"{order.amount:.2f}",
        "currency": order.currency,
        "buyer_claim": dispute.buyer_claim,
        "tracking_summary": _summary("Tracking number", order.tracking_number),
        "delivery_summary": _summary(
            "Delivery confirmed",
            to_z(order.delivered_at) if order.delivered_at else None,
        ),
        "communication_summary": _summary(
            "Buyer communication logged",
            f"{len(order.messages)} message(s)" if order.messages else None,
        ),
        "policy_summary": "Refund policy on file" if order.policy_on_file else None,
        "shipping_summary": (
            f"Tracking {order.tracking_number} with {order.carrier}."
            if order.tracking_number
            else "Shipping details are being prepared."
        ),
        "missing_evidence": missing,
    }


async def create_draft(
    session: Session, dispute: Dispute, *, body: str | None = None, actor: Actor = Actor.MERCHANT
) -> DisputeDraft:
    """Draft a response. Human edits are stored as a new version, never overwriting."""
    facts = facts_for_draft(session, dispute)
    previous = list(
        session.scalars(
            select(DisputeDraft)
            .where(DisputeDraft.dispute_id == dispute.id)
            .order_by(DisputeDraft.version.desc())
        )
    )
    version = (previous[0].version + 1) if previous else 1

    if body is not None:
        draft = DisputeDraft(
            dispute_id=dispute.id,
            version=version,
            body=body.strip(),
            origin="Merchant edit",
            strategy_note="Edited by the merchant before approval.",
            missing_evidence=facts["missing_evidence"],
            source=dispute.source,
            is_demo=dispute.is_demo,
            demo_run_id=dispute.demo_run_id,
        )
        guard_triggered = False
    else:
        result = await llm.draft_dispute_response(facts)
        draft = DisputeDraft(
            dispute_id=dispute.id,
            version=version,
            body=str(result.payload.get("body", "")),
            origin=result.origin,
            strategy_note=str(result.payload.get("strategy_note", "")),
            missing_evidence=list(result.payload.get("missing_evidence") or facts["missing_evidence"]),
            source=dispute.source,
            is_demo=dispute.is_demo,
            demo_run_id=dispute.demo_run_id,
        )
        guard_triggered = result.guard_triggered
        audit.record(
            session,
            event="draft_created",
            actor=actor,
            order_id=dispute.order_id,
            dispute_id=dispute.id,
            message=f"Draft v{version} created ({result.origin})",
            detail={
                "origin": result.origin,
                "provider": result.provider,
                "fallback_reason": result.fallback_reason,
            },
            source=dispute.source,
            is_demo=dispute.is_demo,
            demo_run_id=dispute.demo_run_id,
        )
        if guard_triggered:
            audit.record(
                session,
                event="hallucination_guard_triggered",
                actor=Actor.SYSTEM,
                order_id=dispute.order_id,
                dispute_id=dispute.id,
                message="Model output invented facts; the template was used instead",
                detail={"invented": result.invented, "raw": result.raw[:500]},
                source=dispute.source,
                is_demo=dispute.is_demo,
                demo_run_id=dispute.demo_run_id,
            )

    session.add(draft)
    if dispute.status == DisputeStatus.OPEN.value:
        dispute.status = DisputeStatus.UNDER_REVIEW.value
    session.commit()
    session.refresh(draft)
    return draft


def draft_payload(draft: DisputeDraft) -> dict[str, Any]:
    """One draft, serialised. Every endpoint that returns a draft uses this."""
    return {
        "id": draft.id,
        "dispute_id": draft.dispute_id,
        "draft_id": draft.id,
        "version": draft.version,
        "body": draft.body,
        "origin": draft.origin,
        "strategy_note": draft.strategy_note,
        "missing_evidence": list(draft.missing_evidence or []),
        "status": draft.status,
        "created_at": to_z(draft.created_at),
        "label": "AI-generated, please review" if draft.origin == llm.ORIGIN_AI else None,
    }


def approve_draft(session: Session, draft: DisputeDraft, *, actor: Actor = Actor.MERCHANT) -> DisputeDraft:
    if draft.status == DraftStatus.SUBMITTED.value:
        raise ValueError("Draft has already been submitted.")
    draft.status = DraftStatus.APPROVED.value
    audit.record(
        session,
        event="draft_approved",
        actor=actor,
        dispute_id=draft.dispute_id,
        message=f"Draft v{draft.version} approved",
        detail={"origin": draft.origin},
        source=draft.source,
        is_demo=draft.is_demo,
        demo_run_id=draft.demo_run_id,
        commit=True,
    )
    return draft


def submit(session: Session, dispute: Dispute, *, actor: Actor = Actor.MERCHANT) -> dict[str, Any]:
    """Submit the approved draft. SIMULATED until a real response is verified."""
    approved = session.scalars(
        select(DisputeDraft)
        .where(DisputeDraft.dispute_id == dispute.id, DisputeDraft.status == DraftStatus.APPROVED.value)
        .order_by(DisputeDraft.version.desc())
    ).first()
    if approved is None:
        raise ValueError("No approved draft to submit.")

    settings = get_settings()
    mode = SUBMISSION_MODE
    result = {
        "submission_mode": mode,
        "source": SourceLabel.SIMULATED.value,
        "note": (
            "SIMULATED submission: no PayPal dispute API call was made. This app "
            "only claims LIVE when a real Sandbox response was received and saved."
        ),
        "draft_version": approved.version,
        "origin": approved.origin,
        "paypal_mode": settings.paypal_mode,
    }
    dispute.status = DisputeStatus.SUBMITTED.value
    dispute.submitted_at = utcnow()
    dispute.submit_result = result
    approved.status = DraftStatus.SUBMITTED.value
    approved.submitted_at = utcnow()
    audit.record(
        session,
        event="dispute_submitted",
        actor=actor,
        order_id=dispute.order_id,
        dispute_id=dispute.id,
        message="SIMULATED dispute submission recorded",
        detail=result,
        source=dispute.source,
        is_demo=dispute.is_demo,
        demo_run_id=dispute.demo_run_id,
    )
    session.commit()
    return result


def serialise(dispute: Dispute, session: Session) -> dict[str, Any]:
    order = session.get(Order, dispute.order_id)
    drafts = list(
        session.scalars(
            select(DisputeDraft)
            .where(DisputeDraft.dispute_id == dispute.id)
            .order_by(DisputeDraft.version.desc())
        )
    )
    return {
        "id": dispute.id,
        "order_id": dispute.order_id,
        "order_ref": order.order_ref if order else None,
        "reason": dispute.reason,
        "status": dispute.status,
        "amount": f"{dispute.amount:.2f}",
        "currency": dispute.currency,
        "evidence_strength": dispute.evidence_strength,
        "buyer_claim": dispute.buyer_claim,
        "opened_at": to_z(dispute.opened_at),
        "submitted_at": to_z(dispute.submitted_at) if dispute.submitted_at else None,
        "submit_result": dispute.submit_result,
        "source": dispute.source,
        "is_demo": dispute.is_demo,
        "demo_run_id": dispute.demo_run_id,
        "drafts": [draft_payload(d) for d in drafts],
    }
