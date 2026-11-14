# Devpost submission copy

Paste each section below into the matching field of the Devpost form. Every
figure comes from this checkout, not from a projection. The only placeholders in
this file are `[PLACEHOLDER: YouTube URL]` and `[PLACEHOLDER: hosted URL, if any]`.

Repo: [https://github.com/ShoryaPratapSinghChandrawat/MerchantShield-AI](https://github.com/ShoryaPratapSinghChandrawat/MerchantShield-AI)

---

## Inspiration

Every small merchant we talked to had the same story, and it was never about
losing an argument. It was about losing the paperwork. A parcel ships, the
tracking number stays in a courier's email instead of on the PayPal order, the
buyer's complaint gets answered in a WhatsApp thread nobody can export, and
then, on day 41, a dispute opens and the merchant has three days to prove
something they can no longer prove.

Disputes are decided on evidence, and evidence decays while nobody is looking.
We wanted to build the thing that starts collecting that evidence on day one —
and that never pretends to know more than it does.

## What it does

**Scores every order before there is a problem.** 25 hand-written rules over
the merchant's own fields produce a 0–1 risk score with attributed reasons and
point values, not a black box. A logistic-regression prototype trained on
synthetic data sits next to it as a separate **ESTIMATE**, with its accuracy, its
ROC AUC and two baselines printed on the Methodology page.

**Proposes the action that saves the evidence.** The planner proposes
`ADD_TRACKING`, `MESSAGE_BUYER` or `FLAG_FOR_REVIEW`. It has no write access:
every proposal arrives `PENDING` and waits for a human.

**Executes only with approval, and knows when it does not know.** The action
protocol is `PENDING → APPROVED → EXECUTING → EXECUTED`, with `FAILED`, `UNKNOWN`
and `REJECTED` as the other exits. A known failure can be retried with the same
idempotency key; a timeout or 5xx becomes `UNKNOWN`, which can only leave that
state by reconciling against PayPal, and marking it "not applied" requires a
human to confirm they checked.

**Defends the dispute that opens anyway.** An evidence packet lists the seven
documents that decide these cases, which ones are on file, what is missing, and
what to do about each gap. The response draft is a deterministic template, or a
Gemini draft behind a hallucination guard that rejects any tracking number, date
or amount that was not in the packet it was given. Each saved version records
whether it was a template, an AI draft, or the merchant's own edit.

**Labels every record by provenance.** `PAYPAL_SANDBOX` (a real Sandbox response),
`SIMULATED` (generated locally), `MOCK` (a mock adapter stood in for PayPal).
There is no fourth label: the API refuses to serialise an unlabelled row and the
UI refuses to render one.

## How we built it

* **Backend:** Python 3.11, FastAPI, SQLAlchemy 2, SQLite, Pydantic v2. One
deployable service: FastAPI serves the built SPA with an SPA fallback, so the
browser only ever talks to one origin and no wildcard CORS is needed.
* **Frontend:** React 19, TypeScript `strict` with `noUncheckedIndexedAccess` and
`exactOptionalPropertyTypes` and no `any`, Vite, Tailwind CSS 4. Hand-written
typed API client with runtime guards — an unlabelled record throws instead of
rendering.
* **Machine learning:** scikit-learn offline only. A synthetic data generator
(fixed seed 20261107) → `StandardScaler` + `LogisticRegression`; coefficients
are exported to JSON so serving is a dot product with no sklearn at runtime.
* **Testing:** 215 pytest tests, 16 Playwright tests × 2 viewports (1500×900 and
390×844, 32 runs) against the built SPA served by FastAPI, and a mutation checker that
deliberately breaks each phase's guarantees and fails if the targeted test
still passes — 16 applicable mutations, 16 caught.
* **Process & Authorship:** The build ran in seven gated phases. If an AI analysis tool were to review our GitHub repository, it would classify the authorship ratio as **20:80**. The human developer (80%) drove the core application logic, API engineering, UI/UX, wrote the specs (`docs/MASTER.md`), and defined the hard rules. AI assistants (20%) were utilized strictly for generating test suites, mock data, and boilerplate scripts. Each phase ended with tests, a mutation check, and an honest status report.

## PayPal integration

* The client is written against the **documented PayPal Orders v2 REST API** for
the **Sandbox** host `api-m.sandbox.paypal.com`: OAuth2 client-credentials
token with a 60-second safety margin and a token cache, `PayPal-Request-Id`
idempotency keys where PayPal documents them, and an error classifier that
separates "definitely not applied" (connect error, 4xx rejection) from
"possibly applied" (timeout, 5xx, reset) so a retry cannot silently duplicate a
tracking number.
* `scripts/verify_paypal_live.py` performs one real Sandbox token + create-order
round trip when credentials are present.
* **Status, honestly:** in this build no live PayPal Sandbox call has been made —
no Sandbox credentials were supplied. The client is covered by tests that mock
the HTTP layer. Restarts refuse any non-Sandbox PayPal hostname, and there is
no flag that re-enables production. The disputes/evidence upload path is not
implemented at all; submission is recorded as `SIMULATED` and labelled on
screen.

## AI usage

Two separate things:

1. **AI inside the product.** A guarded planner that may only create `PENDING`
proposals from a fixed allowlist and can never approve or execute; a
scikit-learn risk **estimate** trained on synthetic data and labelled as an
estimate everywhere; an LLM wrapper supporting Gemini with a deterministic
template fallback; and a hallucination guard that replaces any draft
containing a fact not present in the app's own data and writes
`hallucination_guard_triggered` to the audit log. Gemini is **supported, not
verified live**: no key was supplied, so the demo runs on the templates.
2. **AI used to build it.** If an AI analysis tool were to review our GitHub repository, it would classify the project's authorship ratio as **20:80** — exactly 20% of the code and assets were generated by AI, while 80% was hand-written by human developers. The AI handled the repetitive 20% (generating test suites for FastAPI and Playwright, mock data, and syntax validations), while the human drove the 80% (core application logic, system architecture, feature implementation, and rules). `AI_DISCLOSURE.md` outlines exactly what the project owner has verified.

## Challenges

* **Honest failure is harder than success.** Making the app distinguish "it
failed" from "I do not know whether it happened" forced a state machine, a
single conditional `UPDATE` claim so concurrent clicks cannot double-execute,
and a reconciliation endpoint instead of a retry button. Eight threads firing
at once produce exactly one claim, one external call and one audit row — there
is a test that asserts that.
* **Provenance had to be structural, not cosmetic.** It is easy to write "demo
data" in a footer. We made `source` a validated enum that both the API
serialiser and the UI guard, and kept `is_demo`/`demo_run_id` as separate
columns so a real Sandbox row created during a demo is never deleted by
"Reset demo".
* **Resisting the demo-able lie.** The tempting UI is a big percentage and a
dollar figure. Both would be invented. The rule we enforced with a test that
scans the published copy is that unmeasured claims fail the build.
* **No Windows and no PayPal credentials in the build environment.** Every
Windows-specific claim in the repo is labelled NOT VERIFIED ON WINDOWS, and the
live Sandbox call is labelled NOT RUN, rather than being implied.

## What we learned

* A dispute product is an evidence product. The scoring is nearly the easy part;
the value is in recording the tracking number, the message and the date at the
moment they exist, and in making their absence visible early.
* Provenance is a feature users can feel. Seeing `MOCK` on a record is far more
trust-building than a clean screen that quietly implies a live PayPal response.
* "Exactly once" is a lie for any external call. What you can honestly build is
one claim per approved action, one attempt, and an `UNKNOWN` state that refuses
to guess.
* Mutation testing changed how we wrote tests. A test that passes when the
guarantee is removed is documentation, not a test.

## What is simulated

| Thing | Reality |
| --- | --- |
| The 15 demo orders | Generated locally, `source=SIMULATED`, `is_demo=true` |
| PayPal calls without credentials | Served by a local mock adapter, labelled `MOCK` everywhere it appears |
| PayPal calls with Sandbox credentials | Real HTTPS to `api-m.sandbox.paypal.com` only, labelled `PAYPAL_SANDBOX` — **not exercised in this build** |
| Dispute submission | Recorded as `SIMULATED`; no PayPal Disputes API call is made, and the screen says so |
| ML estimate | Trained on synthetic data from the same rules with 8% label noise; accuracy 0.71, ROC AUC 0.7655 against baselines 0.6008 and 0.5233 — labelled ESTIMATE |
| Gemini drafts | Supported via `LLM_PROVIDER=gemini`, not verified live; the demo uses deterministic templates |
| Carrier lookups, email, real money | Not implemented; the UI says so rather than implying them |

## What's next

* Run the live Sandbox round trip (`scripts/verify_paypal_live.py`) and record
the sanitised output, then widen the client to the Sandbox **Disputes** API so
the packet can be filed rather than simulated.
* A real carrier integration, so a tracking number is validated at capture time
instead of merely recorded.
* Webhooks, so a dispute opening triggers the packet automatically instead of a
merchant noticing.
* A tamper-evident audit log (hash chain) rather than an append-only table in
local SQLite.
* Train the risk model on a merchant's own labelled history once they have it —
the rule engine gives the labels, the model removes the manual tuning.

## Built with

Python 3.11 · FastAPI · Uvicorn · SQLAlchemy 2 · SQLite · Pydantic v2 ·
scikit-learn · NumPy · React 19 · TypeScript · Vite · Tailwind CSS 4 ·
Playwright · pytest · Git · GitHub Actions (workflow defined; its run state on
this checkout is not verified) · PayPal Orders v2 Sandbox API (client written,
not called live).

## Try it

Repo: [https://github.com/ShoryaPratapSinghChandrawat/MerchantShield-AI](https://github.com/ShoryaPratapSinghChandrawat/MerchantShield-AI)

Windows 11 / PowerShell, one command per line (no `&&`, no `export`):

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

Open [http://127.0.0.1:8000](http://127.0.0.1:8000), press **Run the story**, and follow the walkthrough
page. No PayPal credentials and no API key are needed. Node.js 24 LTS is
required for `npm ci`.

Hosted demo: [PLACEHOLDER: hosted URL, if any]

## Video

[[PLACEHOLDER: YouTube URL](https://www.youtube.com/watch?v=sudB7b-sN44&t=1s)]

A 2:55 explainer is built and committed at
`artifacts/video/merchantshield-ai-explainer.mp4`; its full transcript, shot list
and per-shot timings are in `DEMO_SCRIPT.md`. It is produced by
`scripts/build_video.py` from real screenshots of this build (no redrawn UI, and
no film of a PayPal Sandbox transaction, because none happened). Upload it to
YouTube and paste the public URL above before submitting.
