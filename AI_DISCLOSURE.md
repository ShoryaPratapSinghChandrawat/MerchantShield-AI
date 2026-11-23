# AI disclosure

This document separates **AI used during development** from **AI functionality
inside the product**. It describes the tools and behaviors recorded in this
repository; it does not assign an estimated percentage of authorship.

Last reviewed: 2026-11-24.

## 1. AI used during development

AI coding assistants were used as development tools for work recorded in the
project history, including:

- Drafting and expanding automated test cases for the Python backend and
  Playwright browser suite from project requirements.
- Generating or shaping mock/test data and repetitive test or CI boilerplate.
- Supporting syntax checks and iterative debugging.
- Synthesising narration for the explainer video. The application footage in
  that video was captured from the running project.

The human developer defined the product scope and acceptance criteria, made the
architecture and safety decisions, implemented and integrated the application,
and reviewed the resulting code and test output.

**No quantitative human/AI authorship ratio is claimed.** A percentage inferred
by an AI tool would not be a reproducible measurement of code authorship, so
this repository intentionally does not publish one.

## 2. AI and machine learning inside the product

The product contains several distinct mechanisms. They should not be described
as though they are all generative AI.

| Component | What it actually does | Important boundary |
| --- | --- | --- |
| Rule-based risk engine | Applies 25 hand-written, explainable rules and shows the reasons and point contributions | Deterministic rules, not an AI model |
| Logistic-regression estimate | Produces a separate estimate from seven order features | Trained offline on synthetic labels derived from the rule system, with 8% label noise; not trained on PayPal or merchant outcomes and not evidence of real-world predictive performance |
| Agent planner | Builds a bounded list of suggested actions from missing evidence and the rule assessment | Deterministic by default; optional suggestions are filtered through a fixed action allowlist; it cannot approve or execute |
| Gemini draft provider | Can generate a dispute-response draft from supplied case facts when configured with a Gemini API key | Optional provider; a live Gemini request was not performed in the recorded build. The default demo uses deterministic templates |
| Factual guard | Checks supported fact patterns such as tracking-like identifiers, long numbers, ISO dates and currency amounts against supplied facts; rejects a draft when an unsupported fact is found | Narrow guard, not a general-purpose truth detector |
| Human approval | Requires a merchant to approve an action before the action protocol can execute it | No autonomous payment or dispute action |

### What the recorded demo actually uses

- The demo runs without an API key.
- Its dispute-response drafts are deterministic templates.
- The order risk estimate is the locally trained synthetic-data logistic-regression
  prototype and is labelled `ESTIMATE`.
- The planner follows deterministic policy rules unless optional model
  suggestions are explicitly configured.
- No live Gemini request was recorded.

## 3. PayPal integration status

The repository contains a PayPal Orders v2 REST client designed for the
**Sandbox host only**. It implements OAuth token handling, order creation,
capture, order read-back and tracking operations. The app distinguishes
`PAYPAL_SANDBOX`, `SIMULATED` and `MOCK` provenance.

However, the recorded build did **not** make a live PayPal Sandbox API call:
the HTTP client was tested with mocked transports because no Sandbox
credentials were supplied. The default demo uses the local mock adapter.

Dispute evidence packet generation and response drafting exist in the app, but
submission to PayPal's Disputes API is **not implemented**. The submit action is
recorded as `SIMULATED`. No production PayPal endpoint is allowed, and no real
money is moved.

## 4. Verification boundaries

The test counts and build results in the README are historical measurements
recorded on 2026-11-11 in a Linux sandbox / clean repository copy. They are not
a claim that this document edit has re-run those tests. The README also
distinguishes the earlier green Phase 0 CI run from later phases whose CI status
was not verified at the time of that record.

For current setup and the exact verification steps, see
[README.md](README.md), [REVIEWER_GUIDE.md](REVIEWER_GUIDE.md), and
[DECISIONS.md](DECISIONS.md).

## 5. Safety constraints

1. AI-generated text may only use case facts supplied to it; unsupported facts
   trigger the narrow factual guard and template fallback.
2. The planner can propose actions from a fixed allowlist but cannot approve
   them or call the executor.
3. Every external PayPal interaction is Sandbox-only.
4. An uncertain external outcome is recorded as `UNKNOWN`, not silently
   retried or reported as successful.
5. Risk-model output is an estimate from synthetic data, not a dispute-win
   probability or a promise of money saved.
