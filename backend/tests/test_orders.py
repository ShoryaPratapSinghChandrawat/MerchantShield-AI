"""Phase 0 tests 2 and 3 - GET /api/orders/1 and the 404 branch."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_get_seeded_order_returns_full_provenance(demo_client: TestClient) -> None:
    response = demo_client.get("/api/orders/1")

    assert response.status_code == 200
    body = response.json()

    assert body["id"] == 1
    assert body["order_ref"] == "MS-1001"
    assert body["buyer_name"] == "Ava Thompson"
    assert body["item_name"] == "Aurora X2 Noise-Cancelling Headphones"

    # Money is a fixed 2-decimal string, never a float (see schemas/common.py).
    assert body["amount"] == "189.99"
    assert isinstance(body["amount"], str)
    assert body["currency"] == "USD"

    # Rule R5: every record carries the provenance triple.
    assert body["source"] == "SIMULATED"
    assert body["is_demo"] is True
    assert body["demo_run_id"] == "demo-seed-phase0"


def test_unknown_order_returns_404(demo_client: TestClient) -> None:
    response = demo_client.get("/api/orders/9999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Order 9999 not found."


def test_unknown_api_route_is_404_json_not_spa_html(demo_client: TestClient) -> None:
    """The SPA catch-all must never swallow an unmatched /api path."""
    response = demo_client.get("/api/does-not-exist")

    assert response.status_code == 404
    assert response.json()["detail"].startswith("No API route for")
