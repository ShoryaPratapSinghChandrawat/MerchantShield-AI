#!/usr/bin/env python3
"""Verify the real PayPal *Sandbox* credentials, by hand, before a demo.

This script is deliberately separate from the test suite. The suite never
touches the network (``conftest.py`` blocks non-loopback sockets), so the only
way to prove a credential works is to run something like this against the
Sandbox - and to say afterwards that it ran.

What it does, in order:

1. Reads ``PAYPAL_CLIENT_ID`` / ``PAYPAL_CLIENT_SECRET`` from the environment.
   It never reads a file, never prints the secret, and refuses to run against
   anything but the Sandbox host.
2. Requests an OAuth2 token.
3. Creates a $1.00 sandbox order (``intent=CAPTURE``).
4. Reads the order back.
5. Prints what happened, including the ``source`` label the app would store.

What it does NOT do: capture money, file a dispute, or touch production.

Usage (PowerShell, from the repository root):

    $env:PAYPAL_CLIENT_ID = "..."
    $env:PAYPAL_CLIENT_SECRET = "..."
    .\\.venv\\Scripts\\python.exe scripts\\verify_paypal_live.py

Exit codes:
    0  the Sandbox answered for every step
    1  a step failed (the message says which)
    2  credentials are missing, or the base URL is not the Sandbox
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.core.config import DEFAULT_PAYPAL_SANDBOX_BASE_URL, validate_paypal_base_url  # noqa: E402
from app.services.paypal_client import (  # noqa: E402
    PayPalClient,
    PayPalConnectionError,
    PayPalError,
    PayPalRequestRejected,
    PayPalUnknownOutcome,
)


def _fail(message: str, code: int = 1) -> int:
    print(f"FAIL  {message}")
    return code


async def main() -> int:
    client_id = os.environ.get("PAYPAL_CLIENT_ID", "").strip()
    client_secret = os.environ.get("PAYPAL_CLIENT_SECRET", "").strip()

    if not client_id or not client_secret:
        return _fail(
            "PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET must both be set in the environment.",
            code=2,
        )

    base_url = os.environ.get("PAYPAL_BASE_URL", DEFAULT_PAYPAL_SANDBOX_BASE_URL).strip()
    try:
        validate_paypal_base_url(base_url)
    except Exception as exc:  # noqa: BLE001 - the validator's message is the point
        return _fail(f"base URL rejected: {exc}", code=2)

    print(f"==> host    : {base_url}")
    print(f"==> client  : {client_id[:6]}…{client_id[-2:]} (truncated on purpose)")
    print("==> secret  : (never printed)")

    client = PayPalClient(
        base_url=base_url,
        client_id=client_id,
        client_secret=client_secret,
        timeout=20.0,
    )

    try:
        token = await client.get_token()
        print(f"PASS  OAuth2 token obtained ({len(token)} characters, not printed)")
    except PayPalRequestRejected as exc:
        return _fail(f"token rejected (HTTP {exc.status_code}): {exc}. Check the app's Sandbox credentials.")
    except PayPalError as exc:
        return _fail(f"token request failed: {exc}")

    try:
        order = await client.create_order(
            amount="1.00",
            currency="USD",
            return_url="http://127.0.0.1:8000/store/return",
            cancel_url="http://127.0.0.1:8000/store",
            request_id="merchantshield-verify-" + os.urandom(6).hex(),
        )
        order_id = order.get("id", "")
        print(f"PASS  order created: {order_id} (status {order.get('status', '?')})")
    except PayPalConnectionError as exc:
        return _fail(f"could not connect to the Sandbox: {exc}")
    except PayPalRequestRejected as exc:
        return _fail(f"order rejected (HTTP {exc.status_code}): {exc}")
    except PayPalUnknownOutcome as exc:
        return _fail(f"order creation outcome unknown: {exc}")
    except PayPalError as exc:
        return _fail(f"order creation failed: {exc}")

    try:
        read_back = await client.get_order(order_id)
        print(f"PASS  order read back: {read_back.get('status', '?')}")
    except PayPalError as exc:
        return _fail(f"could not read the order back: {exc}")

    print("")
    print("All steps answered. In the app these rows would be stored as:")
    print("    source = PAYPAL_SANDBOX   is_demo = false")
    print("Nothing was captured, no dispute was filed, no production host was contacted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
