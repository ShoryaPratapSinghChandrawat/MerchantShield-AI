"""Rule-based risk scoring (Phase 1) - plain English, integer points, testable.

Rules of the house:

* **Integer points internally**, normalised to 0-1 only at the edge. Floats
  accumulating in a loop produce 0.30000000000000004-style scores that look
  arbitrary and are impossible to test exactly.
* **Every reason carries a direction** ("+" raises risk, "-" lowers it) and a
  plain-English sentence. The UI shows them exactly as they are here.
* **Whole-word keyword matching with a negation window**, so "no refund needed"
  cannot trigger the refund/chargeback flag. This is tested directly.
* **Age is only penalised when there is no tracking.** An old, fully tracked
  order is not a risk; an old, untracked one is.

The output is an ESTIMATE built from hand-written rules, not a probability and
not a model. Phase 3 adds a separate ML estimate next to it; this one stays
explainable on purpose.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any

from app.core.timeutil import ensure_utc, to_z, utcnow

#: Thresholds on the normalised 0-1 score.
LOW_MAX = 0.33
MEDIUM_MAX = 0.66

#: Words that flip the meaning of a nearby keyword.
NEGATIONS = frozenset({"no", "not", "never", "without", "none", "nor", "cannot", "cant"})

#: Chargeback / dispute intent keywords. Whole words only, case-insensitive.
DISPUTE_KEYWORDS = (
    "chargeback",
    "refund",
    "dispute",
    "fraud",
    "scam",
    "lawyer",
    "legal",
    "return",
    "cancel",
)


@dataclass(frozen=True)
class Reason:
    """One explainable contributor to the score."""

    code: str
    label: str
    direction: str  # "+" or "-"
    points: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "label": self.label,
            "direction": self.direction,
            "points": self.points,
        }


@dataclass(frozen=True)
class EvidenceCheck:
    """One checklist line: present or missing, plus what to do about it."""

    kind: str
    label: str
    present: bool
    what_to_do: str
    value: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "label": self.label,
            "present": self.present,
            "what_to_do": self.what_to_do,
            "value": self.value,
        }


@dataclass
class RiskAssessment:
    """The complete, explainable output of one scan."""

    score: float
    level: str
    points: int
    reasons: list[Reason] = field(default_factory=list)
    missing_evidence: list[EvidenceCheck] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "risk_score": self.score,
            "risk_level": self.level,
            "risk_points": self.points,
            "reasons": [r.as_dict() for r in self.reasons],
            "missing_evidence": [m.as_dict() for m in self.missing_evidence],
            "estimate_note": (
                "Rule-based ESTIMATE from your own order data. Not a win "
                "probability and not a prediction of any dispute outcome."
            ),
        }


def level_for(score: float) -> str:
    if score < LOW_MAX:
        return "LOW"
    if score < MEDIUM_MAX:
        return "MEDIUM"
    return "HIGH"


def tokenize(text: str) -> list[str]:
    """Lower-case word tokens, punctuation stripped. Whole words only."""
    return re.findall(r"[a-z0-9']+", (text or "").lower())


def keyword_hits(text: str) -> list[str]:
    """Return the dispute keywords that appear *without* a preceding negation.

    The negation window is four tokens, which covers the realistic shapes:
    "no refund needed", "I will not ask for a refund", "never filed a
    chargeback". It deliberately does not try to parse grammar - a simpler
    rule that is testable beats a clever one that is not.
    """
    tokens = tokenize(text)
    hits: list[str] = []
    for index, token in enumerate(tokens):
        if token not in DISPUTE_KEYWORDS:
            continue
        window = tokens[max(0, index - 4) : index]
        if any(word in NEGATIONS or word.endswith("n't") for word in window):
            continue
        if token not in hits:
            hits.append(token)
    return hits


def _documents_age_days(created_at: datetime | None) -> int:
    if created_at is None:
        return 0
    delta = utcnow() - ensure_utc(created_at)
    return max(0, delta.days)


def assess(
    *,
    amount: Decimal | float | str | None,
    currency: str = "USD",
    created_at: datetime | None = None,
    tracking_number: str | None = None,
    carrier: str | None = None,
    shipped_at: datetime | None = None,
    delivered_at: datetime | None = None,
    delivery_confirmed: bool = False,
    item_description_on_file: bool = False,
    policy_on_file: bool = False,
    buyer_country: str | None = None,
    merchant_country: str | None = None,
    is_first_time_buyer: bool = False,
    buyer_negative_history: int = 0,
    category: str = "general",
    message_texts: list[str] | None = None,
) -> RiskAssessment:
    """Score one order. Pure function: no database, no clock beyond ``utcnow``."""
    reasons: list[Reason] = []
    points = 0

    def add(code: str, label: str, direction: str, value: int) -> None:
        nonlocal points
        points += value if direction == "+" else -value
        reasons.append(Reason(code=code, label=label, direction=direction, points=value))

    amount_value = float(amount or 0)
    age_days = _documents_age_days(created_at)
    has_tracking = bool((tracking_number or "").strip())

    # --- value -------------------------------------------------------------
    if amount_value >= 500:
        add(
            "HIGH_VALUE",
            f"High-value order ({amount_value:.2f} {currency}) - the most expensive "
            "kind of dispute to lose.",
            "+",
            18,
        )
    elif amount_value >= 200:
        add("MID_VALUE", f"Above-average order value ({amount_value:.2f} {currency}).", "+", 8)
    else:
        add("LOW_VALUE", f"Modest order value ({amount_value:.2f} {currency}).", "-", 5)

    # --- shipping evidence -------------------------------------------------
    if has_tracking:
        add("TRACKING_ON_FILE", "Tracking number on file - the buyer can see the parcel moving.", "-", 15)
    else:
        add("NO_TRACKING", "No tracking number on file - you cannot currently prove you shipped it.", "+", 20)

    if carrier:
        add("CARRIER_ON_FILE", f"Carrier recorded ({carrier}).", "-", 4)
    else:
        add("NO_CARRIER", "No carrier recorded.", "+", 3)

    if shipped_at is not None:
        add("SHIPPED_DATE", "Shipped date recorded.", "-", 6)
    elif has_tracking:
        add("NO_SHIPPED_DATE", "Tracking exists but no shipped date is recorded.", "+", 4)

    if delivery_confirmed or delivered_at is not None:
        add(
            "DELIVERY_CONFIRMED",
            "Delivery confirmed - the strongest single piece of evidence for "
            "'item not received'.",
            "-",
            14,
        )
    else:
        add("NO_DELIVERY_CONFIRMATION", "No delivery confirmation on file.", "+", 10)

    # --- age (never penalised when the order is tracked) --------------------
    if age_days > 30 and not has_tracking:
        add(
            "AGE_AND_UNTRACKED",
            f"Order is {age_days} days old with no tracking - the evidence window is closing.",
            "+",
            10,
        )
    elif age_days > 30:
        add("AGE_TRACKED", f"Order is {age_days} days old, but it is tracked.", "-", 4)

    # --- buyer profile -----------------------------------------------------
    if is_first_time_buyer:
        add("FIRST_TIME_BUYER", "First-time buyer with no history with you.", "+", 9)
    else:
        add("RETURNING_BUYER", "Returning buyer with a track record.", "-", 6)

    if buyer_country and merchant_country and buyer_country != merchant_country:
        add(
            "COUNTRY_MISMATCH",
            f"Buyer country ({buyer_country}) differs from merchant country ({merchant_country}).",
            "+",
            11,
        )

    negative = max(0, min(100, int(buyer_negative_history or 0)))
    if negative >= 60:
        add("BUYER_NEGATIVE_HIGH", f"Buyer negative-history score {negative}/100.", "+", 15)
    elif negative >= 30:
        add("BUYER_NEGATIVE_MEDIUM", f"Buyer negative-history score {negative}/100.", "+", 7)

    # --- listing / policy --------------------------------------------------
    if item_description_on_file:
        add("ITEM_DESCRIPTION_ON_FILE", "Item description on file - 'not as described' is easier to answer.", "-", 7)
    else:
        add("NO_ITEM_DESCRIPTION", "No item description on file.", "+", 6)

    if policy_on_file:
        add("POLICY_ON_FILE", "Refund and returns policy on file.", "-", 5)
    else:
        add("NO_POLICY", "No refund/returns policy on file.", "+", 4)

    # --- category ----------------------------------------------------------
    if category.lower() in {"electronics", "digital", "jewellery", "luxury"}:
        add("HIGH_RISK_CATEGORY", f"Category '{category}' sees more disputes than average.", "+", 6)

    # --- buyer messages ----------------------------------------------------
    texts = message_texts or []
    hits: list[str] = []
    for text in texts:
        for hit in keyword_hits(text):
            if hit not in hits:
                hits.append(hit)
    if hits:
        add(
            "CHARGEBACK_LANGUAGE",
            "Buyer language already mentions: " + ", ".join(sorted(hits)) + ".",
            "+",
            14,
        )
    elif texts:
        add("CALM_COMMUNICATION", "Buyer messages are calm - no dispute words.", "-", 3)

    # --- clamp + normalise --------------------------------------------------
    points = max(0, min(100, points))
    score = round(points / 100.0, 3)

    return RiskAssessment(
        score=score,
        level=level_for(score),
        points=points,
        reasons=sorted(reasons, key=lambda r: (-r.points, r.code)),
        missing_evidence=evidence_checklist(
            tracking_number=tracking_number,
            carrier=carrier,
            shipped_at=shipped_at,
            delivery_confirmed=delivery_confirmed or delivered_at is not None,
            has_buyer_communication=bool(texts),
            item_description_on_file=item_description_on_file,
            policy_on_file=policy_on_file,
        ),
    )


def evidence_checklist(
    *,
    tracking_number: str | None,
    carrier: str | None,
    shipped_at: datetime | None,
    delivery_confirmed: bool,
    has_buyer_communication: bool,
    item_description_on_file: bool,
    policy_on_file: bool,
) -> list[EvidenceCheck]:
    """The seven-line MISSING EVIDENCE checklist, with a hint per line."""
    return [
        EvidenceCheck(
            kind="TRACKING_NUMBER",
            label="Tracking number",
            present=bool((tracking_number or "").strip()),
            what_to_do="Add the carrier's tracking number to the PayPal order.",
            value=(tracking_number or ""),
        ),
        EvidenceCheck(
            kind="CARRIER",
            label="Carrier",
            present=bool(carrier),
            what_to_do="Record which carrier is handling the parcel.",
            value=(carrier or ""),
        ),
        EvidenceCheck(
            kind="SHIPPED_DATE",
            label="Shipped date",
            present=shipped_at is not None,
            what_to_do="Log the date the parcel left your hands.",
            value=to_z(shipped_at) if shipped_at else "",
        ),
        EvidenceCheck(
            kind="DELIVERY_CONFIRMATION",
            label="Delivery confirmation",
            present=delivery_confirmed,
            what_to_do="Upload the carrier's delivery confirmation or signature.",
        ),
        EvidenceCheck(
            kind="BUYER_COMMUNICATION",
            label="Buyer communication logged",
            present=has_buyer_communication,
            what_to_do="Send the buyer a message here so the thread is on file.",
        ),
        EvidenceCheck(
            kind="ITEM_DESCRIPTION",
            label="Item description / listing on file",
            present=item_description_on_file,
            what_to_do="Attach the listing text and photos you shipped against.",
        ),
        EvidenceCheck(
            kind="POLICY",
            label="Refund / returns policy on file",
            present=policy_on_file,
            what_to_do="Attach your published returns policy.",
        ),
    ]
