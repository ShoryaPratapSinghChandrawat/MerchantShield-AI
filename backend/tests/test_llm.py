"""Phase 6: the LLM wrapper, its fallbacks and the hallucination guard.

No live model is called: the only transport used here is httpx.MockTransport.
"""

from __future__ import annotations

import json

import httpx
import pytest

from app.core.config import Settings
from app.services import llm

FACTS = {
    "order_ref": "MS-2001",
    "buyer_name": "Daniel Reyes",
    "item_name": "Aurora X2 laptop, 16GB",
    "amount": "1899.00",
    "currency": "USD",
    "buyer_claim": "The parcel never arrived.",
    "tracking_summary": None,
    "delivery_summary": None,
    "communication_summary": "Buyer communication logged: 1 message(s)",
    "policy_summary": None,
    "shipping_summary": "Shipping details are being prepared.",
    "missing_evidence": ["Tracking number", "Delivery confirmation"],
}


def _settings(provider: str, key: str | None) -> Settings:
    return Settings(demo_mode=True, llm_provider=provider, llm_api_key=key, llm_model="test-model")


def _client_returning(text: str) -> llm.LLMClient:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"candidates": [{"content": {"parts": [{"text": text}]}}]}
        )

    return llm.LLMClient(settings=_settings("gemini", "test-key"), transport=httpx.MockTransport(handler))


# --------------------------------------------------------------------- parsing
def test_code_fences_are_stripped() -> None:
    assert llm.parse_json_object('```json\n{"a": 1}\n```') == {"a": 1}


def test_unparsable_text_returns_none() -> None:
    assert llm.parse_json_object("not json at all") is None


def test_parse_accepts_surrounding_prose() -> None:
    assert llm.parse_json_object('Here you go: {"a": 2} - done') == {"a": 2}


# ------------------------------------------------------------------ no-key path
async def test_no_provider_returns_a_template_and_says_so() -> None:
    client = llm.LLMClient(settings=_settings("none", None))
    result = await llm.draft_buyer_message(FACTS, client)

    assert result.origin == llm.ORIGIN_TEMPLATE
    assert set(result.payload) >= {"subject", "body"}
    assert result.fallback_reason == "no-key-or-provider-none"


async def test_gemini_without_a_key_also_uses_the_template() -> None:
    client = llm.LLMClient(settings=_settings("gemini", None))
    result = await llm.draft_dispute_response(FACTS, client)

    assert result.origin == llm.ORIGIN_TEMPLATE
    assert "missing_evidence" in result.payload
    assert "strategy_note" in result.payload


# --------------------------------------------------------------- guard + fallback
def test_hallucination_guard_catches_an_invented_tracking_number() -> None:
    allowed = llm.allowed_facts_for(FACTS)
    text = "Your parcel 1Z999AA10123456784 arrives tomorrow."
    ok, invented = llm.hallucination_guard(text, allowed)

    assert ok is False
    assert invented == ["1Z999AA10123456784"]


def test_hallucination_guard_catches_an_invented_date_and_amount() -> None:
    allowed = llm.allowed_facts_for(FACTS)
    ok, invented = llm.hallucination_guard("Shipped 2026-01-01 for $42.00", allowed)

    assert ok is False
    assert "2026-01-01" in invented
    assert "$42.00" in invented


def test_hallucination_guard_allows_facts_that_were_supplied() -> None:
    allowed = llm.allowed_facts_for(FACTS)
    ok, invented = llm.hallucination_guard("Order MS-2001 was paid $1899.00", allowed)
    assert ok is True
    assert invented == []


async def test_model_output_with_an_invented_fact_is_replaced() -> None:
    body = json.dumps(
        {
            "subject": "Update",
            "body": "Your parcel 1Z999AA10123456784 is on the way.",
        }
    )
    result = await llm.draft_buyer_message(FACTS, _client_returning(body))

    assert result.guard_triggered is True
    assert result.origin == llm.ORIGIN_TEMPLATE
    assert result.fallback_reason == "hallucination-guard"
    assert "1Z999AA10123456784" not in result.payload["body"]


async def test_clean_model_output_is_used_and_labelled_ai() -> None:
    body = json.dumps(
        {
            "subject": "Update on MS-2001",
            "body": f"Hello Daniel Reyes, we are checking your order {FACTS['item_name']}.",
        }
    )
    result = await llm.draft_buyer_message(FACTS, _client_returning(body))

    assert result.origin == llm.ORIGIN_AI
    assert result.guard_triggered is False


async def test_unparsable_model_output_falls_back_after_one_retry() -> None:
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "nope"}]}}]})

    client = llm.LLMClient(settings=_settings("gemini", "test-key"), transport=httpx.MockTransport(handler))
    result = await llm.draft_dispute_response(FACTS, client)

    assert calls["count"] == 2, "the wrapper retries exactly once"
    assert result.fallback_reason == "unparsable-json"
    assert result.origin == llm.ORIGIN_TEMPLATE


async def test_http_error_falls_back_without_crashing() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": "rate limited"})

    client = llm.LLMClient(settings=_settings("gemini", "test-key"), transport=httpx.MockTransport(handler))
    result = await llm.draft_buyer_message(FACTS, client)

    assert result.origin == llm.ORIGIN_TEMPLATE
    assert result.fallback_reason == "http-429"


# ------------------------------------------------------------------ classifier
def test_classify_message_uses_rules_and_reports_template_origin() -> None:
    assert llm.classify_message("I want a refund")["intent"] == "dispute_risk"
    assert llm.classify_message("Where is my parcel?")["intent"] == "question"
    assert llm.classify_message("Thanks")["intent"] == "neutral"
    assert llm.classify_message("Thanks")["origin"] == llm.ORIGIN_TEMPLATE
