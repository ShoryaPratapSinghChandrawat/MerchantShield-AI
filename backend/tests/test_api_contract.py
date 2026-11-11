"""The endpoint contract: status codes a client can rely on.

MASTER section 6 asks every implemented endpoint (including the 404/409/422
cases) to be called each phase. This file is that matrix.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.base import get_session_factory
from app.models.audit import AuditLog


def test_every_get_endpoint_answers(demo_client: TestClient) -> None:
    paths = [
        "/api/health",
        "/api/orders",
        "/api/orders/1",
        "/api/actions",
        "/api/audit",
        "/api/about/methodology",
        "/api/store/products",
        "/api/disputes",
    ]
    for path in paths:
        response = demo_client.get(path)
        assert response.status_code == 200, f"{path} -> {response.status_code}: {response.text}"


def test_404_matrix(demo_client: TestClient) -> None:
    cases = [
        ("get", "/api/orders/9999"),
        ("get", "/api/actions/9999"),
        ("get", "/api/disputes/9999"),
        ("post", "/api/actions/9999/approve"),
        ("post", "/api/orders/9999/scan"),
        ("post", "/api/orders/9999/agent"),
        ("get", "/api/nope"),
    ]
    for method, path in cases:
        response = getattr(demo_client, method)(path)
        assert response.status_code == 404, f"{method.upper()} {path} -> {response.status_code}"


def test_409_matrix(demo_client: TestClient) -> None:
    action = demo_client.post(
        "/api/orders/2/propose-action",
        json={"type": "FLAG_FOR_REVIEW", "payload": {}},
    ).json()

    # Not approved yet.
    assert demo_client.post(f"/api/actions/{action['id']}/execute").status_code == 409
    # Retry from PENDING.
    assert demo_client.post(f"/api/actions/{action['id']}/retry").status_code == 409
    # Reconcile from PENDING.
    assert demo_client.post(f"/api/actions/{action['id']}/reconcile", json={}).status_code == 409
    # Approve, then reject.
    demo_client.post(f"/api/actions/{action['id']}/approve")
    assert demo_client.post(f"/api/actions/{action['id']}/reject").status_code == 409


def test_422_matrix(demo_client: TestClient) -> None:
    assert demo_client.post(
        "/api/orders/2/propose-action", json={"type": "REFUND_EVERYTHING"}
    ).status_code == 422
    assert demo_client.post("/api/store/checkout", json={"product_id": "NOPE"}).status_code == 422
    # Missing required body field.
    assert demo_client.post("/api/store/checkout", json={}).status_code == 422
    assert demo_client.post("/api/store/capture", json={}).status_code == 422


def test_methodology_publishes_metrics_and_the_synthetic_disclosure(
    demo_client: TestClient,
) -> None:
    body = demo_client.get("/api/about/methodology").json()

    assert body["ml_estimate"]["metrics"]["data"]["kind"] == "SYNTHETIC"
    assert "majority_class" in body["ml_estimate"]["metrics"]["baselines"]
    assert body["counts_by_source"]["SIMULATED"] == 15
    assert body["counts_by_source"]["PAYPAL_SANDBOX"] == 0
    assert body["paypal"]["mode"] == "mock"
    assert body["llm"]["provider"] == "none"
    assert any("source" in rule for rule in body["honesty_rules"])


def test_audit_filters_work(demo_client: TestClient) -> None:
    demo_client.post("/api/orders/1/scan")

    by_event = demo_client.get("/api/audit", params={"event": "order_scanned"}).json()
    by_order = demo_client.get("/api/audit", params={"order_id": 1}).json()
    limited = demo_client.get("/api/audit", params={"limit": 1}).json()

    assert by_event["count"] >= 1
    assert all(row["event"] == "order_scanned" for row in by_event["items"])
    assert all(row["order_id"] == 1 for row in by_order["items"])
    assert limited["count"] == 1

    # The limit is validated rather than silently clamped.
    assert demo_client.get("/api/audit", params={"limit": 0}).status_code == 422


def test_audit_is_append_only_from_the_api(demo_client: TestClient) -> None:
    session = get_session_factory()()
    try:
        before = len(list(session.scalars(select(AuditLog))))
    finally:
        session.close()

    for method in ("post", "put", "delete", "patch"):
        response = getattr(demo_client, method)("/api/audit")
        assert response.status_code in {404, 405}

    session = get_session_factory()()
    try:
        after = len(list(session.scalars(select(AuditLog))))
    finally:
        session.close()
    assert after == before


def test_every_timestamp_field_ends_with_z(demo_client: TestClient) -> None:
    order = demo_client.get("/api/orders/1").json()
    audit = demo_client.get("/api/audit").json()["items"]

    assert order["order"]["created_at"].endswith("Z")
    assert order["order"]["updated_at"].endswith("Z")
    assert all(row["created_at"].endswith("Z") for row in audit)
