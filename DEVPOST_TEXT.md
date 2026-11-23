# MerchantShield AI — project overview

This file is the repository's current technical overview. It is **not** a claim
that the closed Devpost submission has been edited. The submission period ended
on 12 November 2026; the project repository remains available for reviewers to
inspect.

Repository:
[ShoryaPratapSinghChandrawat/MerchantShield-AI](https://github.com/ShoryaPratapSinghChandrawat/MerchantShield-AI)

## The problem

PayPal dispute workflows depend on evidence: shipping details, buyer
communication, order facts and relevant policy records. For a small merchant,
those facts may be scattered across systems or never attached to the order.
MerchantShield explores a workflow for identifying missing evidence earlier and
organising the information needed when a dispute occurs.

This is a prototype, not a measured claim that disputes or losses are reduced.
No real-merchant outcome study is included.

## What the application does

1. **Order triage.** Applies 25 attributed rules across six groups and explains
   why an order is flagged. A separate logistic-regression output is shown as
   an `ESTIMATE`.
2. **Evidence readiness.** Lists evidence items present or missing and shows
   the gaps a merchant may need to address.
3. **Human-reviewed action proposals.** Suggests adding tracking, recording a
   buyer message in the app, or flagging an order for review. Proposals begin
   as `PENDING`; the planner cannot approve or execute them.
4. **Action protocol.** Enforces explicit approval and distinguishes known
   failure from an uncertain result (`UNKNOWN`). It uses a conditional
   database claim to prevent concurrent local executions.
5. **Dispute preparation.** Builds an evidence packet and supports response
   drafts. Template drafts work without credentials; optional Gemini drafts
   require a configured key and pass through the factual guard.
6. **Provenance and audit.** Records whether data is from PayPal Sandbox,
   local simulation or a mock adapter, and records application activity in a
   local SQLite audit table.

## Implementation

- **Backend:** Python 3.11, FastAPI, SQLAlchemy 2, SQLite and Pydantic v2.
- **Frontend:** React 19, TypeScript strict mode, Vite and Tailwind CSS 4.
- **ML:** scikit-learn logistic regression trained offline on synthetic data
  generated from the same rule system, with 8% label noise.
- **Browser testing:** Playwright.
- **Backend testing:** pytest.
- **Deployment model:** one FastAPI service serves the built single-page
  application and the API.

## PayPal status — read this before evaluating

The code includes a PayPal Orders v2 client targeting the PayPal Sandbox host.
It contains OAuth, order creation, capture, read-back and tracking operations.
The client is covered by mocked-HTTP tests.

**No live PayPal Sandbox call was made in the recorded build.** No credentials
were available in that environment. The default walkthrough therefore uses
the local mock adapter and labels records `MOCK`; locally generated records
are labelled `SIMULATED`.

The app does **not** submit a dispute or upload an evidence packet to PayPal.
Dispute submission is labelled `SIMULATED`. It does not send email, does not
call a carrier API and does not move real money.

For a credentialed Sandbox check, see
[`scripts/verify_paypal_live.py`](scripts/verify_paypal_live.py). It requests
a token, creates a $1.00 Sandbox order and reads the order back; it does not
capture it or file a dispute. Never commit credentials.

## AI status — read this before evaluating

- The rule engine is deterministic; it is not generative AI.
- The logistic-regression estimate is trained on synthetic data generated from
  the same rules. Its reported metrics describe that synthetic benchmark only;
  they do not establish real-world dispute prediction.
- The action planner is deterministic by default and cannot execute actions.
- Gemini drafting is an optional provider. A live Gemini request was not made
  in the recorded build, and the default demo uses deterministic templates.
- The factual guard checks selected fact patterns against the supplied evidence;
  it is not a general truth detector.

See [AI_DISCLOSURE.md](AI_DISCLOSURE.md) for the development and product AI
disclosure.

## Verification evidence

The following figures are the last recorded measurements in the README, dated
2026-11-11. They are historical evidence, not a claim that this documentation
update re-ran the suite.

| Check | Recorded result |
| --- | --- |
| Backend pytest suite | 215 passed |
| Playwright browser suite | 16 tests × 2 viewport sizes = 32 runs passed |
| Mutation check | 16/16 applicable mutations caught |
| TypeScript strict type-check | Passed |
| Vite production build | Passed |
| Clean-copy quick start | Recorded as verified on the Linux sandbox |
| GitHub Actions | Three jobs green on Phase 0 commit `048cdd4`; later phases were not verified in CI in that record |
| Live PayPal Sandbox | Not run |
| Live Gemini | Not run |
| Windows execution | Not verified on a Windows machine |

The detailed evidence and commands are in [README.md](README.md).

## Run the mock demo

Follow the Windows 11 / PowerShell instructions in the README. In summary:

```powershell
git clone https://github.com/ShoryaPratapSinghChandrawat/MerchantShield-AI.git
cd MerchantShield-AI
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
cd frontend
npm ci
npm run build
cd ..
$env:DEMO_MODE = "true"
$env:PAYPAL_MODE = "mock"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

Open <http://127.0.0.1:8000> and use **Run the story**. Node.js 24 is required
for the frontend; Python 3.11 is required for the backend.

## Video

The repository contains the 2:55 explainer at
`artifacts/video/merchantshield-ai-explainer.mp4`, plus its transcript and
build script. The referenced YouTube URL is
https://www.youtube.com/watch?v=sudB7b-sN44; public playback was not
independently verified during this repository review.
