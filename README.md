# MerchantShield AI

**Stops PayPal disputes before they happen, and helps small merchants answer
the ones that do.**

Sandbox-first, provenance-labelled, and deliberately unglamorous about what it
does not know. Every record on screen says where its data came from. Nothing
here moves real money.

Built for the **PayPal AI Hackathon** (deadline 12 November 2026, 12:00 PT).

### Quick start for judges (Windows 11, PowerShell)

The same commands as [Run it in 5 minutes](#run-it-in-5-minutes-windows-11-powershell)
below, with nothing added. Every line is a **separate** command — paste them one
at a time (or paste the block as a whole; PowerShell 5.1 runs each line on its own).
There is no `&&` and no `export`, because neither works in Windows PowerShell.

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

Open **<http://127.0.0.1:8000>** and press **Run the story** on the Overview page.
No PayPal credentials and no API key are needed: every record is labelled `MOCK`
or `SIMULATED`, and the UI says so on screen.

---

## The problem

A small merchant loses a PayPal dispute for one reason far more often than any
other: by the time the case opens, they can no longer *prove* what happened.
The parcel went out, but the tracking number was never attached to the PayPal
order. The buyer was messaged, but only in a channel nobody can export. The
delivery was signed for, but the receipt is in a drawer.

Disputes are resolved on evidence. Evidence decays. The merchant notices on day
41, when the order is old, the window is closing, and the answer is due in a few
days.

## What this app does

1. **Scores every order** with 25 hand-written rules (six groups: value,
   shipping evidence, buyer profile, listing/policy, category, buyer messages)
   over the merchant's own
   fields, and shows the reasons — each with a direction and a point value, not
   a black-box number. A separate logistic-regression prototype produces an
   **ESTIMATE** next to it, trained on synthetic data, with its metrics printed
   on the Methodology page.
2. **Proposes the next actions** an experienced operator would take: attach the
   tracking number, message the buyer, flag the order for review. The planner has
   no write access: proposals arrive `PENDING` and wait for a human.
3. **Executes only with approval**, exactly once, through a documented protocol
   that distinguishes "it failed" from "I do not know whether it happened".
4. **Builds an evidence packet** for a dispute: the seven documents that decide
   these cases, which ones you hold, which are missing, and what to do about
   each one.
5. **Drafts the response** — a deterministic template, or a Gemini draft behind a
   hallucination guard — and keeps every version, recording whether it was an AI
   draft, a template, or the merchant's own edit.
6. **Records everything** in an append-only audit log: who did what, when, and
   which source the data came from.

## The honesty rules, enforced by code

| Label | Meaning | Real PayPal? |
| --- | --- | --- |
| `PAYPAL_SANDBOX` | An actual response from the PayPal **Sandbox** REST API | Yes — Sandbox only, never production |
| `SIMULATED` | Generated locally by this app; nothing external was contacted | No |
| `MOCK` | A mock adapter stood in for PayPal | No |

`is_demo` and `demo_run_id` are tracked **separately** from `source`, so a real
Sandbox row created during a demo is still `is_demo=false`, and "Reset Demo"
must never delete it.

Five rules the code holds itself to, each with tests behind it:

- **No unlabelled record.** The API refuses to serialize a row whose source is
  not one of the three labels; the UI refuses to render one.
- **No silent retry of an ambiguous call.** A timeout or 5xx is `UNKNOWN`. It
  exits only through reconciliation, and `NOT_APPLIED` requires an explicit
  confirmation that a human checked PayPal.
- **No uncited fact in an AI draft.** Tracking numbers, dates and amounts in a
  draft must appear in the evidence packet handed to the model, or the draft is
  replaced by the template and marked `hallucination-guard`.
- **No claim without a measurement.** See "Limitations" below; a test scans the
  published copy for banned phrases and fails the build.
- **No production host.** `validate_paypal_base_url` rejects every non-Sandbox
  PayPal hostname at startup. There is no flag that re-enables production.

## Run it in 5 minutes (Windows 11, PowerShell)

Every line below is a **separate command**. `&&` does not work in Windows
PowerShell 5.1, and `export` is not a PowerShell command.

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

Open <http://127.0.0.1:8000>. You get 15 seeded orders, a storefront, an audit
log, and a guided walkthrough that plays the whole story end to end.

No PayPal credentials are needed: the mock adapter answers, every record says
`MOCK`, and the UI says so on the checkout screen rather than pretending a
PayPal page exists.

**Prefer a script?** `scripts\run_demo.ps1` does the same thing with pre-flight
checks. On Linux/macOS: `bash scripts/run_demo.sh`.

### Using the real PayPal Sandbox

Create an app at <https://developer.paypal.com/dashboard/applications/sandbox>,
then in the same PowerShell window:

```powershell
$env:PAYPAL_CLIENT_ID = "your-sandbox-client-id"
$env:PAYPAL_CLIENT_SECRET = "your-sandbox-client-secret"
$env:PAYPAL_MODE = "sandbox"
```

The storefront will then create a real Sandbox order and send you to PayPal's
own approval page; the capture records `source=PAYPAL_SANDBOX`. Only the host
`api-m.sandbox.paypal.com` is permitted.

### Optional: a Gemini key

```powershell
$env:LLM_PROVIDER = "gemini"
$env:LLM_API_KEY = "your-key"
```

Without it, drafts are deterministic templates labelled `Template draft`. With
it, drafts are labelled `AI-generated, please review` and pass through the
hallucination guard. `LLM_PROVIDER` accepts only `gemini` or `none`.

## Node.js 24 is required for the frontend

The frontend is pinned to Node **24 LTS** (`frontend/package.json` declares
`"engines": { "node": ">=24 <25" }`, and `.nvmrc` contains `24`).

1. Install Node 24 LTS from <https://nodejs.org> (or with `nvm-windows`:
   `nvm install 24` then `nvm use 24`).
2. Verify before building:

   ```powershell
   node --version
   ```

   It must print `v24.x`. On another major version `npm ci` and
   `npm run build` will warn or fail, and the pinned Playwright browser may not
   match the one CI installs.

The backend does not need Node at all; `backend/requirements.txt` and Python
3.11 are enough to run the API and its tests.

## Verification status

Three-way labelling, because "it works" is not a claim this project makes
loosely. This table describes **this checkout**, measured on 2026-11-11 in a
Linux sandbox — and re-measured in a clean copy of the repository with no
`.venv`, `node_modules`, `dist`, database or `artifacts/`, following only the
"Run it in 5 minutes" steps below.

| What | Status |
| --- | --- |
| Backend suite — **215 tests** (config guards, UTC timestamps, seeding, demo reset, orders, risk rules, evidence score, the full action protocol, PayPal client, LLM wrapper and hallucination guard, ML, disputes, storefront, API contract, honesty scan, mutation-tooling self-test) | **RAN HERE** — `215 passed` |
| Frontend `tsc --noEmit` | **RAN HERE** — clean, `strict` with `noUncheckedIndexedAccess` and `exactOptionalPropertyTypes` |
| Frontend `vite build` | **RAN HERE** — clean |
| Mutation check — **16 applicable mutations** across phases 0, 1, 2, 5 and 6 (a mutation that no test notices is a hard failure) | **RAN HERE** — 16/16 caught; reports in `artifacts/phase-*/MUTATION_REPORT.md` |
| Browser suite — **16 tests × 2 viewports** (1500×900 and 390×844) against the built SPA served by FastAPI, with any console error failing the test | **RAN HERE** — 32/32 passed, using a substitute Chromium 153 via `MS_CHROMIUM_PATH` because the pinned download host is blocked in this sandbox |
| GitHub Actions CI (backend tests, frontend build + Playwright with the pinned browser, mutation check) | **RAN IN CI on commit `048cdd4` (Phase 0)** — all three jobs green, and the Playwright job's pinned-Chromium install and artifact-upload steps succeeded (`DECISIONS.md` D-023). **NOT VERIFIED IN CI for the later phases**: the workflow file is unchanged and committed, so check the Actions tab after your next push |
| Windows 11 / PowerShell | **NOT VERIFIED ON WINDOWS** — every command is written for PowerShell 5.1 and `scripts\windows_check.ps1` exists to check it, but no Windows machine has executed this build |
| A live PayPal Sandbox call | **NOT RUN** — the client targets the documented Orders v2 Sandbox API and is covered by mocked-HTTP tests; `scripts/verify_paypal_live.py` is the first step that would change this row |
| A live Gemini call | **NOT RUN** — without a key the app uses its deterministic templates; the wrapper's fallback path is what the demo shows |
| The explainer video — `artifacts/video/merchantshield-ai-explainer.mp4`, 2:55, built from real screenshots of this build | **BUILT HERE** — frames captured from the running app in Chromium, narration synthesised, transcript in `artifacts/video/video-manifest.json`. `artifacts/` is gitignored, so the MP4 is uploaded to YouTube and linked from `DEVPOST_TEXT.md` |

## Architecture

`docs/MASTER.md` is the source of truth for the design; this is the map.

```
backend/
  app/main.py       FastAPI app, startup guards, SPA fallback, startup seeding
  app/core/         config (env parsing, validate_paypal_base_url: Sandbox hosts only)
  app/schemas/      Pydantic v2 request/response models
  app/api/          health, orders, actions, audit, demo, store, disputes, about, router
  app/services/     risk_rules, evidence_score, actions, paypal_client, paypal_mock,
                    paypal_service, llm, agent, risk_model, orders, disputes, store,
                    demo_story, audit
  app/models/       order, action, dispute, audit, enums, jsoncol (provenance on every row)
  app/db/           base, sqlite_url, seed (15 story orders + demo reset)
  ml/               generate_data.py (synthetic orders), train.py (sklearn, offline),
                    model/ (gitignored artefact, retrained on first boot if absent)
  tests/            215 tests across 21 files
frontend/
  src/pages/        Dashboard (labelled "Overview"), Orders, Store, Disputes, Audit,
                    Walkthrough, About (labelled "Methodology")
  src/api/          client.ts — typed client, no `any`, refuses unlabelled records
  src/components/   ui.tsx (primitives), SourceChip.tsx (the provenance chip)
  src/lib/          formatting helpers
  e2e/              16 Playwright tests in 8 spec files
  capture/          screenshot capture for the explainer video (not part of the suite)
scripts/            mutation_check.py, package_release.py, run_demo.ps1/.sh,
                    test_all.ps1/.sh, safe_commit.sh, verify_paypal_live.py,
                    windows_check.ps1, build_video.py
docs/               MASTER.md, GLOSSARY.md, SOURCES.md
(root)              README.md, DEMO_SCRIPT.md, DEVPOST_TEXT.md, AI_DISCLOSURE.md,
                    DECISIONS.md, BUGS_FIXED.md, HANDOFF.md, LICENSE, PHASE
```

One deployable service: FastAPI serves the built SPA from `frontend/dist` with
an SPA fallback, so the browser only ever talks to one origin and no wildcard
CORS policy is needed.

## The action protocol in one paragraph

`PENDING → APPROVED → EXECUTING → EXECUTED`, with `FAILED`, `UNKNOWN` and
`REJECTED` as the other exits. Execution claims the action with a single
conditional `UPDATE ... WHERE status = 'APPROVED'`, so eight concurrent clicks
produce exactly one claim and one external call — there is a test that fires
eight threads and asserts exactly that. A known failure becomes `FAILED` and may
be retried with the *same* idempotency key. A possibly-applied failure
(timeout, 5xx, connection reset, crash) becomes `UNKNOWN`, which can only be
resolved by reconciling against PayPal. Submission of a dispute response is
recorded as `SIMULATED`: no PayPal dispute API call is made, and the screen says
so.

## API

Everything is under `/api`: `health`; `orders` (list, detail, scan, agent,
propose-action); `actions` (list, detail, approve, reject, execute, retry,
reconcile); `audit`; `demo` (reset, seed, run-story — 404 unless `DEMO_MODE`);
`store` (products, checkout, capture, return); `disputes` (list, detail, packet,
drafts, approve, submit, open); `about` (methodology, metrics and disclosures).

Errors are JSON with a `detail` string. Unknown ids are 404, illegal transitions
are 409, and bad input is 422 — including an action type outside the allowlist,
which the engine rejects with a list of what is allowed.

## Limitations

What this build does **not** do, in its own words:

- It is not connected to PayPal production, and it never will be while
  `validate_paypal_base_url` is in place.
- It does not file a real dispute or upload evidence to PayPal. The Disputes API
  is out of scope for this build; submission is simulated and labelled.
- It does not call a carrier API. Tracking numbers are recorded, not verified.
- It does not send email. "Message the buyer" creates a logged message inside
  this app and says so on screen.
- The ML estimate is a prototype trained on synthetic data generated from the
  same rules, with 8% label noise. It is not trained on PayPal data. It is shown
  next to the rule score, with its metrics and both baselines, and it is labelled
  ESTIMATE everywhere. That is not a win probability and not a "chance to win":
  it is an estimate from your own order fields.
- No win probabilities, no "money protected", no "X% fewer disputes". Those
  claims require measurements this project has not made in a real merchant's
  account.
- It does not guarantee that a retried call is delivered once and only once.
  This project does not claim exactly-once semantics for any external call. The claim is
  narrower and it is tested: one claim per approved action, one external attempt,
  and an honest `UNKNOWN` when the outcome cannot be established. Idempotency
  keys are sent where PayPal documents them, which makes a retry *safe*, not
  *free*.
- The audit log is append-only by convention and by API shape, not
  tamper-evident: it is a table in the local SQLite database.
- Windows has not executed this build. See the verification table.

## Testing

```powershell
# backend
.\.venv\Scripts\python.exe -m pytest -q

# frontend types and bundle
cd frontend
npx tsc --noEmit
npx vite build

# browser suite (starts its own uvicorn on 127.0.0.1:8010)
npx playwright test

# everything, one command
cd ..
powershell -ExecutionPolicy Bypass -File scripts\test_all.ps1
```

On Linux/macOS: `bash scripts/test_all.sh`.

Mutation checking is per phase, and a surviving mutant is a hard failure.
Applicable mutations per phase — `0`: 3, `1`: 4, `2`: 12, `5`: 14, `6`: 16
(each includes the earlier phases), 16 distinct mutations in total:

```powershell
.\.venv\Scripts\python.exe scripts\mutation_check.py --phase 6
```

## Documentation

- [`docs/MASTER.md`](docs/MASTER.md) — the specification this build is measured
  against (single source of truth).
- [`docs/GLOSSARY.md`](docs/GLOSSARY.md) — plain-English definitions (dispute,
  chargeback, `UNKNOWN`, provenance labels) for a reader new to payments.
- [`docs/SOURCES.md`](docs/SOURCES.md) — the PayPal documentation each claim
  about the API is based on.
- [`DEMO_SCRIPT.md`](DEMO_SCRIPT.md) — the three-minute explainer video: shot
  list, full transcript, timings, and how to rebuild it with
  `scripts/build_video.py`.
- [`DEVPOST_TEXT.md`](DEVPOST_TEXT.md) — submission copy, including the
  "what is simulated" section.
- [`DECISIONS.md`](DECISIONS.md) — every non-obvious choice and the reason.
- [`BUGS_FIXED.md`](BUGS_FIXED.md) — the bugs found during the build, including
  the ones this project caused itself.
- [`HANDOFF.md`](HANDOFF.md) — how to pick this up, and what is still open.
- [`AI_DISCLOSURE.md`](AI_DISCLOSURE.md) — how AI was used to build and inside
  the product.

## The explainer video

`artifacts/video/merchantshield-ai-explainer.mp4` — **2:55**, 430 words of
narration, 22 shots, built from real screenshots of this build. Rebuild it with:

```powershell
cd frontend
npx playwright test --config playwright.capture.config.ts
cd ..
.\.venv\Scripts\python.exe scripts\build_video.py --frames artifacts\video\frames --audio artifacts\video\audio --out artifacts\video\merchantshield-ai-explainer.mp4
```

`artifacts/` is gitignored, so the MP4 lives on YouTube:
[PLACEHOLDER: YouTube URL]. `DEMO_SCRIPT.md` has the transcript, the per-shot
timings and what the video claims and does not claim.

## Licence

MIT — see [LICENSE](LICENSE). The copyright line currently reads
`[COPYRIGHT HOLDER - owner to confirm]`; the project owner must replace it with
their name before publishing.
