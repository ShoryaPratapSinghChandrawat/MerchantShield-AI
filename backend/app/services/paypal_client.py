"""PayPal Sandbox REST client - every PayPal call lives in exactly one function.

MASTER section 5: verify every endpoint, header and payload against the official
docs (developer.paypal.com) before coding. What was checked:

* ``POST /v1/oauth2/token`` - form body ``grant_type=client_credentials``,
  HTTP Basic auth with client id and secret.
* ``POST /v2/checkout/orders`` - ``intent=CAPTURE``, ``purchase_units``,
  ``payment_source.paypal.experience_context`` for return/cancel URLs.
  ``PayPal-Request-Id`` IS documented here.
* ``POST /v2/checkout/orders/{id}/capture`` - ``PayPal-Request-Id`` documented.
* ``GET  /v2/checkout/orders/{id}`` - read-back, used by Reconcile.
* ``POST /v2/checkout/orders/{id}/track`` - ``PayPal-Request-Id`` is NOT
  documented for this endpoint, so this client never sends it. The consequence
  (residual duplicate-call risk) is in README Limitations and DECISIONS D-003.
* ``GET  /v1/customer/disputes`` - read-only listing.

Nothing here has been called against a real PayPal Sandbox account from this
project's own runs: there are no credentials. See ``DECISIONS.md``
"UNVERIFIED PAYPAL CALLS" and ``scripts/verify_paypal_live.py``, which the
project owner runs locally to produce real evidence.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 15.0
TOKEN_SAFETY_MARGIN_SECONDS = 60


class PayPalError(Exception):
    """Base class for every PayPal problem this app can classify."""


class PayPalConnectionError(PayPalError):
    """Nothing was transmitted (DNS, refused, connect timeout) -> FAILED."""


class PayPalRequestRejected(PayPalError):
    """PayPal answered and rejected the request (4xx) -> FAILED."""

    def __init__(self, message: str, status_code: int, body: str = "") -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class PayPalUnknownOutcome(PayPalError):
    """The request may or may not have been applied (timeout, 5xx, reset) -> UNKNOWN."""


class PayPalClient:
    """Thin, single-responsibility wrapper. No retries of writes, ever."""

    def __init__(
        self,
        *,
        base_url: str,
        client_id: str,
        client_secret: str,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._client_id = client_id
        self._client_secret = client_secret
        self._timeout = timeout
        self._transport = transport
        self._token: str | None = None
        self._token_expires_at: datetime | None = None
        #: Counted here so tests can assert "one external attempt" without
        #: reaching into mock internals.
        self.calls: int = 0

    # ------------------------------------------------------------------ token
    async def get_token(self) -> str:
        """Return a cached OAuth token, refreshing ``margin`` before expiry."""
        now = datetime.now(timezone.utc)
        if self._token and self._token_expires_at and now < self._token_expires_at:
            return self._token

        self.calls += 1
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout, transport=self._transport
            ) as client:
                response = await client.post(
                    f"{self.base_url}/v1/oauth2/token",
                    data={"grant_type": "client_credentials"},
                    auth=(self._client_id, self._client_secret),
                    headers={"Accept": "application/json"},
                )
        except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
            raise PayPalConnectionError(f"token: connection failed ({type(exc).__name__})") from exc
        except (httpx.ReadTimeout, httpx.ReadError, httpx.RemoteProtocolError) as exc:
            raise PayPalUnknownOutcome(f"token: outcome unknown ({type(exc).__name__})") from exc

        if response.status_code >= 500:
            raise PayPalUnknownOutcome(f"token: PayPal {response.status_code}")
        if response.status_code >= 400:
            raise PayPalRequestRejected(
                f"token: PayPal {response.status_code}", response.status_code, response.text[:400]
            )

        body = response.json()
        token = body.get("access_token")
        if not token:
            raise PayPalUnknownOutcome("token: response had no access_token")
        expires_in = int(body.get("expires_in", 0) or 0)
        self._token = token
        self._token_expires_at = now + timedelta(
            seconds=max(0, expires_in - TOKEN_SAFETY_MARGIN_SECONDS)
        )
        return token

    def invalidate_token(self) -> None:
        """Drop the cached token (used when PayPal answers 401)."""
        self._token = None
        self._token_expires_at = None

    # ------------------------------------------------------------------ core
    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        token = await self.get_token()
        request_headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if headers:
            request_headers.update(headers)

        self.calls += 1
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout, transport=self._transport
            ) as client:
                response = await client.request(
                    method,
                    f"{self.base_url}{path}",
                    json=json_body,
                    headers=request_headers,
                    params=params,
                )
        except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
            # Nothing left the process: safe to call this FAILED.
            raise PayPalConnectionError(
                f"{method} {path}: connection failed ({type(exc).__name__})"
            ) from exc
        except (httpx.ReadTimeout, httpx.ReadError, httpx.RemoteProtocolError, httpx.WriteError) as exc:
            # The request may well have been applied: UNKNOWN, never retried.
            raise PayPalUnknownOutcome(
                f"{method} {path}: outcome unknown ({type(exc).__name__})"
            ) from exc

        if response.status_code >= 500:
            raise PayPalUnknownOutcome(f"{method} {path}: PayPal {response.status_code}")
        if response.status_code == 401:
            self.invalidate_token()
            raise PayPalRequestRejected(
                f"{method} {path}: PayPal 401", 401, response.text[:400]
            )
        if response.status_code >= 400:
            raise PayPalRequestRejected(
                f"{method} {path}: PayPal {response.status_code}",
                response.status_code,
                response.text[:400],
            )

        if not response.content:
            return {}
        try:
            return response.json()
        except ValueError as exc:  # pragma: no cover - PayPal always returns JSON
            raise PayPalUnknownOutcome(f"{method} {path}: unparsable body") from exc

    # --------------------------------------------------------------- endpoints
    async def create_order(
        self,
        *,
        amount: str,
        currency: str,
        return_url: str,
        cancel_url: str,
        request_id: str,
    ) -> dict[str, Any]:
        """Create an order and return PayPal's body (contains the approve link)."""
        return await self._request(
            "POST",
            "/v2/checkout/orders",
            json_body={
                "intent": "CAPTURE",
                "purchase_units": [
                    {"amount": {"currency_code": currency, "value": amount}}
                ],
                "payment_source": {
                    "paypal": {
                        "experience_context": {
                            "return_url": return_url,
                            "cancel_url": cancel_url,
                            "user_action": "PAY_NOW",
                            "shipping_preference": "NO_SHIPPING",
                        }
                    }
                },
            },
            headers={"PayPal-Request-Id": request_id},
        )

    async def capture_order(self, order_id: str, *, request_id: str) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/v2/checkout/orders/{order_id}/capture",
            json_body={},
            headers={"PayPal-Request-Id": request_id},
        )

    async def get_order(self, order_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/v2/checkout/orders/{order_id}")

    async def add_tracking(
        self,
        *,
        order_id: str,
        tracking_number: str,
        carrier: str,
        status: str = "SHIPPED",
    ) -> dict[str, Any]:
        """Add tracking. NO ``PayPal-Request-Id``: the docs do not list it here.

        Sending a header PayPal does not support for this endpoint would be a
        fake guarantee, so it is omitted and the risk is documented instead.
        """
        return await self._request(
            "POST",
            f"/v2/checkout/orders/{order_id}/track",
            json_body={
                "tracking_number": tracking_number,
                "carrier": carrier,
                "status": status,
                "capture_id": None,
                "notify_payer": False,
            },
        )

    async def list_disputes(self, *, page_size: int = 10) -> dict[str, Any]:
        return await self._request(
            "GET", "/v1/customer/disputes", params={"page_size": page_size}
        )
