"""LLM wrapper: ``gemini`` and ``none``, strict JSON, templates of the same shape.

Design rules that matter for the honesty story:

* The app must work with **no key at all**. ``LLM_PROVIDER=none`` (the default)
  produces deterministic templates, and every draft says which one it is:
  "AI draft" or "Template draft" (MASTER 10.8).
* Output is parsed strictly: code fences stripped, JSON required, one retry,
  then the template fallback with the SAME shape. A malformed model reply can
  never break a page.
* The **hallucination guard** rejects any draft that mentions a tracking
  number, date, amount or identifier that is not present in the facts we
  supplied, and the caller records ``hallucination_guard_triggered`` in the
  audit log.

No live Gemini call has ever been made from this project (no key). The HTTP
shape below follows Google's documented ``generateContent`` REST call; it is in
DECISIONS.md under "UNVERIFIED PAYPAL CALLS / UNVERIFIED LLM CALLS" until a
real key produces a real response.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"

ORIGIN_AI = "AI draft"
ORIGIN_TEMPLATE = "Template draft"

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


@dataclass
class LLMResult:
    """Every LLM call returns this, whether a model ran or not."""

    payload: dict[str, Any]
    origin: str
    provider: str
    fallback_reason: str | None = None
    raw: str = ""
    guard_triggered: bool = False
    invented: list[str] = field(default_factory=list)

    @property
    def used_model(self) -> bool:
        return self.origin == ORIGIN_AI


# --------------------------------------------------------------------- parsing
def strip_code_fences(text: str) -> str:
    match = _FENCE_RE.search(text)
    return (match.group(1) if match else text).strip()


def parse_json_object(text: str) -> dict[str, Any] | None:
    """Best-effort strict parse. Returns None rather than raising."""
    candidate = strip_code_fences(text)
    for attempt in (candidate, candidate[candidate.find("{") : candidate.rfind("}") + 1]):
        if not attempt:
            continue
        try:
            value = json.loads(attempt)
        except (TypeError, ValueError):
            continue
        if isinstance(value, dict):
            return value
    return None


# --------------------------------------------------------------- hallucination
#: A tracking-like token: at least 8 characters that mix letters and
#: digits, or a run of 10+ digits. Chosen to catch real carrier formats
#: (1Z999AA10123456784, 9400111899223197428490, ES123456789012).
_TRACKING_TOKEN = re.compile(r"\b(?=[A-Z0-9]*[A-Z])(?=[A-Z0-9]*[0-9])[A-Z0-9]{8,}\b")
_LONG_DIGITS = re.compile(r"\b\d{10,}\b")
_ISO_DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
_AMOUNT = re.compile(r"\$\s?\d+(?:[.,]\d{2})?")


def extract_facts(text: str) -> set[str]:
    """Every entity-looking token a reader could take as a material fact."""
    found: set[str] = set()
    found.update(_TRACKING_TOKEN.findall(text or ""))
    found.update(_LONG_DIGITS.findall(text or ""))
    found.update(_ISO_DATE.findall(text or ""))
    found.update(a.replace(" ", "") for a in _AMOUNT.findall(text or ""))
    return found


def allowed_facts_for(facts: dict[str, Any]) -> set[str]:
    """The complete fact set a draft may use, including bare numbers.

    ``extract_facts`` only sees entities with recognisable shapes (a tracking
    number, an ISO date, a $ amount). An order's amount is stored bare
    ("1899.00"), so it has to be added explicitly or the guard would reject the
    app's own true fact.
    """
    allowed = extract_facts(_facts_block(facts))
    for key in ("order_ref", "amount", "currency", "buyer_name", "item_name"):
        value = facts.get(key)
        if value:
            allowed.add(str(value))
    amount = str(facts.get("amount", "") or "")
    if amount:
        allowed.add(f"${amount}".replace(",", ""))
    return allowed


def _normalise_token(value: str) -> str:
    """Compare "$1,899.00", "1899.00" and "1899.00 " as the same fact."""
    return re.sub(r"[\s,$]", "", value).upper()


def hallucination_guard(text: str, allowed_facts: set[str]) -> tuple[bool, list[str]]:
    """True when the draft invents nothing beyond the facts we handed over."""
    normalised_allowed = {_normalise_token(fact) for fact in allowed_facts}
    normalised_allowed.discard("")
    invented: list[str] = []
    for token in extract_facts(text):
        if _normalise_token(token) not in normalised_allowed:
            invented.append(token)
    return (len(invented) == 0), sorted(invented)


# --------------------------------------------------------------------- prompts
SYSTEM_RULES = (
    "You write short, factual merchant messages for a payment-dispute tool. "
    "Use ONLY the facts in the JSON you are given. Never invent a tracking "
    "number, a date, an amount or a person. If a fact is absent, do not "
    "mention it. Reply with a single JSON object and nothing else."
)


def _facts_block(facts: dict[str, Any]) -> str:
    return json.dumps(facts, indent=2, sort_keys=True, default=str)


# ------------------------------------------------------------------- providers
class LLMClient:
    """Provider dispatch. ``none`` never opens a socket."""

    def __init__(self, settings: Settings | None = None, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.settings = settings or get_settings()
        self.transport = transport
        self.provider = self.settings.llm_provider
        self.model = self.settings.llm_model or DEFAULT_GEMINI_MODEL
        self.calls = 0

    @property
    def enabled(self) -> bool:
        return self.provider == "gemini" and bool(self.settings.llm_api_key)

    async def _gemini_json(self, prompt: str) -> tuple[dict[str, Any] | None, str | None]:
        """One call, one retry, then None. Returns (payload, failure_reason)."""
        if not self.enabled:  # pragma: no cover - guarded by callers
            return None, "provider-disabled"

        body = {
            "system_instruction": {"parts": [{"text": SYSTEM_RULES}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"},
        }
        url = GEMINI_ENDPOINT.format(model=self.model)
        last_reason = "no-attempt"
        for attempt in range(2):
            self.calls += 1
            try:
                async with httpx.AsyncClient(timeout=20.0, transport=self.transport) as client:
                    response = await client.post(
                        url,
                        params={"key": self.settings.llm_api_key or ""},
                        json=body,
                    )
            except Exception as exc:  # network problems must never break a page
                last_reason = f"{type(exc).__name__}"
                continue
            if response.status_code != 200:
                last_reason = f"http-{response.status_code}"
                continue
            try:
                data = response.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"]
            except (KeyError, IndexError, ValueError, TypeError):
                last_reason = "unexpected-shape"
                continue
            parsed = parse_json_object(text)
            if parsed is None:
                last_reason = "unparsable-json"
                continue
            return parsed, None
        return None, last_reason


# ------------------------------------------------------------------ templates
def template_buyer_message(facts: dict[str, Any]) -> dict[str, Any]:
    item = facts.get("item_name", "your order")
    reference = facts.get("order_ref", "your order")
    shipping = facts.get("shipping_summary") or "Shipping details are being prepared."
    return {
        "subject": f"Update on {reference}",
        "body": (
            f"Hello {facts.get('buyer_name', 'there')}, thank you for your order of "
            f"{item}. {shipping} If anything is unclear, reply to this message and "
            "we will help. This message was written from your order record only."
        ),
        "facts_used": ["order_ref", "item_name", "shipping_summary"],
    }


def template_dispute_response(facts: dict[str, Any]) -> dict[str, Any]:
    lines = [
        f"Order {facts.get('order_ref', '')} - {facts.get('item_name', '')}",
        "",
        f"The buyer states: {facts.get('buyer_claim', 'a problem with the order')}.",
        "",
        "Our record shows:",
    ]
    for key in (
        "tracking_summary",
        "delivery_summary",
        "communication_summary",
        "policy_summary",
    ):
        value = facts.get(key)
        if value:
            lines.append(f"- {value}")
    missing = facts.get("missing_evidence") or []
    if missing:
        lines.append("")
        lines.append("Evidence we are still gathering: " + ", ".join(missing) + ".")
    lines.extend(
        [
            "",
            "We ask that this evidence be considered before the case is decided. "
            "We are happy to provide anything else that would help.",
        ]
    )
    return {
        "body": "\n".join(lines),
        "missing_evidence": list(missing),
        "strategy_note": (
            "Lead with delivery confirmation if present; otherwise lead with the "
            "tracking trail and the buyer's own messages."
        ),
        "facts_used": [k for k in facts if k != "missing_evidence"],
    }


# ------------------------------------------------------------------- public API
async def draft_buyer_message(
    facts: dict[str, Any], client: LLMClient | None = None
) -> LLMResult:
    """Draft a merchant -> buyer message. Never invents facts (guarded)."""
    llm = client or LLMClient()
    template = template_buyer_message(facts)
    allowed = allowed_facts_for(facts)

    if not llm.enabled:
        return LLMResult(payload=template, origin=ORIGIN_TEMPLATE, provider=llm.provider,
                         fallback_reason="no-key-or-provider-none")

    prompt = (
        "Draft a short, polite merchant message about this order.\n"
        f"Facts:\n{_facts_block(facts)}\n"
        'Return JSON: {"subject": str, "body": str}.'
    )
    parsed, reason = await llm._gemini_json(prompt)  # noqa: SLF001 - same module family
    if parsed is None or "body" not in parsed:
        return LLMResult(payload=template, origin=ORIGIN_TEMPLATE, provider=llm.provider,
                         fallback_reason=reason or "bad-shape")

    guard_ok, invented = hallucination_guard(str(parsed.get("body", "")), allowed)
    if not guard_ok:
        return LLMResult(
            payload=template,
            origin=ORIGIN_TEMPLATE,
            provider=llm.provider,
            fallback_reason="hallucination-guard",
            guard_triggered=True,
            invented=invented,
            raw=str(parsed.get("body", ""))[:2000],
        )
    return LLMResult(
        payload={"subject": parsed.get("subject", ""), "body": parsed.get("body", "")},
        origin=ORIGIN_AI,
        provider=llm.provider,
        raw=str(parsed)[:2000],
    )


async def draft_dispute_response(
    facts: dict[str, Any], client: LLMClient | None = None
) -> LLMResult:
    """Draft a 150-300 word dispute response plus a strategy note."""
    llm = client or LLMClient()
    template = template_dispute_response(facts)
    allowed = allowed_facts_for(facts)

    if not llm.enabled:
        return LLMResult(payload=template, origin=ORIGIN_TEMPLATE, provider=llm.provider,
                         fallback_reason="no-key-or-provider-none")

    prompt = (
        "Write a 150-300 word dispute response for this PayPal case. Facts only.\n"
        f"Facts:\n{_facts_block(facts)}\n"
        'Return JSON: {"body": str, "missing_evidence": [str], "strategy_note": str}.'
    )
    parsed, reason = await llm._gemini_json(prompt)
    if parsed is None or "body" not in parsed:
        return LLMResult(payload=template, origin=ORIGIN_TEMPLATE, provider=llm.provider,
                         fallback_reason=reason or "bad-shape")

    body = str(parsed.get("body", ""))
    guard_ok, invented = hallucination_guard(body, allowed)
    if not guard_ok:
        return LLMResult(
            payload=template,
            origin=ORIGIN_TEMPLATE,
            provider=llm.provider,
            fallback_reason="hallucination-guard",
            guard_triggered=True,
            invented=invented,
            raw=body[:2000],
        )
    return LLMResult(
        payload={
            "body": body,
            "missing_evidence": list(parsed.get("missing_evidence") or []),
            "strategy_note": str(parsed.get("strategy_note", "")),
        },
        origin=ORIGIN_AI,
        provider=llm.provider,
        raw=body[:2000],
    )


def classify_message(text: str) -> dict[str, Any]:
    """Cheap deterministic intent classification used by Phase 6's inbox."""
    from app.services.risk_rules import keyword_hits

    hits = keyword_hits(text)
    if hits:
        intent = "dispute_risk"
    elif "?" in text:
        intent = "question"
    else:
        intent = "neutral"
    return {"intent": intent, "keywords": hits, "provider": "rules", "origin": ORIGIN_TEMPLATE}
