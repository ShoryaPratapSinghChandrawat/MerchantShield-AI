"""Demo mode: reset semantics, gating, and the demo director."""

from __future__ import annotations

from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.config import reset_settings_cache
from app.db.base import get_session_factory, reset_engine_for_tests
from app.models.audit import AuditLog
from app.models.order import Order


def test_demo_routes_are_404_when_demo_mode_is_false(
    make_client: Callable[..., TestClient],
) -> None:
    client = make_client(demo_mode=False, db_name="no-demo.db")

    assert client.post("/api/demo/reset").status_code == 404
    assert client.post("/api/demo/run-story").status_code == 404
    assert client.post("/api/demo/seed").status_code == 404


def test_reset_deletes_demo_rows_and_keeps_a_live_order(demo_client: TestClient) -> None:
    """The rule that matters: a LIVE row and its audit trail survive a reset."""
    session = get_session_factory()()
    try:
        live = Order(
            order_ref="LIVE-1",
            buyer_name="Live Buyer",
            buyer_email="live@example.com",
            item_name="Live item",
            amount=100,
            currency="USD",
            status="COMPLETED",
            source="PAYPAL_SANDBOX",
            is_demo=True,
            demo_run_id="demo-run-phase1",
        )
        session.add(live)
        session.flush()
        session.add(
            AuditLog(
                order_id=live.id,
                event="payment_captured",
                message="live row",
                source="PAYPAL_SANDBOX",
                is_demo=True,
                demo_run_id="demo-run-phase1",
            )
        )
        session.commit()
        live_id = live.id
    finally:
        session.close()

    before = demo_client.get("/api/orders").json()["count"]
    assert before == 16

    result = demo_client.post("/api/demo/reset").json()

    assert result["deleted"]["orders"] == 15
    assert result["kept_live_orders"] == [live_id]

    remaining = demo_client.get("/api/orders").json()
    assert remaining["count"] == 1
    assert remaining["items"][0]["order_ref"] == "LIVE-1"

    session = get_session_factory()()
    try:
        live_audit = session.scalar(
            select(func.count()).select_from(AuditLog).where(AuditLog.order_id == live_id)
        )
        total_audit = session.scalar(select(func.count()).select_from(AuditLog))
        reset_rows = session.scalar(
            select(func.count()).select_from(AuditLog).where(AuditLog.event == "demo_reset")
        )
    finally:
        session.close()

    assert live_audit == 1, "the LIVE order's audit rows must survive"
    assert reset_rows == 1, "reset writes exactly one kept audit row"
    assert total_audit >= 2


def test_reset_then_seed_restores_the_demo(demo_client: TestClient) -> None:
    demo_client.post("/api/demo/reset")
    assert demo_client.get("/api/orders").json()["count"] == 0

    seeded = demo_client.post("/api/demo/seed").json()
    assert seeded["inserted"] == 15
    assert demo_client.get("/api/orders").json()["count"] == 15


def test_run_story_plays_the_whole_v1_flow(demo_client: TestClient) -> None:
    body = demo_client.post("/api/demo/run-story").json()

    steps = [step["step"] for step in body["steps"]]
    assert steps[0] == "checkout"
    assert steps[1] == "captured"
    for required in ("fast_forward", "scan", "proposals", "execute", "dispute_packet", "draft", "submit"):
        assert required in steps, f"missing story step {required}"

    # Every step states a real source label - nothing is left unlabelled.
    assert all(step["source"] in {"PAYPAL_SANDBOX", "SIMULATED", "MOCK"} for step in body["steps"])
    assert body["executed_action_ids"], "the story must actually execute something"

    order = demo_client.get(f"/api/orders/{body['order_id']}").json()
    assert order["order"]["tracking_number"]
    assert order["risk"]["risk_level"] in {"LOW", "MEDIUM", "HIGH"}

    dispute = demo_client.get(f"/api/disputes/{body['dispute_id']}").json()
    assert dispute["status"] == "SUBMITTED"
    assert dispute["submit_result"]["submission_mode"] == "SIMULATED"
    assert dispute["drafts"][0]["origin"] in {"Template draft", "AI draft"}


def test_run_story_is_repeatable(demo_client: TestClient) -> None:
    first = demo_client.post("/api/demo/run-story").json()
    second = demo_client.post("/api/demo/run-story").json()

    assert first["order_id"] != second["order_id"]
    assert first["run_id"] != second["run_id"]
    assert demo_client.get("/api/orders").json()["count"] >= 17
