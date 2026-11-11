"""Transparent evidence-strength checklist (Phase 3) - 0-100, no ML.

This is deliberately *not* a model. It is a weighted list, printed in full in
the UI, so a merchant can see exactly why a number moved and what to upload.
It is also not a win prediction: there is no dispute-outcome data in this
project, so any percentage claiming otherwise would be invented.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.services.risk_rules import EvidenceCheck

#: Weights must sum to 100. Tested.
WEIGHTS: dict[str, int] = {
    "TRACKING_NUMBER": 25,
    "DELIVERY_CONFIRMATION": 20,
    "SHIPPED_DATE": 15,
    "CARRIER": 10,
    "BUYER_COMMUNICATION": 10,
    "ITEM_DESCRIPTION": 10,
    "POLICY": 10,
}


@dataclass
class EvidenceScore:
    score: int
    present: list[EvidenceCheck]
    missing: list[EvidenceCheck]

    def as_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "max": 100,
            "present": [p.label for p in self.present],
            "missing": [m.label for m in self.missing],
            "what_to_upload": [{"label": m.label, "hint": m.what_to_do} for m in self.missing],
            "note": (
                "A checklist of documents you hold. Not a win probability and "
                "not machine learning."
            ),
        }


def score_from_checks(checks: list[EvidenceCheck]) -> EvidenceScore:
    """Sum the weights of the present items. Missing items contribute nothing."""
    total = 0
    present: list[EvidenceCheck] = []
    missing: list[EvidenceCheck] = []
    for check in checks:
        weight = WEIGHTS.get(check.kind, 0)
        if check.present:
            total += weight
            present.append(check)
        else:
            missing.append(check)
    return EvidenceScore(score=max(0, min(100, total)), present=present, missing=missing)
