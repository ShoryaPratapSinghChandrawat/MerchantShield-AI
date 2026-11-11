"""Shared enumerations.

``SourceLabel`` is the honesty backbone of the whole app (rule R5). It is
defined once, used by the ORM, the API schemas and the UI chip, so the three
can never drift apart.
"""

from __future__ import annotations

from enum import Enum


class SourceLabel(str, Enum):
    """Where a record's data actually came from.

    PAYPAL_SANDBOX
        An actual response from the PayPal Sandbox REST API. Never production.
    SIMULATED
        Behaviour generated locally by MerchantShield itself (for example the
        seeded story orders). No external system was contacted.
    MOCK
        A mock adapter or a canned test response standing in for PayPal.
    """

    PAYPAL_SANDBOX = "PAYPAL_SANDBOX"
    SIMULATED = "SIMULATED"
    MOCK = "MOCK"

    @property
    def human_label(self) -> str:
        return {
            SourceLabel.PAYPAL_SANDBOX: "PayPal Sandbox response",
            SourceLabel.SIMULATED: "Simulated locally",
            SourceLabel.MOCK: "Mock adapter",
        }[self]


class RiskLevel(str, Enum):
    """Coarse band derived from the 0-1 ESTIMATE. Not a probability."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ActionType(str, Enum):
    """The fixed allowlist (MASTER 4.4). Anything else is a 422."""

    ADD_TRACKING = "ADD_TRACKING"
    MESSAGE_BUYER = "MESSAGE_BUYER"
    FLAG_FOR_REVIEW = "FLAG_FOR_REVIEW"


class ActionStatus(str, Enum):
    """The action state machine (MASTER 4.4)."""

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXECUTING = "EXECUTING"
    EXECUTED = "EXECUTED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


class Actor(str, Enum):
    """Who caused an audit row. The agent can never be the actor of a write."""

    MERCHANT = "MERCHANT"
    AGENT = "AGENT"
    SYSTEM = "SYSTEM"


class ReconcileOutcome(str, Enum):
    """Exactly one of these, always (MASTER 4.4)."""

    APPLIED = "APPLIED"
    NOT_APPLIED = "NOT_APPLIED"
    INDETERMINATE = "INDETERMINATE"


class DisputeStatus(str, Enum):
    OPEN = "OPEN"
    UNDER_REVIEW = "UNDER_REVIEW"
    SUBMITTED = "SUBMITTED"
    RESOLVED = "RESOLVED"


class DraftStatus(str, Enum):
    DRAFT = "DRAFT"
    APPROVED = "APPROVED"
    SUBMITTED = "SUBMITTED"


#: Every action type the engine will accept. Enforced on propose AND execute.
ACTION_ALLOWLIST: frozenset[str] = frozenset(t.value for t in ActionType)
