"""Safety regression tests for planner-generated action payloads."""

from __future__ import annotations

from sqlalchemy import select
from fastapi.testclient import TestClient

from app.db.base import get_session_factory
from app.models.order import Order


def test_planner_never_invents_tracking_for_a_non_demo_order(
    demo_client: TestClient,
) -> None:
    """A live/Sandbox order with missing shipment data must not get demo values."""
    session = get_session_factory()()
    try:
        order = session.scalar(select(Order).where(Order.order_ref == "MS-2001"))
        assert order is not None
        order.source = "PAYPAL_SANDBOX"
        order.is_demo = False
        order.demo_run_id = None
        order.tracking_number = None
        order.carrier = None
        order_id = order.id
        session.commit()
    finally:
        session.close()

    response = demo_client.post(f"/api/orders/{order_id}/agent")

    assert response.status_code == 200, response.text
    proposals = response.json()["proposals"]
    assert not any(proposal["type"] == "ADD_TRACKING" for proposal in proposals)
    review = next(
        proposal for proposal in proposals if proposal["type"] == "FLAG_FOR_REVIEW"
    )
    assert "will not invent shipment details" in review["rationale"]
    assert "1Z999AA10123456784" not in str(proposals)


def test_demo_tracking_example_is_explicitly_limited_to_mock_walkthroughs(
    demo_client: TestClient,
) -> None:
    """The guided story may use a sample, but the proposal must label it."""
    response = demo_client.post("/api/orders/1/agent")

    assert response.status_code == 200, response.text
    proposal = next(
        item for item in response.json()["proposals"] if item["type"] == "ADD_TRACKING"
    )
    assert proposal["payload"]["tracking_number"] == "1Z999AA10123456784"
    assert "DEMO ONLY" in proposal["rationale"]
    assert "never use this sample for a real shipment" in proposal["rationale"]
