"""GET /api/health - liveness plus honest mode flags."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_returns_ok_and_honest_flags(demo_client: TestClient) -> None:
    response = demo_client.get("/api/health")

    assert response.status_code == 200
    body = response.json()

    assert body["status"] == "ok"
    assert body["phase"] == "7"
    assert body["demo_mode"] is True
    assert body["paypal_mode"] == "mock"
    # No credentials were configured for the test run.
    assert body["paypal_credentials_present"] is False
    # The LLM runs on templates when no key is present (MASTER 10.8).
    assert body["llm_provider"] == "none"


def test_health_never_leaks_secrets(demo_client: TestClient) -> None:
    """The health payload must expose booleans about credentials, not values."""
    body = demo_client.get("/api/health").json()

    forbidden = {"paypal_client_id", "paypal_client_secret", "llm_api_key"}
    assert forbidden.isdisjoint(body.keys())
    # Nothing anywhere in the payload may contain a configured secret value.
    assert "client_secret" not in str(body).lower()
