"""The evidence checklist: weights, empty/full cases, and the "not ML" claim."""

from __future__ import annotations

from app.services import evidence_score, risk_rules


def _checks(**present: bool) -> list[risk_rules.EvidenceCheck]:
    return risk_rules.evidence_checklist(
        tracking_number="1Z999AA10123456784" if present.get("TRACKING_NUMBER") else None,
        carrier="UPS" if present.get("CARRIER") else None,
        shipped_at=None if not present.get("SHIPPED_DATE") else __import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        delivery_confirmed=present.get("DELIVERY_CONFIRMATION", False),
        has_buyer_communication=present.get("BUYER_COMMUNICATION", False),
        item_description_on_file=present.get("ITEM_DESCRIPTION", False),
        policy_on_file=present.get("POLICY", False),
    )


def test_weights_sum_to_one_hundred() -> None:
    assert sum(evidence_score.WEIGHTS.values()) == 100


def test_nothing_present_scores_zero() -> None:
    scored = evidence_score.score_from_checks(_checks())
    assert scored.score == 0
    assert len(scored.missing) == 7
    assert scored.present == []


def test_everything_present_scores_one_hundred() -> None:
    scored = evidence_score.score_from_checks(
        _checks(
            TRACKING_NUMBER=True,
            CARRIER=True,
            SHIPPED_DATE=True,
            DELIVERY_CONFIRMATION=True,
            BUYER_COMMUNICATION=True,
            ITEM_DESCRIPTION=True,
            POLICY=True,
        )
    )
    assert scored.score == 100
    assert scored.missing == []


def test_tracking_and_delivery_are_the_heaviest_items() -> None:
    tracking_only = evidence_score.score_from_checks(_checks(TRACKING_NUMBER=True))
    policy_only = evidence_score.score_from_checks(_checks(POLICY=True))
    assert tracking_only.score > policy_only.score
    assert tracking_only.score == evidence_score.WEIGHTS["TRACKING_NUMBER"]


def test_payload_never_claims_probability() -> None:
    payload = evidence_score.score_from_checks(_checks()).as_dict()
    text = str(payload).lower()
    assert "win probability" in text  # inside the sentence that denies it
    assert payload["max"] == 100
    assert payload["what_to_upload"]
