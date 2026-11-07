"""Rule R4 - production PayPal hostnames are rejected at startup.

Pulled forward from Phase 5 because it is a safety rule, not a feature: there
must be no point in the project's history where a production host is reachable.
"""

from __future__ import annotations

import pytest

from app.core.config import (
    DEFAULT_PAYPAL_SANDBOX_BASE_URL,
    ProductionPayPalHostError,
    Settings,
    validate_paypal_base_url,
)

PRODUCTION_HOSTS = [
    "https://api-m.paypal.com",
    "https://api.paypal.com",
    # Trailing-slash variants: a stray slash must not change the verdict.
    "https://api-m.paypal.com/",
    "https://api.paypal.com/",
    # Upper-case variants: hostnames are case-insensitive, and a config file
    # written in capitals must not slip past the guard.
    "https://API-M.PAYPAL.COM",
    "https://API.PAYPAL.COM/",
    "HTTPS://API.PAYPAL.COM/",
    "https://www.paypal.com",
    "https://paypal.com",
    "http://api-m.paypal.com",
    # Look-alikes that must not be mistaken for the sandbox host.
    "https://api-m.sandbox.paypal.com.evil.test",
    "https://sandbox.paypal.com.attacker.example",
]

SANDBOX_HOSTS = [
    "https://api-m.sandbox.paypal.com",
    "https://api-m.sandbox.paypal.com/",
    "https://API-M.SANDBOX.PAYPAL.COM",
    "https://api.sandbox.paypal.com",
]


@pytest.mark.parametrize("url", PRODUCTION_HOSTS)
def test_production_hosts_are_rejected(url: str) -> None:
    with pytest.raises(ProductionPayPalHostError):
        validate_paypal_base_url(url)


@pytest.mark.parametrize("url", SANDBOX_HOSTS)
def test_sandbox_hosts_are_accepted(url: str) -> None:
    assert validate_paypal_base_url(url).startswith("https://")


def test_default_base_url_is_the_documented_sandbox_host() -> None:
    assert DEFAULT_PAYPAL_SANDBOX_BASE_URL == "https://api-m.sandbox.paypal.com"
    assert Settings().paypal_base_url == DEFAULT_PAYPAL_SANDBOX_BASE_URL


def test_settings_refuse_to_construct_with_a_production_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PAYPAL_BASE_URL", "https://api-m.paypal.com")
    with pytest.raises(ValueError):
        Settings()


def test_safe_dump_contains_no_secret_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PAYPAL_CLIENT_ID", "client-id-should-never-appear")
    monkeypatch.setenv("PAYPAL_CLIENT_SECRET", "client-secret-should-never-appear")
    monkeypatch.setenv("LLM_API_KEY", "llm-key-should-never-appear")

    dumped = repr(Settings().safe_dump())

    assert "should-never-appear" not in dumped
    assert Settings().safe_dump()["paypal_credentials_present"] is True
