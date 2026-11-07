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
