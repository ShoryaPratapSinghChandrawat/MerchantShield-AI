"""Phase 1 rules: one test per rule, thresholds, negation, and the age trap."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.services import risk_rules


def _base(**overrides: object) -> risk_rules.RiskAssessment:
    params: dict[str, object] = {
        "amount": Decimal("50.00"),
        "created_at": datetime.now(timezone.utc) - timedelta(days=2),
        "tracking_number": None,
        "carrier": None,
        "shipped_at": None,
        "delivered_at": None,
        "delivery_confirmed": False,
        "item_description_on_file": False,
        "policy_on_file": False,
        "buyer_country": "US",
        "merchant_country": "US",
        "is_first_time_buyer": False,
        "buyer_negative_history": 0,
        "category": "general",
        "message_texts": [],
    }
    params.update(overrides)
    return risk_rules.assess(**params)  # type: ignore[arg-type]


def _codes(assessment: risk_rules.RiskAssessment) -> set[str]:
    return {reason.code for reason in assessment.reasons}


# --------------------------------------------------------------------- basics
def test_score_is_between_zero_and_one() -> None:
    for assessment in (_base(), _base(amount=Decimal("9999.00"), is_first_time_buyer=True)):
        assert 0.0 <= assessment.score <= 1.0
        assert assessment.points == round(assessment.score * 100)


def test_every_reason_carries_a_direction_and_plain_english() -> None:
    assessment = _base(amount=Decimal("900.00"), is_first_time_buyer=True)
    assert assessment.reasons
    for reason in assessment.reasons:
        assert reason.direction in {"+", "-"}
        assert len(reason.label) > 10
        assert " " in reason.label


def test_thresholds_map_to_the_documented_bands() -> None:
    assert risk_rules.level_for(0.0) == "LOW"
    assert risk_rules.level_for(0.329) == "LOW"
    assert risk_rules.level_for(0.33) == "MEDIUM"
    assert risk_rules.level_for(0.659) == "MEDIUM"
    assert risk_rules.level_for(0.66) == "HIGH"
    assert risk_rules.level_for(1.0) == "HIGH"


# ---------------------------------------------------------------------- rules
def test_missing_tracking_raises_and_present_tracking_lowers() -> None:
    assert "NO_TRACKING" in _codes(_base(tracking_number=None))
    tracked = _base(tracking_number="1Z999AA10123456784", carrier="UPS")
    assert "TRACKING_ON_FILE" in _codes(tracked)
    assert tracked.score < _base().score


def test_high_value_order_is_flagged() -> None:
    codes = _codes(_base(amount=Decimal("1500.00")))
    assert "HIGH_VALUE" in codes


def test_first_time_buyer_and_country_mismatch_raise_the_score() -> None:
    assessment = _base(is_first_time_buyer=True, buyer_country="IT", merchant_country="US")
    codes = _codes(assessment)
    assert "FIRST_TIME_BUYER" in codes
    assert "COUNTRY_MISMATCH" in codes
    assert assessment.score > _base().score


def test_delivery_confirmation_is_the_strongest_negative() -> None:
    confirmed = _base(
        tracking_number="1Z999AA10123456784",
        carrier="UPS",
        delivered_at=datetime.now(timezone.utc) - timedelta(days=1),
        delivery_confirmed=True,
    )
    reasons = {reason.code: reason for reason in confirmed.reasons}
    assert reasons["DELIVERY_CONFIRMED"].points == 14
    assert reasons["DELIVERY_CONFIRMED"].direction == "-"


def test_age_is_not_penalised_when_the_order_has_tracking() -> None:
    """The explicit rule in MASTER section 9 PHASE 1."""
    old = datetime.now(timezone.utc) - timedelta(days=58)
    untracked = _base(created_at=old, tracking_number=None)
    tracked = _base(
        created_at=old,
        tracking_number="1Z999AA10123456784",
        carrier="UPS",
        shipped_at=old,
    )

    assert "AGE_AND_UNTRACKED" in _codes(untracked)
    assert "AGE_AND_UNTRACKED" not in _codes(tracked)
    assert "AGE_TRACKED" in _codes(tracked)


def test_buyer_negative_history_bands() -> None:
    assert "BUYER_NEGATIVE_HIGH" in _codes(_base(buyer_negative_history=90))
    assert "BUYER_NEGATIVE_MEDIUM" in _codes(_base(buyer_negative_history=45))
    assert "BUYER_NEGATIVE_HIGH" not in _codes(_base(buyer_negative_history=10))


def test_documents_on_file_lower_the_score() -> None:
    documented = _base(item_description_on_file=True, policy_on_file=True)
    assert "ITEM_DESCRIPTION_ON_FILE" in _codes(documented)
    assert "POLICY_ON_FILE" in _codes(documented)
    assert documented.score < _base().score


# ------------------------------------------------------------------ negation
def test_chargeback_language_raises_the_score() -> None:
    assessment = _base(message_texts=["I will file a chargeback with my bank."])
    assert "CHARGEBACK_LANGUAGE" in _codes(assessment)


def test_negated_chargeback_language_does_not_raise() -> None:
    """'no refund needed' must not trigger a refund flag (MASTER section 9)."""
    assessment = _base(message_texts=["Thanks - no refund needed, it arrived safely."])
    codes = _codes(assessment)
    assert "CHARGEBACK_LANGUAGE" not in codes
    assert "CALM_COMMUNICATION" in codes


def test_negation_window_covers_not_and_never() -> None:
    assert risk_rules.keyword_hits("I will not ask for a refund") == []
    assert risk_rules.keyword_hits("never filed a chargeback") == []
    assert risk_rules.keyword_hits("I want a refund") == ["refund"]


def test_keyword_matching_is_whole_word_only() -> None:
    # "returnable" and "cancellation" contain keywords but are not them.
    assert risk_rules.keyword_hits("The returnable packaging is fine") == []
    assert risk_rules.keyword_hits("No cancellation needed") == []


# --------------------------------------------------------------- checklist
def test_checklist_has_seven_lines_each_with_a_hint() -> None:
    assessment = _base()
    kinds = [item.kind for item in assessment.missing_evidence]
    assert kinds == [
        "TRACKING_NUMBER",
        "CARRIER",
        "SHIPPED_DATE",
        "DELIVERY_CONFIRMATION",
        "BUYER_COMMUNICATION",
        "ITEM_DESCRIPTION",
        "POLICY",
    ]
    for item in assessment.missing_evidence:
        assert item.what_to_do
        assert item.present is False
        assert item.label


def test_checklist_marks_present_items_as_present() -> None:
    assessment = _base(
        tracking_number="1Z999AA10123456784",
        carrier="UPS",
        shipped_at=datetime.now(timezone.utc) - timedelta(days=3),
        delivery_confirmed=True,
        item_description_on_file=True,
        policy_on_file=True,
        message_texts=["hello"],
    )
    assert all(item.present for item in assessment.missing_evidence)


def test_assessment_is_json_ready() -> None:
    payload = _base().as_dict()
    assert set(payload) >= {"risk_score", "risk_level", "reasons", "missing_evidence"}
    assert "estimate_note" in payload
    assert "win probability" in payload["estimate_note"]  # it denies it, in words
