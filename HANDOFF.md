# MerchantShield AI — current handoff

**Updated:** 2026-11-24  
**Repository:** [ShoryaPratapSinghChandrawat/MerchantShield-AI](https://github.com/ShoryaPratapSinghChandrawat/MerchantShield-AI)

This file replaces an old Phase 0 handoff that described an earlier workspace
and is no longer an accurate description of the current repository.

## Current project state

MerchantShield AI is a sandbox-first prototype for helping small merchants
identify missing order evidence and prepare dispute-response material. The
repository contains the full application source at its root, a root-level
GitHub Actions workflow, documentation, scripts and a committed explainer
video.

The implementation includes:

- FastAPI backend and React/TypeScript frontend served as one application.
- Twenty-five deterministic order-risk rules with attributed explanations.
- A separate logistic-regression estimate trained on synthetic data.
- Evidence-readiness scoring and dispute evidence packets.
- Human-approved action proposals and an explicit execution/reconciliation
  state machine.
- PayPal Orders v2 Sandbox client code, with strict Sandbox-host validation.
- Optional Gemini draft provider with template fallback and a narrow factual
  guard.
- Source labels distinguishing `PAYPAL_SANDBOX`, `SIMULATED` and `MOCK`.

## Verification record and limits

The README records the latest full local verification on 2026-11-11:

- 215 backend tests passed in that recorded run.
- 16 Playwright tests across two viewport sizes (32 browser runs) passed.
- Two planner shipment-data safety regression tests were added on 2026-11-24; their execution result is pending and they are not included in the 215-test baseline.
- 16/16 applicable mutations were caught.
- TypeScript type-check and Vite build passed.
- A clean-copy quick start was recorded as verified in the Linux sandbox.

The same record states that GitHub Actions was green on the Phase 0 commit
`048cdd4`; CI for the later phases had not been verified at that time. A new
CI run should be inspected before treating the current main branch as CI-green.

**Not verified in the recorded build:**

- No live PayPal Sandbox request was made. The client was tested using mocked
  HTTP transports; the demo defaults to the local mock adapter.
- No live Gemini request was made. The default response-drafting path uses
  deterministic templates.
- Dispute submission/evidence upload to PayPal is not implemented; submission
  is simulated.
- No Windows machine executed the build.
- The synthetic-data model does not establish real-world predictive accuracy.
- The local SQLite audit log is not tamper-evident.

## How to evaluate the current checkout

1. Start with [REVIEWER_GUIDE.md](REVIEWER_GUIDE.md).
2. Follow the quick-start instructions in [README.md](README.md).
3. Run the guided **Run the story** walkthrough.
4. Inspect [AI_DISCLOSURE.md](AI_DISCLOSURE.md) and
   [DEVPOST_TEXT.md](DEVPOST_TEXT.md) for the exact AI and integration boundaries.
5. Use [DECISIONS.md](DECISIONS.md) and [BUGS_FIXED.md](BUGS_FIXED.md) for
   design rationale and documented defects.

## Work still needed for a more complete product

These are future product-development tasks, not capabilities claimed by this
checkout:

1. Run and record the credentialed PayPal Sandbox verification script.
2. Add and test the supported PayPal Disputes API workflow before claiming
   evidence submission.
3. Run the Gemini path with a real key and retain a redacted verification
   record.
4. Validate model usefulness on real, consented and properly governed merchant
   data before making predictive claims.
5. Obtain Windows verification and a current full CI run.
6. Consider external or tamper-evident audit storage before production use.
