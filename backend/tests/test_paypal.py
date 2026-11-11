"""Phase 5: the PayPal client and facade, with mocked HTTP only.

No test in this file touches a network: httpx's MockTransport serves every
response, and ``conftest`` blocks real sockets anyway.
"""

from __future__ import annotations

import logging

import httpx
import pytest

from app.core.config import Settings
from app.services.paypal_client import (
    PayPalClient,
    PayPalConnectionError,
    PayPalRequestRejected,
    PayPalUnknownOutcome,
)
from app.services.paypal_service import PayPalService

BASE = "https://api-m.sandbox.paypal.com"


def _client(handler, *, timeout: float = 15.0) -> PayPalClient:
    return PayPalClient(
        base_url=BASE,
        client_id="test-client-id",
        client_secret="test-client-secret",
        timeout=timeout,
        transport=httpx.MockTransport(handler),
    )


def _token_ok(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"access_token": "A-TOKEN", "expires_in": 32400})


# ------------------------------------------------------------------- token cache
async def test_token_is_cached_until_expiry() -> None:
    calls = {"token": 0, "orders": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/v1/oauth2/token"):
            calls["token"] += 1
            return _token_ok(request)
        calls["orders"] += 1
        return httpx.Response(200, json={"id": "ORDER-1", "status": "COMPLETED"})

    client = _client(handler)
    await client.get_order("ORDER-1")
    await client.get_order("ORDER-1")

    assert calls["token"] == 1, "the token must be reused while it is valid"
    assert calls["orders"] == 2


async def test_token_cache_respects_the_sixty_second_margin() -> None:
    """expires_in below the 60 s safety margin must not be cached as fresh."""
    calls = {"token": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/v1/oauth2/token"):
            calls["token"] += 1
            return httpx.Response(200, json={"access_token": "SHORT", "expires_in": 30})
        return httpx.Response(200, json={"id": "ORDER-1"})

    client = _client(handler)
    await client.get_order("ORDER-1")
    await client.get_order("ORDER-1")

    assert calls["token"] == 2


# ------------------------------------------------------------- classification
async def test_connect_error_is_a_connection_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    with pytest.raises(PayPalConnectionError):
        await _client(handler).get_order("ORDER-1")


async def test_read_timeout_is_an_unknown_outcome() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("too slow", request=request)

    with pytest.raises(PayPalUnknownOutcome):
        await _client(handler).get_order("ORDER-1")


async def test_connection_reset_is_an_unknown_outcome() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.RemoteProtocolError("reset", request=request)

    with pytest.raises(PayPalUnknownOutcome):
        await _client(handler).get_order("ORDER-1")


async def test_5xx_is_an_unknown_outcome_never_a_retry() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/v1/oauth2/token"):
            return _token_ok(request)
        return httpx.Response(503, json={"name": "SERVICE_UNAVAILABLE"})

    with pytest.raises(PayPalUnknownOutcome):
        await _client(handler).get_order("ORDER-1")


async def test_4xx_is_a_rejection() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/v1/oauth2/token"):
            return _token_ok(request)
        return httpx.Response(422, json={"name": "UNPROCESSABLE_ENTITY"})

    with pytest.raises(PayPalRequestRejected) as excinfo:
        await _client(handler).add_tracking(
            order_id="ORDER-1", tracking_number="1Z999AA10123456784", carrier="UPS"
        )
    assert excinfo.value.status_code == 422


async def test_401_drops_the_cached_token() -> None:
    state = {"expired": False, "tokens": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/v1/oauth2/token"):
            state["tokens"] += 1
            return _token_ok(request)
        if not state["expired"]:
            state["expired"] = True
            return httpx.Response(401, json={"error": "invalid_token"})
        return httpx.Response(200, json={"id": "ORDER-1"})

    client = _client(handler)
    with pytest.raises(PayPalRequestRejected):
        await client.get_order("ORDER-1")
    assert client._token is None  # noqa: SLF001 - asserting the cache was dropped

    await client.get_order("ORDER-1")
    assert state["tokens"] == 2


# ------------------------------------------------------------------- headers
async def test_request_id_is_sent_only_where_paypal_documents_it() -> None:
    seen: dict[str, str | None] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/v1/oauth2/token"):
            return _token_ok(request)
        seen[request.url.path] = request.headers.get("paypal-request-id")
        return httpx.Response(200, json={"id": "ORDER-1"})

    client = _client(handler)
    await client.create_order(
        amount="10.00",
        currency="USD",
        return_url="http://127.0.0.1:8000/store/return",
        cancel_url="http://127.0.0.1:8000/store",
        request_id="checkout-1",
    )
    await client.add_tracking(
        order_id="ORDER-1", tracking_number="1Z999AA10123456784", carrier="UPS"
    )

    assert seen["/v2/checkout/orders"] == "checkout-1"
    # Documented for create/capture, NOT for track - so it is not sent there.
    assert seen["/v2/checkout/orders/ORDER-1/track"] is None


async def test_secrets_never_reach_the_logs(caplog: pytest.LogCaptureFixture) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/v1/oauth2/token"):
            return _token_ok(request)
        return httpx.Response(200, json={"id": "ORDER-1"})

    caplog.set_level(logging.DEBUG)
    client = _client(handler)
    await client.get_order("ORDER-1")

    text = caplog.text
    assert "test-client-secret" not in text
    assert "A-TOKEN" not in text


# ------------------------------------------------------------------- the facade
async def test_facade_falls_back_to_mock_without_credentials() -> None:
    service = PayPalService(Settings(paypal_mode="auto", demo_mode=True))
    assert service.mode == "mock"
    assert service.source_label == "MOCK"


async def test_mock_never_touches_the_network_and_counts_calls() -> None:
    service = PayPalService(Settings(paypal_mode="mock", demo_mode=True))
    result = await service.add_tracking(
        order_id="MS-1", tracking_number="1Z999AA10123456784", carrier="UPS"
    )
    assert result.outcome == "EXECUTED"
    assert result.source == "MOCK"
    assert service.mock.call_count == 1


async def test_mock_honours_the_idempotency_key() -> None:
    service = PayPalService(Settings(paypal_mode="mock", demo_mode=True))
    first = await service.create_order(
        amount="10.00",
        currency="USD",
        return_url="http://127.0.0.1:8000/store/return",
        cancel_url="http://127.0.0.1:8000/store",
        request_id="same-key",
    )
    second = await service.create_order(
        amount="10.00",
        currency="USD",
        return_url="http://127.0.0.1:8000/store/return",
        cancel_url="http://127.0.0.1:8000/store",
        request_id="same-key",
    )
    assert first.detail["order_id"] == second.detail["order_id"]


async def test_facade_classifies_injected_failures() -> None:
    service = PayPalService(Settings(paypal_mode="mock", demo_mode=True))

    service.mock.failure_mode = "4xx"
    assert (await service.add_tracking(order_id="MS-1", tracking_number="1Z999AA10123456784", carrier="UPS")).outcome == "FAILED"

    service.mock.failure_mode = "connect"
    assert (await service.add_tracking(order_id="MS-1", tracking_number="1Z999AA10123456784", carrier="UPS")).outcome == "FAILED"

    for mode in ("timeout", "5xx", "reset", "crash"):
        service.mock.failure_mode = mode
        assert (
            await service.add_tracking(
                order_id="MS-1", tracking_number="1Z999AA10123456784", carrier="UPS"
            )
        ).outcome == "UNKNOWN"


async def test_live_mode_requires_both_credentials() -> None:
    no_secret = PayPalService(
        Settings(paypal_mode="auto", paypal_client_id="abc", demo_mode=True)
    )
    assert no_secret.mode == "mock"

    both = PayPalService(
        Settings(
            paypal_mode="auto",
            paypal_client_id="abc",
            paypal_client_secret="def",
            demo_mode=True,
        )
    )
    assert both.mode == "live-sandbox"
    assert both.source_label == "PAYPAL_SANDBOX"
