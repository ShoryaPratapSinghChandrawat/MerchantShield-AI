# AI disclosure

Rule R11: this file must not claim the project owner wrote, ran or verified
anything they did not. It is also the artefact the hackathon's "Tools" field
requires ("identify which tools (model or AI service) were used and explain how
the tools were used in your project").

Last updated: 2026-11-07, after the move to this repository and a full re-run.

---

## 1. AI used to *build* this project

| What | Detail |
| --- | --- |
| Tool | An AI coding agent running on Arena.ai's Agent Mode |
| Role | Wrote essentially all Phase 0 source code, tests, CI configuration and documentation in this folder |
| Human role so far | Shoryapratap Singh Chandrawat specified the requirements, the hard rules (R1-R11), the phase plan and the honesty constraints, and is the reviewer/verifier |
| Human verification so far | **None yet.** Phase 0 deliberately stops here so the project owner can run it on Windows 11 and report back. |

### Honest split for Phase 0

- **Written by the AI agent:** every file in this repository.
- **Run by the AI agent (real executions, real output):** `pip install`,
  `pytest` (86 tests), `npm install`, `tsc --noEmit`, `vite build`, `uvicorn`,
  a curl-based HTTP smoke test, `scripts/mutation_check.py --phase 0`,
  `scripts/package_release.py --phase 0`, and the Playwright harness up to the
  point where it launches a browser.
- **Run on 2026-11-07, in a substituted browser:** the Playwright suite, 6/6,
  in headless Chromium 153 from the `@sparticuz/chromium` npm package. The
  pinned Playwright Chromium 156 could not be downloaded here
  (`cdn.playwright.dev` resets the connection). See `DECISIONS.md` D-021.
- **NOT run by anyone yet:** the *pinned* Playwright browser build,
  `scripts/windows_check.ps1` (no PowerShell here - it has never been executed
  or even parsed), the GitHub Actions CI workflow, anything on Windows, and any
  PayPal API call.
- **Specified by the human:** the entire requirement set, including the rules
  that forced the add-tracking idempotency check and the three-label
  provenance model.

Nothing in this repository should be read as "the project owner tested this"
until the project owner says so. The phase reports track that distinction
explicitly.

---

## 2. AI used *inside* the product

This is what the hackathon's "Tools" field is really asking about.

### Phase 0: none

There is no LLM, no model and no AI inference in the running application yet.
`LLM_PROVIDER` defaults to `none`.

### Planned (Phase 3 and Phase 6), recorded now so the claims stay bounded

| Component | Phase | What it is | What it is **not** |
| --- | --- | --- | --- |
| `ml_risk_estimate` | 3 | A scikit-learn `LogisticRegression` on `StandardScaler`-normalised features, trained on **synthetic** data generated locally with a fixed seed | **Not** a win probability, **not** trained on real PayPal data, **not** a prediction of dispute outcome |
| Evidence-strength checklist | 3 | A deterministic, transparent 0-100 score computed from which evidence fields exist | Not ML at all; no model is involved |
| Dispute Defense Checklist | 6 | Deterministic rules over order data | The LLM may only *phrase* it, never add a fact |
| LLM wrapper (`services/llm.py`) | 6 | `gemini` and `none` only (MASTER 10.5 cuts the rest; the interface stays extensible), strict JSON output, deterministic template fallback of identical shape | Never a source of facts |
| Hallucination guard | 6 | Rejects any LLM output containing a tracking number, date, amount or identity not present in the app's own data, and logs `hallucination_guard_triggered` | - |
| Guarded planner | 6 | May only create `PENDING` proposals from a fixed allowlist | Can never claim, execute or approve an action |

### Standing constraints on AI in the product (rules R6-R8)

1. Scores are **estimates from synthetic data** and are labelled as such. The
   UI will never display "win probability", "money protected" or
   "X% fewer disputes".
2. LLM output may only use facts already present in the application's data.
   Invented tracking numbers, dates, amounts or identities are rejected and
   replaced, and the rejection is written to the audit log.
3. AI may only create **PENDING** proposals. A human approves. Any PayPal MCP
   or Agent Toolkit integration is **read-only**; every write (capture,
   tracking, refund, dispute submission) goes through the human-approval
   action engine. A write-capable AI tool is never exposed to the agent.
4. Uncertain external outcomes stay `UNKNOWN`. The app never claims an
   external action succeeded without confirmation.

---

## 3. Third-party services contacted so far

| Service | Contacted? | Notes |
| --- | --- | --- |
| PayPal (Sandbox) | **No** | No credentials supplied; no client code exists yet |
| PayPal (production) | **No, and structurally prevented** | `app/core/config.py` refuses to start against a non-sandbox PayPal host |
| Any LLM provider | **No** | `LLM_PROVIDER=none` |
| PyPI, npm registry | Yes | Dependency installation only |
| developer.paypal.com, devpost.com | Yes, read-only documentation fetches | Quoted in `docs/SOURCES.md` |
