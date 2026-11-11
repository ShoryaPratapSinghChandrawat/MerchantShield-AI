# AI disclosure

Two separate questions, answered separately: **how AI was used to build this
project**, and **how AI is used inside the product**. Nothing here claims the
project owner wrote, ran or verified something they did not.

Last updated: 2026-11-11.

---

## 1. AI used to *build* this project

| What | Detail |
| --- | --- |
| Tools | An AI coding agent running on (code, tests, docs, screenshots and the video build); a text-to-speech voice model for the video narration (the session used several underlying models; the agent the code in a single Linux sandbox) |
| Human role | Shoryapratap Singh Chandrawat specified the product, the hard rules (R1–R11), the seven-phase plan, the honesty constraints and the acceptance tests for each phase, and reviewed every phase report |
|the human has done | Windows run, no live PayPal Sandbox call, live Gemini call, no CI run on this branch, and the demo video has been recorded. Each of those is labelled NOT RUN or NOT VERIFIED in `README.md` |

### What was actually executed by the agent, and where

- **Run in the Linux sandbox (RAN HERE):** `pip install -r backend/requirements.txt`,
  `pytest` (215 tests), `tsc --noEmit`, `vite build`, `npm ci` under Node 24,
  `uvicorn` + HTTP checks against the running app, `scripts/mutation_check.py`
  for phases 0/1/2/5/6 (16 applicable mutations, 16 caught), and the Playwright
  suite (16 tests × 2 viewports = 32 passed) against the built SPA served by
  FastAPI.
- **Run with a substitute browser:** the Playwright suite ran in headless
  Chromium 153 from `@sparticuz/chromium`, because the pinned Playwright browser
  download host is blocked in this sandbox. See `DECISIONS.md` D-021. The
  pinned browser is what CI installs.
- **Written but never executed by anyone:** `scripts/windows_check.ps1`,
  `scripts/run_demo.ps1`, `scripts/test_all.ps1`, `scripts/safe_commit.sh` were
  syntax-checked only (PowerShell is not available here; the `.sh` files were
  parsed with `bash -n`). `scripts/verify_paypal_live.py` compiles and imports
  cleanly but has never made a network call.
- **Built here (RAN HERE):** the 2:55 explainer video
  (`artifacts/video/merchantshield-ai-explainer.mp4`). Its app frames are real
  screenshots captured from this build in Chromium by
  `frontend/capture/capture.spec.ts`; its narration is a text-to-speech model
  reading the transcript in `scripts/build_video.py`; the title and closing
  cards are drawn text. No frame was redrawn, and no PayPal Sandbox transaction
  is shown, because none happened.
- **Never run:** anything on Windows 11, GitHub Actions on this branch, a live
  PayPal Sandbox request, and a live Gemini request.

### Honest split

- **Written by the AI agent:** 
some source file, test, workflow, script and
  document in this repository.
- **Specified and reviewed by the human:** the requirements, the rules, the
  phase gates, the decision to label everything by provenance, and the decision
  to publish unflattering results rather than smooth them over.
- **Verified by the human personally:** nothing yet. The project owner is the
  only person who can do that, which is why `HANDOFF.md` and the Task 7
  checklist exist.

If a judge asks "did a human test this on their machine", the answer today is
no, and the repository says so in the verification table rather than in a
footnote.

---

## 2. AI used *inside* the product

| Component | What it is | What it is **not** |
| --- | --- | --- |
| `ml_risk_estimate` (`backend/ml/train.py` → `backend/app/services/risk_model.py`) | A scikit-learn `LogisticRegression` on standardised features, trained **offline** on synthetic data (fixed seed 20261107, 8% label noise); coefficients exported to JSON so serving is a dot product with no sklearn at runtime | **Not** a win probability, **not** trained on PayPal data, **not** a prediction of any dispute outcome. Accuracy 0.71, ROC AUC 0.7655 against baselines 0.6008 and 0.5233 — synthetic, labelled ESTIMATE in the UI |
| Rule engine (`services/risk_rules.py`) | 25 hand-written, attributed rules in six groups producing a 0–1 score with per-rule reasons and point values | Not ML. Deterministic and arguable, which is the point |
| Evidence-strength score (`services/evidence_score.py`) | Weighted checklist over evidence that exists (tracking 25, delivery 20, shipped date 15, carrier 10, buyer comms 10, item description 10, policy 10) | Not a prediction of anything; a transparent inventory |
| Guarded planner (`services/agent.py`) | Proposes `ADD_TRACKING`, `MESSAGE_BUYER`, `FLAG_FOR_REVIEW` as `PENDING` actions from a fixed allowlist | Can never approve, claim, execute or write to PayPal. It has no code path that mutates an action's status |
| LLM wrapper (`services/llm.py`) | `gemini` and `none` only; strict JSON output; deterministic template fallback of the same shape | Never a source of facts. With no key, every draft is a template and is labelled `Template draft` |
| Hallucination guard | Rejects any draft containing a tracking number, date, amount or identity not present in the evidence packet handed over, replaces it with the template, and logs `hallucination_guard_triggered` | Not a general fact-checker; it only compares against the packet |
| Dispute draft versions | Each save records whether it was a template, an AI draft, or the merchant's own edit | The merchant always sends their own words; the UI says so |

### Live-status of the AI features

- **Gemini:** supported, **not verified live**. No key was supplied in this
  sandbox, so the wrapper's `none` path (deterministic templates) is what the
  demo and the browser suite exercise. `LLM_API_KEY` is read from the
  environment only; nothing is hard-coded.
- **The ML model:** trained and evaluated here from synthetic data. The metrics
  on the Methodology page come from the stored `metrics.json`; they describe the
  synthetic dataset, not any real merchant.

---

## 3. Third-party services contacted

| Service | Contacted? | Notes |
| --- | --- | --- |
| PayPal Sandbox REST API | **No** | No Sandbox credentials were supplied. The client is covered by tests that mock the HTTP layer; `scripts/verify_paypal_live.py` is the step that would change this row |
| PayPal production | **No, and structurally prevented** | `validate_paypal_base_url` rejects every non-Sandbox hostname at startup; there is no flag that re-enables production |
| Any LLM provider | **No** | `LLM_PROVIDER=none` throughout this build |
| PyPI, npm registry | Yes | Dependency installation only |
| developer.paypal.com, devpost.com | Yes, read-only documentation and rules pages | Quoted in `docs/SOURCES.md` |

---

## 4. Standing constraints on AI in the product (rules R6–R8)

1. Scores are **estimates from synthetic data** and are labelled as such. The UI
   never displays "win probability", "money protected" or "X% fewer disputes";
   a test scans the published copy for those phrases and fails if they appear as
   claims.
2. LLM output may only use facts already present in the application's data.
   Invented tracking numbers, dates, amounts or identities are rejected and
   replaced, and the rejection is written to the audit log.
3. AI may only create **PENDING** proposals. A human approves. There is no
   write-capable AI tool, and no PayPal MCP/Agent Toolkit write is exposed.
4. Uncertain external outcomes stay `UNKNOWN`. The app never claims an external
   action succeeded without confirmation, and it never claims exactly-once
   delivery — only one claim per approved action, one attempt, and an honest
   `UNKNOWN`.
