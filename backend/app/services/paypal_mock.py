"""Mock PayPal adapter.

Used whenever there are no credentials, when ``PAYPAL_MODE=mock``, or as the
safe fallback after a live attempt fails. Everything it returns is labelled
``MOCK``; nothing here contacts anything.

It also exists to make failure modes testable without touching a network:
``failure_mode`` injects each classification MASTER 4.4 requires, and
``call_count`` proves that a duplicate execute produced ONE external attempt.
"""

from __future__ import annotations

import logging
from typing import Any

from app.services.paypal_client import (
    PayPalConnectionError,
    PayPalRequestRejected,
    PayPalUnknownOutcome,
)

logger = logging.getLogger(__name__)

FAILURE_MODES = frozenset(
    {"ok", "4xx", "connect", "timeout", "5xx", "reset", "crash"}
)


class PayPalMock:
    """Deterministic stand-in for the Sandbox REST API."""

    def __init__(self) -> None:
        self.call_count = 0
        self.failure_mode = "ok"
        #: idempotency key -> response, so a replayed key is observably a no-op.
        self._idempotent_results: dict[str, dict[str, Any]] = {}
        #: order id -> tracking number, so "read back" can verify an effect.
        self._tracking: dict[str, str] = {}
        self._orders: dict[str, dict[str, Any]] = {}
        self._seq = 0

    # ------------------------------------------------------------- helpers
    def reset(self) -> None:
        self.call_count = 0
        self.failure_mode = "ok"
        self._idempotent_results.clear()
        self._tracking.clear()
        self._orders.clear()
        self._seq = 0

    def _guard_failure(self, operation: str) -> None:
        """Raise the exception that classifies to the required status."""
        mode = self.failure_mode
        if mode == "ok":
            return
        if mode == "4xx":
            raise PayPalRequestRejected(
                f"{operation}: PayPal 422 (mock)", 422, '{"name":"UNPROCESSABLE_ENTITY"}'
            )
        if mode == "connect":
            raise PayPalConnectionError(f"{operation}: connection refused (mock)")
        if mode == "timeout":
            raise PayPalUnknownOutcome(f"{operation}: read timeout (mock)")
        if mode == "5xx":
            raise PayPalUnknownOutcome(f"{operation}: PayPal 503 (mock)")
        if mode == "reset":
            raise PayPalUnknownOutcome(f"{operation}: connection reset (mock)")
        if mode == "crash":
            # Simulates the process dying after the request was accepted.
            raise PayPalUnknownOutcome(f"{operation}: worker crashed after send (mock)")
        raise PayPalUnknownOutcome(f"{operation}: unknown failure mode {mode!r} (mock)")

    # ------------------------------------------------------------ endpoints
    async def create_order(
        self,
        *,
        amount: str,
        currency: str,
        return_url: str,
        cancel_url: str,
        request_id: str,
    ) -> dict[str, Any]:
        self.call_count += 1
        self._guard_failure("create_order")
        cached = self._idempotent_results.get(request_id)
        if cached is not None:
            return cached
        self._seq += 1
        order_id = f"MOCK-ORDER-{self._seq:04d}"
        body = {
            "id": order_id,
            "status": "CREATED",
            "intent": "CAPTURE",
            "links": [
                {
                    "href": f"{return_url}&mock_token={order_id}",
                    "rel": "approve",
                    "method": "GET",
                },
                {"href": cancel_url, "rel": "cancel", "method": "GET"},
            ],
            "purchase_units": [
                {"amount": {"currency_code": currency, "value": amount}}
            ],
        }
        self._idempotent_results[request_id] = body
        self._orders[order_id] = {**body, "status": "APPROVED"}
        logger.info("mock paypal: created %s (source=MOCK)", order_id)
        return body

    async def capture_order(self, order_id: str, *, request_id: str) -> dict[str, Any]:
        self.call_count += 1
        self._guard_failure("capture_order")
        cached = self._idempotent_results.get(request_id)
        if cached is not None:
            return cached
        body = {
            "id": order_id,
            "status": "COMPLETED",
            "purchase_units": [{"payments": {"captures": [{"id": f"CAP-{order_id}"}]}}],
        }
        self._idempotent_results[request_id] = body
        self._orders[order_id] = body
        return body

    async def get_order(self, order_id: str) -> dict[str, Any]:
        self.call_count += 1
        self._guard_failure("get_order")
        return self._orders.get(order_id, {"id": order_id, "status": "UNKNOWN"})

    async def add_tracking(
        self,
        *,
        order_id: str,
        tracking_number: str,
        carrier: str,
        status: str = "SHIPPED",
    ) -> dict[str, Any]:
        self.call_count += 1
        self._guard_failure("add_tracking")
        self._tracking[order_id] = tracking_number
        return {"id": order_id, "tracking_number": tracking_number, "carrier": carrier}

    async def read_tracking(self, order_id: str) -> str | None:
        """Read-back used by Reconcile. Absence is a fact, not an error."""
        self.call_count += 1
        self._guard_failure("read_tracking")
        return self._tracking.get(order_id)

    async def list_disputes(self, *, page_size: int = 10) -> dict[str, Any]:
        self.call_count += 1
        self._guard_failure("list_disputes")
        return {"items": [], "page_size": page_size}
