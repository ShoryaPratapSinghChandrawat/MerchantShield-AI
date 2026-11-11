"""Orders API: the seeded story order, provenance, risk, and the 404 branches."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_get_seeded_order_returns_full_provenance(demo_client: TestClient) -> None:
    response = demo_client.get("/api/orders/1")

    assert response.status_code == 200
    body = response.json()
    order = body["order"]

    assert order["id"] == 1
    assert order["order_ref"] == "MS-2001"
    assert order["buyer_name"] == "Daniel Reyes"
    assert order["item_name"] == "Aurora X2 laptop, 16GB"

    # Money is a fixed 2-decimal string, never a float (see schemas/common.py).
    assert order["amount"] == "1899.00"
    assert isinstance(order["amount"], str)
    assert order["currency"] == "USD"

    # Rule R5: every record carries the provenance triple.
    assert order["source"] == "SIMULATED"
    assert order["is_demo"] is True
    assert order["demo_run_id"] == "demo-run-phase1"


def test_order_detail_carries_risk_reasons_and_missing_evidence(demo_client: TestClient) -> None:
    body = demo_client.get("/api/orders/1").json()

    risk = body["risk"]
    assert risk["risk_level"] in {"LOW", "MEDIUM", "HIGH"}
    assert 0.0 <= risk["risk_score"] <= 1.0
    assert risk["reasons"], "a scored order must always explain itself"
    for reason in risk["reasons"]:
        assert reason["direction"] in {"+", "-"}
        assert reason["label"]
    assert len(risk["missing_evidence"]) == 7
    assert all("what_to_do" in item for item in risk["missing_evidence"])

    assert body["ml_risk_estimate"]["label"] == "ESTIMATE"
    assert 0.0 <= body["ml_risk_estimate"]["estimate"] <= 1.0
    assert body["evidence_strength"]["max"] == 100


def test_orders_list_returns_every_seeded_story(demo_client: TestClient) -> None:
    body = demo_client.get("/api/orders").json()

    assert body["count"] == 15
    refs = [row["order_ref"] for row in body["items"]]
    assert refs[0] == "MS-2001"
    assert len(set(refs)) == 15
    assert all(row["risk_level"] in {"LOW", "MEDIUM", "HIGH"} for row in body["items"])


def test_scan_is_repeatable_and_audited(demo_client: TestClient) -> None:
    first = demo_client.post("/api/orders/2/scan").json()
    second = demo_client.post("/api/orders/2/scan").json()

    assert first["risk_score"] == second["risk_score"]
    assert first["reasons"] == second["reasons"]

    audit = demo_client.get("/api/audit", params={"event": "order_scanned"}).json()
    assert audit["count"] >= 2


def test_unknown_order_returns_404(demo_client: TestClient) -> None:
    response = demo_client.get("/api/orders/9999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Order 9999 not found."


def test_unknown_api_route_is_404_json_not_spa_html(demo_client: TestClient) -> None:
    """The SPA catch-all must never swallow an unmatched /api path."""
    response = demo_client.get("/api/does-not-exist")

    assert response.status_code == 404
    assert response.json()["detail"].startswith("No API route for")
