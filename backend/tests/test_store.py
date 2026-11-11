"""Phase 5 storefront: products, MOCK checkout, capture, and honest labels."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_four_products_including_a_high_value_item(demo_client: TestClient) -> None:
    items = demo_client.get("/api/store/products").json()["items"]

    assert len(items) == 4
    assert any(item["high_value"] for item in items)
    assert all({"id", "name", "price", "blurb"} <= set(item) for item in items)


def test_mock_checkout_returns_a_labelled_approval_link(demo_client: TestClient) -> None:
    body = demo_client.post(
        "/api/store/checkout",
        json={"product_id": "P-200", "buyer_name": "Test Buyer", "buyer_email": "t@example.com"},
    ).json()

    assert body["source"] == "MOCK"
    assert body["mock"] is True
    assert body["approval_url"].startswith("http://127.0.0.1:8000/store/mock-approve")
    assert body["paypal_order_id"].startswith("MOCK-ORDER-")

    order = demo_client.get(f"/api/orders/{body['order_id']}").json()["order"]
    assert order["status"] == "PENDING_PAYMENT"
    assert order["is_demo"] is False, "a storefront order is not demo data"


def test_capture_completes_the_order_and_keeps_the_mock_label(demo_client: TestClient) -> None:
    checkout = demo_client.post("/api/store/checkout", json={"product_id": "P-100"}).json()

    captured = demo_client.post(
        "/api/store/capture", json={"token": checkout["paypal_order_id"]}
    ).json()

    assert captured["captured"] is True
    assert captured["source"] == "MOCK"
    assert "no PayPal account was contacted" in captured["note"]

    order = demo_client.get(f"/api/orders/{checkout['order_id']}").json()["order"]
    assert order["status"] == "COMPLETED"
    assert order["amount"] == "1899.00"


def test_return_endpoint_captures_by_token(demo_client: TestClient) -> None:
    checkout = demo_client.post("/api/store/checkout", json={"product_id": "P-300"}).json()

    response = demo_client.get(
        "/api/store/return", params={"token": checkout["paypal_order_id"]}
    )

    assert response.status_code == 200
    assert response.json()["captured"] is True


def test_unknown_product_is_422(demo_client: TestClient) -> None:
    response = demo_client.post("/api/store/checkout", json={"product_id": "NOPE"})
    assert response.status_code == 422


def test_unknown_capture_token_is_404(demo_client: TestClient) -> None:
    assert demo_client.post("/api/store/capture", json={"token": "nope"}).status_code == 404
