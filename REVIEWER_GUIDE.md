# Reviewer guide

MerchantShield AI is a sandbox-first prototype for improving merchant evidence
readiness and dispute preparation. This guide is designed to help a reviewer
understand the working path, the architecture and the limits without guessing.

## 1. Fastest way to see the product

Use the Windows 11 / PowerShell quick start in [README.md](README.md). The
default path is deliberately credential-free:

- `DEMO_MODE=true`
- `PAYPAL_MODE=mock`
- no PayPal credentials
- no Gemini API key

Open <http://127.0.0.1:8000> and click **Run the story** on the Overview page.
This uses clearly labelled mock and simulated records. It does not contact
PayPal or move money.

## 2. Suggested reviewer walkthrough

1. **Overview:** start the guided story and see the seeded merchant/order
   context.
2. **Orders:** inspect a flagged order and its attributed reasons from the
   25-rule engine.
3. **Evidence:** compare what is present with the evidence items that remain
   missing.
4. **Action inbox:** inspect the proposed action. It starts as `PENDING`;
   approve or reject it explicitly.
5. **Execution and audit:** follow the state transition and inspect the stored
   source label and audit record. In mock mode, the result is `MOCK`, not a
   real PayPal response. The planner's example tracking value is explicitly
   limited to synthetic/mock walkthrough rows; it is not proposed for non-demo
   orders.
6. **Disputes:** inspect the evidence packet and response draft. The default
   draft is a deterministic template. The submit path is simulated.

## 3. Architecture map

| Layer | Location | Responsibility |
| --- | --- | --- |
| API and application startup | `backend/app/main.py`, `backend/app/api/` | FastAPI app, routes and SPA serving |
| Risk rules | `backend/app/services/risk_rules.py` | 25 attributed deterministic rules |
| Evidence readiness | `backend/app/services/evidence_score.py` | Evidence checklist/strength score |
| Action planning | `backend/app/services/agent.py` | Bounded, deterministic action proposals |
| Action execution | `backend/app/services/actions.py` | Human approval, state machine, local atomic claim |
| PayPal adapter | `backend/app/services/paypal_client.py`, `paypal_service.py` | Orders v2 Sandbox client and mock selection |
| Model estimate | `backend/app/services/risk_model.py`, `backend/ml/` | Synthetic-data logistic-regression estimate |
| Drafting | `backend/app/services/llm.py` | Optional Gemini adapter and deterministic template fallback |
| Frontend | `frontend/src/` | React/TypeScript user experience |
| Browser tests | `frontend/e2e/` | Playwright end-to-end checks |
| Backend tests | `backend/tests/` | pytest coverage |

## 4. What is real, local, simulated or unverified

| Capability | Current status |
| --- | --- |
| Risk rules and evidence checklist | Implemented locally; deterministic |
| ML risk estimate | Implemented locally; synthetic training labels derived from the rule system |
| Action approval/state machine | Implemented locally; database transitions tested |
| PayPal Orders v2 client | Implemented for Sandbox; recorded live API verification was not run |
| Default checkout and PayPal responses | Local mock adapter; records labelled `MOCK` |
| Seeded walkthrough records | Locally generated; records labelled `SIMULATED` |
| Gemini drafting | Optional integration; live request not recorded |
| Default dispute-response drafts | Deterministic templates |
| Factual guard | Narrow checks for selected tracking/number/date/amount patterns, not a general fact checker |
| Dispute evidence packet | Generated inside the application |
| PayPal Disputes API submission | Not implemented; app marks submission `SIMULATED` |
| Buyer communication | Recorded inside the app; no email or external message is sent |
| Carrier verification | Not implemented; tracking numbers are recorded, not verified |
| Production PayPal | Structurally blocked by the Sandbox-host guard |

## 5. Verification evidence

The README's last recorded full local test run is dated 2026-11-11:

- 215 backend tests passed in the 2026-11-11 recorded run.
- Two additional planner shipment-data safety tests were added on 2026-11-24; they have not yet been run in a verified environment.
- 16 Playwright tests × 2 viewport sizes = 32 browser runs passed.
- 16/16 applicable mutations were caught.
- TypeScript strict type-check and Vite build passed.

Those figures are reproduced as historical evidence; this guide edit has not
re-run those tests. At the time of the README record, all three CI jobs were
green on Phase 0 commit `048cdd4`, while later phases had not been verified
in CI. Check the Actions tab for the result of the latest run before relying on
a current CI claim.

## 6. Model and data limitations

The logistic-regression model is trained from synthetic examples labelled from
the same hand-written rule logic, with 8% label noise. Its reported accuracy
and ROC AUC therefore describe a controlled synthetic benchmark. They do not
show that the model predicts actual PayPal disputes or merchant losses.

The Gemini integration is optional. No live Gemini request was recorded for
this build; the walkthrough uses deterministic templates. The factual guard
checks selected entity patterns against the supplied packet and is not a
general-purpose hallucination detector.

## 7. PayPal safety and limitations

The PayPal client is restricted to Sandbox hosts. The recorded build has not
made a live Sandbox call because credentials were not available. The
credentialed verification script is
[`scripts/verify_paypal_live.py`](scripts/verify_paypal_live.py); it requests
an OAuth token, creates a $1.00 Sandbox order and reads it back. It does not
capture the order or file a dispute.

Dispute submission is simulated, no real money is moved, and the local audit
table is not tamper-evident storage. The application is a prototype, not a
production payment or dispute-management system.

## 8. Mapping to the official judging criteria

The [official rules](https://paypalaihackathon.devpost.com/rules) state that the
five Stage Two criteria are equally weighted. This map points to evidence in
the repository and states the relevant limitation alongside it.

| Criterion | Evidence a reviewer can inspect | Boundary / remaining weakness |
| --- | --- | --- |
| **Technological implementation** | FastAPI + React/TypeScript application; 25-rule engine; synthetic-data logistic-regression estimate; human-approved action state machine; PayPal Orders v2 Sandbox client; 215-test baseline, 32 browser runs and 16/16 mutation checks in the last recorded local run, plus 2 new safety tests awaiting execution | The recorded build did not make a live PayPal Sandbox call or a live Gemini request; the default walkthrough is mock/template based; PayPal dispute submission is simulated |
| **Design** | Guided walkthrough, separate Orders / Action Inbox / Audit / Disputes experiences, explicit provenance labels, responsive Playwright coverage | The demonstrated checkout and external results use mock/simulated data; no production merchant usability study is claimed |
| **Potential impact** | Focuses on the operational gap between an order being shipped and the evidence being available when a dispute occurs; shows evidence present/missing and a response packet | No measured reduction in disputes, chargebacks, losses or merchant workload; no real-merchant outcome study is included |
| **Innovation / idea** | Connects pre-dispute evidence readiness with post-dispute packet preparation and human-approved actions, rather than presenting only a dispute-response text generator | This is a product-direction distinction, not a claim that no competing product offers similar features; the wider gallery includes adjacent dispute automation projects |
| **Presentation** | A 2:55 explainer MP4, transcript and shot manifest are committed in the repository; README provides a reproducible local run path | The recorded video uses mock/simulated app data and contains no live PayPal transaction; public playback of the referenced YouTube URL was not independently verified during this review |

This section is an evidence index, not a self-awarded score. Reviewers should
use the linked source, test records and limitations above rather than treating
the project narrative as proof of an unrun integration.

## 9. Primary references

- [README and quick start](README.md)
- [AI disclosure](AI_DISCLOSURE.md)
- [Project overview](DEVPOST_TEXT.md)
- [Architecture/design decisions](DECISIONS.md)
- [Bug history](BUGS_FIXED.md)
- [Master build specification](docs/MASTER.md)
