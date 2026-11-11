"""Phase 6: dispute defence flow - packet, versions, approval, labelled submit."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _open(client: TestClient, order_id: int) -> dict:
    response = client.post(f"/api/disputes/orders/{order_id}/open")
    assert response.status_code == 201, response.text
    return response.json()


def test_opening_a_dispute_is_idempotent(demo_client: TestClient) -> None:
    first = _open(demo_client, 1)
    second = _open(demo_client, 1)

    assert first["id"] == second["id"]
    assert first["source"] == "SIMULATED"
    assert demo_client.get("/api/disputes").json()["count"] == 1


def test_packet_lists_evidence_and_never_predicts(demo_client: TestClient) -> None:
    dispute = _open(demo_client, 1)
    packet = demo_client.get(f"/api/disputes/{dispute['id']}/packet").json()

    assert len(packet["evidence"]) == 7
    assert packet["evidence_strength"]["max"] == 100
    assert "not a prediction" in packet["note"].lower()
    assert packet["timeline"][0]["at"].endswith("Z")


def test_draft_without_a_key_is_a_labelled_template(demo_client: TestClient) -> None:
    dispute = _open(demo_client, 1)

    created = demo_client.post(f"/api/disputes/{dispute['id']}/drafts", json={})
    assert created.status_code == 201
    draft = created.json()

    assert draft["origin"] == "Template draft"
    assert draft["version"] == 1
    assert draft["label"] is None, "only AI drafts carry the AI notice"
    assert draft["body"]


def test_editing_creates_a_new_version_instead_of_overwriting(demo_client: TestClient) -> None:
    dispute = _open(demo_client, 1)
    demo_client.post(f"/api/disputes/{dispute['id']}/drafts", json={})
    edited = demo_client.post(
        f"/api/disputes/{dispute['id']}/drafts", json={"body": "Merchant rewritten text."}
    ).json()

    assert edited["version"] == 2
    assert edited["origin"] == "Merchant edit"

    drafts = demo_client.get(f"/api/disputes/{dispute['id']}").json()["drafts"]
    assert [d["version"] for d in drafts] == [2, 1]


def test_submit_requires_an_approved_draft(demo_client: TestClient) -> None:
    dispute = _open(demo_client, 1)
    demo_client.post(f"/api/disputes/{dispute['id']}/drafts", json={})

    response = demo_client.post(f"/api/disputes/{dispute['id']}/submit")

    assert response.status_code == 409
    assert "approved draft" in response.json()["detail"]


def test_full_submit_flow_is_labelled_simulated(demo_client: TestClient) -> None:
    dispute = _open(demo_client, 1)
    draft = demo_client.post(f"/api/disputes/{dispute['id']}/drafts", json={}).json()
    approved = demo_client.post(
        f"/api/disputes/{dispute['id']}/drafts/{draft['draft_id']}/approve"
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "APPROVED"

    submitted = demo_client.post(f"/api/disputes/{dispute['id']}/submit").json()

    assert submitted["submission_mode"] == "SIMULATED"
    assert submitted["source"] == "SIMULATED"
    assert "no PayPal dispute API call was made" in submitted["note"]

    detail = demo_client.get(f"/api/disputes/{dispute['id']}").json()
    assert detail["status"] == "SUBMITTED"
    assert detail["submitted_at"].endswith("Z")


def test_approve_returns_the_same_full_draft_shape_as_create(demo_client: TestClient) -> None:
    """Regression: a short approve payload broke the strict frontend mapper.

    The approval persisted but the card never refreshed, so the merchant saw
    "DRAFT" for a draft that was already approved.
    """
    dispute = _open(demo_client, 1)
    created = demo_client.post(f"/api/disputes/{dispute['id']}/drafts", json={}).json()
    approved = demo_client.post(
        f"/api/disputes/{dispute['id']}/drafts/{created['draft_id']}/approve"
    ).json()

    assert approved["status"] == "APPROVED"
    assert set(created) == set(approved)
    assert approved["body"] == created["body"]
    assert approved["origin"] == created["origin"]
    assert isinstance(approved["missing_evidence"], list)


def test_unknown_dispute_is_404(demo_client: TestClient) -> None:
    assert demo_client.get("/api/disputes/999").status_code == 404
    assert demo_client.get("/api/disputes/999/packet").status_code == 404
    assert demo_client.post("/api/disputes/orders/9999/open").status_code == 404
