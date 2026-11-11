"""Phase 2: the whole of MASTER 4.4, one test at a time.

Every external call is served by the PayPal mock, so nothing here touches a
network. ``PayPalMock.call_count`` is the evidence that a duplicate execute
produced exactly ONE external attempt.
"""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.actions import paypal_dep
from app.services import actions as action_service
from app.core.timeutil import utcnow
from app.db.base import get_session_factory
from app.models.action import Action
from app.models.audit import AuditLog
from app.services.paypal_service import PayPalService

TRACKING = {"tracking_number": "1Z999AA10123456784", "carrier": "UPS"}


@pytest.fixture
def paypal(demo_client: TestClient) -> PayPalService:
    """A controllable mock-mode facade installed over the API dependency."""
    service = PayPalService()
    assert service.mode == "mock", "tests must never run in live mode"
    demo_client.app.dependency_overrides[paypal_dep] = lambda: service  # type: ignore[attr-defined]
    return service


def _propose(client: TestClient, order_id: int, action_type: str, payload: dict[str, str] | None = None) -> dict:
    response = client.post(
        f"/api/orders/{order_id}/propose-action",
        json={"type": action_type, "payload": payload or {}, "rationale": "test"},
    )
    assert response.status_code in {200, 201}, response.text
    return response.json()


def _approve(client: TestClient, action_id: int) -> dict:
    response = client.post(f"/api/actions/{action_id}/approve")
    assert response.status_code == 200, response.text
    return response.json()


def _execute(client: TestClient, action_id: int) -> tuple[int, dict]:
    response = client.post(f"/api/actions/{action_id}/execute")
    return response.status_code, response.json()


def _action_status(action_id: int) -> str:
    session = get_session_factory()()
    try:
        action = session.get(Action, action_id)
        assert action is not None
        return action.status
    finally:
        session.close()


# ------------------------------------------------------------------ proposing
def test_propose_defaults_to_flag_for_review(demo_client: TestClient) -> None:
    response = demo_client.post("/api/orders/2/propose-action", json={})
    assert response.status_code == 201
    assert response.json()["type"] == "FLAG_FOR_REVIEW"
    assert response.json()["status"] == "PENDING"


def test_propose_rejects_types_outside_the_allowlist(demo_client: TestClient) -> None:
    response = demo_client.post(
        "/api/orders/2/propose-action", json={"type": "ISSUE_REFUND", "payload": {}}
    )
    assert response.status_code == 422
    assert "not an allowed action type" in response.json()["detail"]


def test_duplicate_open_proposal_returns_the_existing_one(demo_client: TestClient) -> None:
    first = _propose(demo_client, 3, "ADD_TRACKING", TRACKING)
    second = demo_client.post(
        "/api/orders/3/propose-action",
        json={"type": "ADD_TRACKING", "payload": TRACKING},
    )

    assert second.status_code == 200
    assert second.json()["id"] == first["id"]
    assert second.json()["created"] is False
    actions = demo_client.get("/api/actions", params={"order_id": 3}).json()
    assert actions["count"] == 1


def test_propose_on_a_missing_order_is_404(demo_client: TestClient) -> None:
    assert demo_client.post("/api/orders/9999/propose-action", json={}).status_code == 404


# ------------------------------------------------------------------ approving
def test_execute_before_approval_is_409(demo_client: TestClient, paypal: PayPalService) -> None:
    action = _propose(demo_client, 4, "ADD_TRACKING", TRACKING)

    status, body = _execute(demo_client, action["id"])

    assert status == 409
    assert "APPROVED" in body["detail"]
    assert paypal.mock.call_count == 0


def test_reapprove_is_a_200_noop_and_approving_executed_is_409(
    demo_client: TestClient, paypal: PayPalService
) -> None:
    action = _propose(demo_client, 5, "ADD_TRACKING", TRACKING)
    _approve(demo_client, action["id"])

    again = demo_client.post(f"/api/actions/{action['id']}/approve")
    assert again.status_code == 200
    assert again.json()["status"] == "APPROVED"

    assert _execute(demo_client, action["id"])[0] == 200
    conflict = demo_client.post(f"/api/actions/{action['id']}/approve")
    assert conflict.status_code == 409


def test_reject_moves_pending_to_rejected_and_then_conflicts(demo_client: TestClient) -> None:
    action = _propose(demo_client, 6, "FLAG_FOR_REVIEW")

    assert demo_client.post(f"/api/actions/{action['id']}/reject").json()["status"] == "REJECTED"
    assert demo_client.post(f"/api/actions/{action['id']}/reject").status_code == 409
    assert demo_client.post(f"/api/actions/{action['id']}/approve").status_code == 409


# ------------------------------------------------------------------- executing
def test_execute_applies_tracking_and_records_only_changed_fields(
    demo_client: TestClient, paypal: PayPalService
) -> None:
    action = _propose(demo_client, 6, "ADD_TRACKING", TRACKING)
    _approve(demo_client, action["id"])

    status, body = _execute(demo_client, action["id"])

    assert status == 200
    assert body["status"] == "EXECUTED"
    assert body["before"] == {
        "tracking_number": None,
        "carrier": None,
        "shipped_at": None,
    }
    assert body["after"]["tracking_number"] == TRACKING["tracking_number"]
    assert body["after"]["carrier"] == "UPS"
    # Unchanged fields are not in the diff at all.
    assert "flagged_for_review" not in body["before"]
    assert body["result"]["source"] == "MOCK"
    assert paypal.mock.call_count == 1

    order = demo_client.get("/api/orders/6").json()["order"]
    assert order["tracking_number"] == TRACKING["tracking_number"]


def test_local_action_reports_no_external_call(demo_client: TestClient, paypal: PayPalService) -> None:
    """A locally-handled action must never claim an external PayPal call.

    BUG-0020: FLAG_FOR_REVIEW is applied inside this app and stores
    source=SIMULATED, but the response carried a `source` field and no
    indication that nothing external happened, so the drawer painted it as a
    real PayPal Sandbox response. The API now states the fact explicitly and
    leaves the label honest.
    """
    action = _propose(demo_client, 6, "FLAG_FOR_REVIEW")
    _approve(demo_client, action["id"])

    status, body = _execute(demo_client, action["id"])

    assert status == 200
    assert body["status"] == "EXECUTED"
    assert body["after"]["flagged_for_review"] is True
    assert body["result"]["external_call"] is False
    assert body["result"]["source"] == "SIMULATED"
    assert body["result"]["external"] == {"note": "local action, no external call"}
    # No adapter was contacted for a local action.
    assert paypal.mock.call_count == 0


def test_execute_twice_is_idempotent_and_makes_no_second_call(
    demo_client: TestClient, paypal: PayPalService
) -> None:
    action = _propose(demo_client, 8, "ADD_TRACKING", TRACKING)
    _approve(demo_client, action["id"])
    _execute(demo_client, action["id"])

    status, body = _execute(demo_client, action["id"])

    assert status == 200
    assert body["already_executed"] is True
    assert paypal.mock.call_count == 1


def test_message_buyer_creates_a_logged_message_in_the_diff(
    demo_client: TestClient, paypal: PayPalService
) -> None:
    action = _propose(
        demo_client, 9, "MESSAGE_BUYER", {"body": "Your parcel is on the way."}
    )
    _approve(demo_client, action["id"])
    status, body = _execute(demo_client, action["id"])

    assert status == 200
    assert body["after"]["merchant_messages"] == 1
    detail = demo_client.get("/api/orders/9").json()
    merchant_messages = [m for m in detail["messages"] if m["direction"] == "MERCHANT"]
    assert merchant_messages and merchant_messages[-1]["body"].startswith("Your parcel")


def test_invalid_tracking_number_fails_locally_without_a_call(
    demo_client: TestClient, paypal: PayPalService
) -> None:
    action = _propose(demo_client, 10, "ADD_TRACKING", {"tracking_number": "!!", "carrier": "UPS"})
    _approve(demo_client, action["id"])

    response = demo_client.post(f"/api/actions/{action['id']}/execute")

    assert response.status_code == 422
    assert paypal.mock.call_count == 0
    assert _action_status(action["id"]) == "FAILED"


def test_missing_carrier_is_a_validation_failure(demo_client: TestClient, paypal: PayPalService) -> None:
    action = _propose(
        demo_client, 11, "ADD_TRACKING", {"tracking_number": "1Z999AA10123456784", "carrier": ""}
    )
    _approve(demo_client, action["id"])

    assert demo_client.post(f"/api/actions/{action['id']}/execute").status_code == 422
    assert paypal.mock.call_count == 0


# ---------------------------------------------------------------- 8 concurrent
def test_eight_concurrent_executes_claim_once(
    demo_client: TestClient, paypal: PayPalService
) -> None:
    """MASTER 4.4: exactly one claim, one external attempt, one audit row."""
    action = _propose(demo_client, 12, "ADD_TRACKING", TRACKING)
    _approve(demo_client, action["id"])

    def fire(_: int) -> tuple[int, bool]:
        response = demo_client.post(f"/api/actions/{action['id']}/execute")
        body = response.json()
        # "executed by me" is exactly one of: 200 with already_executed=False.
        return response.status_code, body.get("already_executed") is False

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(fire, range(8)))

    statuses = [code for code, _ in results]
    winners = [mine for _, mine in results]

    assert all(code in {200, 409} for code in statuses), statuses
    # Losers either lost the claim (409, while EXECUTING) or arrived after the
    # winner committed (200 + already_executed=True, which is a documented no-op).
    assert winners.count(True) == 1, f"exactly one caller may execute, got {results}"
    assert paypal.mock.call_count == 1, "a duplicate execute must make no extra call"

    session = get_session_factory()()
    try:
        rows = list(
            session.scalars(
                select(AuditLog).where(
                    AuditLog.action_id == action["id"], AuditLog.event == "action_executed"
                )
            )
        )
    finally:
        session.close()
    assert len(rows) == 1


# ------------------------------------------------------------- the claim itself
def test_claim_is_conditional_on_approved(demo_client: TestClient) -> None:
    """The single guarantee that stops a duplicate external call.

    ``_claim`` is a conditional UPDATE: it may only succeed while the row is
    APPROVED. The second caller must lose, even if it read APPROVED a moment
    earlier. Eight-thread tests show the happy path; this one pins the rule.
    """
    action = _propose(demo_client, 2, "FLAG_FOR_REVIEW")
    _approve(demo_client, action["id"])

    session = get_session_factory()()
    try:
        first_token, first = action_service._claim(session, action["id"])  # noqa: SLF001
        assert first is not None
        assert first.status == "EXECUTING"
        assert first.claim_token == first_token

        second_token, second = action_service._claim(session, action["id"])  # noqa: SLF001
        assert second is None, "a second claim must lose while the row is EXECUTING"
        assert second_token != first_token
    finally:
        session.close()


# --------------------------------------------------------- failure classification
@pytest.mark.parametrize("mode", ["4xx", "connect"])
def test_known_failures_become_failed(
    demo_client: TestClient, paypal: PayPalService, mode: str
) -> None:
    action = _propose(demo_client, 13, "ADD_TRACKING", TRACKING)
    _approve(demo_client, action["id"])
    paypal.mock.failure_mode = mode

    status, body = _execute(demo_client, action["id"])

    assert status == 200
    assert body["status"] == "FAILED"
    assert body["error"]
    assert body["can_retry"] is True
    assert body["can_reconcile"] is False


@pytest.mark.parametrize("mode", ["timeout", "5xx", "reset", "crash"])
def test_possibly_applied_failures_become_unknown(
    demo_client: TestClient, paypal: PayPalService, mode: str
) -> None:
    action = _propose(demo_client, 14, "ADD_TRACKING", TRACKING)
    _approve(demo_client, action["id"])
    paypal.mock.failure_mode = mode

    status, body = _execute(demo_client, action["id"])

    assert status == 200
    assert body["status"] == "UNKNOWN"
    assert body["can_retry"] is False, "UNKNOWN must never offer a blind retry"
    assert body["can_reconcile"] is True


def test_retry_reuses_the_same_idempotency_key(
    demo_client: TestClient, paypal: PayPalService
) -> None:
    action = _propose(demo_client, 15, "ADD_TRACKING", TRACKING)
    _approve(demo_client, action["id"])
    paypal.mock.failure_mode = "4xx"
    _execute(demo_client, action["id"])

    before = demo_client.get(f"/api/actions/{action['id']}").json()
    paypal.mock.failure_mode = "ok"
    retried = demo_client.post(f"/api/actions/{action['id']}/retry")

    assert retried.status_code == 200
    assert retried.json()["status"] == "APPROVED"
    assert retried.json()["idempotency_key"] == before["idempotency_key"]

    status, body = _execute(demo_client, action["id"])
    assert status == 200
    assert body["status"] == "EXECUTED"
    assert body["idempotency_key"] == before["idempotency_key"]


def test_retry_from_unknown_is_409(demo_client: TestClient, paypal: PayPalService) -> None:
    action = _propose(demo_client, 2, "ADD_TRACKING", TRACKING)
    _approve(demo_client, action["id"])
    paypal.mock.failure_mode = "timeout"
    _execute(demo_client, action["id"])

    response = demo_client.post(f"/api/actions/{action['id']}/retry")

    assert response.status_code == 409
    assert "Reconcile" in response.json()["detail"]


def test_stale_claim_is_marked_unknown_and_never_re_executed(
    demo_client: TestClient, paypal: PayPalService
) -> None:
    action = _propose(demo_client, 3, "ADD_TRACKING", TRACKING)
    _approve(demo_client, action["id"])

    session = get_session_factory()()
    try:
        row = session.get(Action, action["id"])
        assert row is not None
        row.status = "EXECUTING"
        row.claim_token = "abandoned"
        row.claimed_at = utcnow() - timedelta(minutes=12)
        session.commit()
    finally:
        session.close()

    response = demo_client.post(f"/api/actions/{action['id']}/execute")

    assert response.status_code == 409
    assert _action_status(action["id"]) == "UNKNOWN"
    assert paypal.mock.call_count == 0


# ------------------------------------------------------------------- reconcile
def test_reconcile_applied_marks_executed_with_read_back_evidence(
    demo_client: TestClient, paypal: PayPalService
) -> None:
    action = _propose(demo_client, 4, "ADD_TRACKING", TRACKING)
    _approve(demo_client, action["id"])
    paypal.mock.failure_mode = "timeout"
    _execute(demo_client, action["id"])
    # The call actually landed: the mock remembers the tracking number.
    paypal.mock._tracking["MS-2004"] = TRACKING["tracking_number"]
    paypal.mock.failure_mode = "ok"

    response = demo_client.post(f"/api/actions/{action['id']}/reconcile", json={})

    assert response.status_code == 200
    assert response.json()["outcome"] == "APPLIED"
    after = demo_client.get(f"/api/actions/{action['id']}").json()
    assert after["status"] == "EXECUTED"
    assert after["result"]["read_back_tracking_number"] == TRACKING["tracking_number"]


def test_reconcile_not_applied_requires_confirmation(
    demo_client: TestClient, paypal: PayPalService
) -> None:
    action = _propose(demo_client, 5, "ADD_TRACKING", TRACKING)
    _approve(demo_client, action["id"])
    paypal.mock.failure_mode = "timeout"
    _execute(demo_client, action["id"])
    paypal.mock.failure_mode = "ok"

    refused = demo_client.post(f"/api/actions/{action['id']}/reconcile", json={})
    assert refused.status_code == 409
    assert _action_status(action["id"]) == "UNKNOWN"

    confirmed = demo_client.post(
        f"/api/actions/{action['id']}/reconcile", json={"confirm_not_applied": True}
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["outcome"] == "NOT_APPLIED"
    assert _action_status(action["id"]) == "APPROVED"

    audit = demo_client.get("/api/audit", params={"event": "action_reconciled"}).json()
    assert any(row["detail"].get("confirmed") is True for row in audit["items"])


def test_reconcile_read_error_is_indeterminate(
    demo_client: TestClient, paypal: PayPalService
) -> None:
    action = _propose(demo_client, 8, "ADD_TRACKING", TRACKING)
    _approve(demo_client, action["id"])
    paypal.mock.failure_mode = "timeout"
    _execute(demo_client, action["id"])
    paypal.mock.failure_mode = "timeout"  # the read-back also fails

    response = demo_client.post(f"/api/actions/{action['id']}/reconcile", json={})

    assert response.status_code == 200
    assert response.json()["outcome"] == "INDETERMINATE"
    assert _action_status(action["id"]) == "UNKNOWN"


def test_reconcile_on_a_non_unknown_action_is_409(
    demo_client: TestClient, paypal: PayPalService
) -> None:
    action = _propose(demo_client, 10, "FLAG_FOR_REVIEW")
    assert demo_client.post(f"/api/actions/{action['id']}/reconcile", json={}).status_code == 409


# ------------------------------------------------------------------ the agent
def test_agent_proposals_are_pending_and_cannot_execute(
    demo_client: TestClient, paypal: PayPalService
) -> None:
    body = demo_client.post("/api/orders/1/agent").json()

    assert body["proposals"], "the planner should propose something for the worst order"
    assert all(p["status"] == "PENDING" for p in body["proposals"])
    assert all(p["proposed_by"] == "AGENT" for p in body["proposals"])

    first = body["proposals"][0]
    status, payload = _execute(demo_client, first["id"])
    assert status == 409, "an unapproved agent proposal must not execute"
    assert paypal.mock.call_count == 0


def test_agent_planner_never_exceeds_six_steps(demo_client: TestClient) -> None:
    body = demo_client.post("/api/orders/1/agent").json()
    assert len(body["proposals"]) <= 6


# ------------------------------------------------------------------- the audit
def test_every_transition_writes_exactly_one_audit_row(
    demo_client: TestClient, paypal: PayPalService
) -> None:
    action = _propose(demo_client, 11, "ADD_TRACKING", TRACKING)
    _approve(demo_client, action["id"])
    _execute(demo_client, action["id"])

    rows = demo_client.get("/api/audit", params={"action_id": action["id"]}).json()["items"]
    events = [row["event"] for row in rows]
    assert events.count("action_proposed") == 1
    assert events.count("action_approved") == 1
    assert events.count("action_executed") == 1
    assert all(row["created_at"].endswith("Z") for row in rows)
