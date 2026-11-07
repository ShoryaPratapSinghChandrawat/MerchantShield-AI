"""Phase 0 test 1 - GET /api/health."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_returns_ok_and_honest_flags(demo_client: TestClient) -> None:
    response = demo_client.get("/api/health")

    assert response.status_code == 200
    body = response.json()

    assert body["status"] == "ok"
    assert body["phase"] == "0"
    assert body["demo_mode"] is True
    assert body["paypal_mode"] == "mock"
    # No credentials were configured for the test run.
    assert body["paypal_credentials_present"] is False


def test_health_never_leaks_secrets(demo_client: TestClient) -> None:
    """The health payload must expose booleans about credentials, not values."""
    body = demo_client.get("/api/health").json()

    forbidden = {"paypal_client_id", "paypal_client_secret", "llm_api_key"}
    assert forbidden.isdisjoint(body.keys())
