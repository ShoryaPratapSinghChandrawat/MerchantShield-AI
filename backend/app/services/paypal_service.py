"""The PayPal facade: one place that decides LIVE vs MOCK and classifies outcomes.

Every external call in the app goes through here. The classification is the
whole point (MASTER 4.4):

FAILED  - known NOT to have happened: local validation, connection refused,
          DNS failure, connect timeout, or a PayPal 4xx rejection.
UNKNOWN - may have happened: read timeout, connection reset, any 5xx, a crash
          after sending. Never retried automatically.

The facade never raises into the API. A PayPal outage produces a labelled
result, not a 500.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Literal

from app.core.config import Settings, get_settings
from app.services.paypal_client import (
    PayPalClient,
    PayPalConnectionError,
    PayPalError,
    PayPalRequestRejected,
    PayPalUnknownOutcome,
)
from app.services.paypal_mock import PayPalMock

logger = logging.getLogger(__name__)

Outcome = Literal["EXECUTED", "FAILED", "UNKNOWN"]
ReconcileOutcome = Literal["APPLIED", "NOT_APPLIED", "INDETERMINATE"]


@dataclass
class CallResult:
    """The single shape every PayPal interaction returns."""

    outcome: Outcome
    source: str  # PAYPAL_SANDBOX | MOCK
    detail: dict[str, Any]
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.outcome == "EXECUTED"


def _sanitize(text: str, limit: int = 300) -> str:
    """Trim and strip anything that could be a credential or a token."""
    cleaned = " ".join(str(text).split())
    for marker in ("access_token", "Bearer ", "client_secret"):
        cleaned = cleaned.replace(marker, "[redacted]")
    return cleaned[:limit]


class PayPalService:
    """Mode-aware facade. One instance per process, created lazily."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.mock = PayPalMock()
        self.client: PayPalClient | None = None
        self.mode: Literal["live-sandbox", "mock"] = "mock"
        self._configure()

    # ------------------------------------------------------------------ mode
    def _configure(self) -> None:
        s = self.settings
        if s.paypal_mode == "mock":
            self.mode = "mock"
            return
        if s.has_paypal_credentials:
            self.client = PayPalClient(
                base_url=s.paypal_base_url,
                client_id=s.paypal_client_id or "",
                client_secret=s.paypal_client_secret or "",
            )
            self.mode = "live-sandbox"
            return
        if s.paypal_mode == "sandbox":
            logger.warning(
                "PAYPAL_MODE=sandbox but no credentials are configured; falling "
                "back to MOCK. Every record produced will be labelled MOCK."
            )
        self.mode = "mock"

    @property
    def source_label(self) -> str:
        return "PAYPAL_SANDBOX" if self.mode == "live-sandbox" else "MOCK"

    def describe(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "source_label": self.source_label,
            "credentials_present": self.settings.has_paypal_credentials,
            "base_url": self.settings.paypal_base_url,
        }

    # -------------------------------------------------------------- tracking
    async def add_tracking(
        self, *, order_id: str, tracking_number: str, carrier: str
    ) -> CallResult:
        """Add tracking to a PayPal order. Never retried internally."""
        if self.mode == "mock":
            try:
                body = await self.mock.add_tracking(
                    order_id=order_id, tracking_number=tracking_number, carrier=carrier
                )
                return CallResult(
                    outcome="EXECUTED", source="MOCK", detail={"mock_response": body}
                )
            except (PayPalConnectionError, PayPalRequestRejected) as exc:
                return CallResult(
                    outcome="FAILED", source="MOCK", detail={}, error=_sanitize(str(exc))
                )
            except PayPalError as exc:
                # The mock can inject a "may have been applied" failure too
                # (timeout, 5xx, reset, crash), and those must classify as
                # UNKNOWN here exactly as they do against the real API.
                return CallResult(
                    outcome="UNKNOWN", source="MOCK", detail={}, error=_sanitize(str(exc))
                )

        assert self.client is not None
        try:
            body = await self.client.add_tracking(
                order_id=order_id, tracking_number=tracking_number, carrier=carrier
            )
            return CallResult(
                outcome="EXECUTED", source="PAYPAL_SANDBOX", detail={"paypal_response": body}
            )
        except PayPalConnectionError as exc:
            return CallResult(
                outcome="FAILED",
                source="PAYPAL_SANDBOX",
                detail={"reason": "connection-not-established"},
                error=_sanitize(str(exc)),
            )
        except PayPalRequestRejected as exc:
            return CallResult(
                outcome="FAILED",
                source="PAYPAL_SANDBOX",
                detail={"reason": "paypal-rejected", "status": exc.status_code},
                error=_sanitize(str(exc)),
            )
        except PayPalUnknownOutcome as exc:
            return CallResult(
                outcome="UNKNOWN",
                source="PAYPAL_SANDBOX",
                detail={"reason": "may-have-been-applied"},
                error=_sanitize(str(exc)),
            )
        except Exception as exc:  # never crash the API on an external call
            logger.exception("unexpected PayPal failure in add_tracking")
            return CallResult(
                outcome="UNKNOWN",
                source="PAYPAL_SANDBOX",
                detail={"reason": "unexpected-error"},
                error=_sanitize(f"{type(exc).__name__}: {exc}"),
            )

    async def read_tracking(self, *, order_id: str) -> tuple[str, str | None]:
        """Read back what PayPal holds. Returns ("FOUND"|"ABSENT"|"UNKNOWN", number)."""
        if self.mode == "mock":
            try:
                return "FOUND" if await self.mock.read_tracking(order_id) else "ABSENT", (
                    await self.mock.read_tracking(order_id)
                )
            except PayPalError:
                return "UNKNOWN", None
        assert self.client is not None
        try:
            body = await self.client.get_order(order_id)
        except (PayPalConnectionError, PayPalRequestRejected, PayPalUnknownOutcome):
            return "UNKNOWN", None
        for unit in body.get("purchase_units", []) or []:
            shipments = unit.get("shipments") or {}
            for track in shipments.get("trackers", []) or []:
                number = track.get("tracking_number")
                if number:
                    return "FOUND", str(number)
        return "ABSENT", None

    # --------------------------------------------------------------- checkout
    async def create_order(
        self,
        *,
        amount: str,
        currency: str,
        return_url: str,
        cancel_url: str,
        request_id: str,
    ) -> CallResult:
        if self.mode == "mock":
            body = await self.mock.create_order(
                amount=amount,
                currency=currency,
                return_url=return_url,
                cancel_url=cancel_url,
                request_id=request_id,
            )
            approve = next(
                (link["href"] for link in body.get("links", []) if link["rel"] == "approve"),
                None,
            )
            return CallResult(
                outcome="EXECUTED",
                source="MOCK",
                detail={"order_id": body["id"], "approval_url": approve, "mock_response": body},
            )

        assert self.client is not None
        try:
            body = await self.client.create_order(
                amount=amount,
                currency=currency,
                return_url=return_url,
                cancel_url=cancel_url,
                request_id=request_id,
            )
        except PayPalError as exc:
            return CallResult(
                outcome="FAILED", source="PAYPAL_SANDBOX", detail={}, error=_sanitize(str(exc))
            )
        approve = next(
            (link["href"] for link in body.get("links", []) if link["rel"] == "approve"), None
        )
        return CallResult(
            outcome="EXECUTED",
            source="PAYPAL_SANDBOX",
            detail={"order_id": body.get("id"), "approval_url": approve, "paypal_response": body},
        )

    async def capture_order(self, *, order_id: str, request_id: str) -> CallResult:
        if self.mode == "mock":
            body = await self.mock.capture_order(order_id=order_id, request_id=request_id)
            return CallResult(
                outcome="EXECUTED", source="MOCK", detail={"mock_response": body}
            )
        assert self.client is not None
        try:
            body = await self.client.capture_order(order_id, request_id=request_id)
        except PayPalConnectionError as exc:
            return CallResult(
                outcome="FAILED", source="PAYPAL_SANDBOX", detail={}, error=_sanitize(str(exc))
            )
        except PayPalRequestRejected as exc:
            return CallResult(
                outcome="FAILED", source="PAYPAL_SANDBOX", detail={}, error=_sanitize(str(exc))
            )
        except PayPalUnknownOutcome as exc:
            return CallResult(
                outcome="UNKNOWN", source="PAYPAL_SANDBOX", detail={}, error=_sanitize(str(exc))
            )
        return CallResult(
            outcome="EXECUTED", source="PAYPAL_SANDBOX", detail={"paypal_response": body}
        )

    async def list_disputes(self) -> CallResult:
        try:
            if self.mode == "mock":
                body = await self.mock.list_disputes()
                return CallResult(outcome="EXECUTED", source="MOCK", detail={"items": body.get("items", [])})
            assert self.client is not None
            body = await self.client.list_disputes()
            return CallResult(
                outcome="EXECUTED", source="PAYPAL_SANDBOX", detail={"items": body.get("items", [])}
            )
        except PayPalError as exc:
            return CallResult(
                outcome="FAILED", source=self.source_label, detail={"items": []}, error=_sanitize(str(exc))
            )


_service: PayPalService | None = None


def get_paypal_service() -> PayPalService:
    """Process-wide lazily created facade (tests replace it via ``app.state``)."""
    global _service
    if _service is None:
        _service = PayPalService()
    return _service


def reset_paypal_service() -> None:
    global _service
    _service = None
