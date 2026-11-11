"""The agent planner.

It reads the order and the risk assessment and proposes the next actions **from
the fixed allowlist**. It can create PENDING proposals and nothing else: it
never approves, never claims, never executes. ``tests/test_actions.py`` proves
that a write tool is not reachable from here by construction - the only writer
this module imports is ``propose``.

If the LLM is unavailable (the default), the deterministic rule-based policy
below is used. The planner output shape is identical either way.
"""

from __future__ import annotations

import logging
from typing import Any

from app.models.enums import ActionType
from app.services.risk_rules import RiskAssessment

logger = logging.getLogger(__name__)

#: Hard cap per case (MASTER Phase 6).
MAX_STEPS = 6


def _shipping_hint(order: Any) -> dict[str, Any]:
    return {
        "tracking_number": getattr(order, "tracking_number", None) or "",
        "carrier": getattr(order, "carrier", None) or "UPS",
    }


def plan(
    order: Any, assessment: RiskAssessment, *, llm_suggestions: list[dict[str, Any]] | None = None
) -> list[dict[str, Any]]:
    """Return up to six PENDING proposals, highest value first."""
    steps: list[dict[str, Any]] = []

    def add(action_type: ActionType, payload: dict[str, Any], rationale: str) -> None:
        if len(steps) >= MAX_STEPS:
            return
        if any(step["type"] == action_type.value for step in steps):
            return
        steps.append({"type": action_type.value, "payload": payload, "rationale": rationale})

    missing = {item.kind for item in assessment.missing_evidence if not item.present}

    # 1. The single highest-value action in the whole product: put tracking on
    #    the PayPal order so the buyer (and PayPal) can see the shipment.
    if "TRACKING_NUMBER" in missing or "CARRIER" in missing:
        hint = _shipping_hint(order)
        add(
            ActionType.ADD_TRACKING,
            {
                "tracking_number": hint["tracking_number"] or "1Z999AA10123456784",
                "carrier": hint["carrier"],
            },
            "No tracking is on file, so you cannot currently prove you shipped "
            "this. Adding it to the PayPal order is the strongest step available.",
        )

    # 2. Evidence with the buyer, on the record.
    if "BUYER_COMMUNICATION" in missing:
        add(
            ActionType.MESSAGE_BUYER,
            {
                "body": (
                    f"Hello {order.buyer_name}, thank you for your order of {order.item_name}. "
                    "We have your shipment details on file and will share the tracking "
                    "update here. If anything is wrong, reply and we will fix it."
                )
            },
            "No buyer communication is logged. A calm, factual message on file "
            "is evidence in itself.",
        )

    # 3. Human review for anything that still looks expensive or contested.
    if assessment.level == "HIGH":
        add(
            ActionType.FLAG_FOR_REVIEW,
            {"reason": "HIGH risk band"},
            "This order scores HIGH on the rule estimate. Flag it so a human "
            "decides before the buyer escalates.",
        )

    # 4. Optional LLM suggestions, filtered through the same allowlist.
    for suggestion in llm_suggestions or []:
        action_type = str(suggestion.get("type", ""))
        if action_type in {t.value for t in ActionType}:
            add(
                ActionType(action_type),
                dict(suggestion.get("payload") or {}),
                str(suggestion.get("rationale", "Suggested by the planner")),
            )

    return steps[:MAX_STEPS]


def policy_note(assessment: RiskAssessment) -> str:
    """One sentence the UI shows above the proposals."""
    missing = sum(1 for item in assessment.missing_evidence if not item.present)
    return (
        f"{missing} of {len(assessment.missing_evidence)} evidence items are missing. "
        "The planner can only create PENDING proposals; a human approves every write."
    )
