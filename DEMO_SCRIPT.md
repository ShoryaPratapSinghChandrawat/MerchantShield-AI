# MerchantShield AI — explainer video (3 minutes)

**The video exists in this repository:** `artifacts/video/merchantshield-ai-explainer.mp4`
— **2:55**, 1920×1080, H.264 + AAC, 430 words of narration across 22 shots and 10
scenes. It is built by `scripts/build_video.py` from real screenshots of this
build; the manifest next to it (`video-manifest.json`) carries the exact
transcript and per-shot timings that were rendered, so nothing below has to be
taken on trust.

**What it is, honestly.** Every app image is a screenshot of this build running
locally (`DEMO_MODE=true`, `PAYPAL_MODE=mock`), captured by
`frontend/capture/capture.spec.ts` in Chromium — not a mock-up, not a redrawn
UI. The narration is synthesised speech reading the transcript in
`video-manifest.json`. The title card and the closing card are drawn text, not
app footage. **There is no footage of a real PayPal Sandbox transaction**, and
nothing in the video says there is: on screen, every record is labelled `MOCK` or
`SIMULATED`.

**To rebuild it** (from the repository root, after the capture run):

```bash
# 1. real screenshots from the running app  (needs Node 24 + a Chromium)
cd frontend
npx playwright test --config playwright.capture.config.ts
cd ..

# 2. narration audio: 10 clips, text in scripts/build_video.py
#    (synthesised with a text-to-speech model; see AI_DISCLOSURE.md)

# 3. assemble
.venv/bin/python scripts/build_video.py \
    --frames artifacts/video/frames \
    --audio  artifacts/video/audio \
    --out    artifacts/video/merchantshield-ai-explainer.mp4
```

The MP4 and `video-manifest.json` are **committed** (`.gitignore` excludes the
rest of `artifacts/` but not these two files), so a judge can watch it from the
repository without downloading anything from a third party. Uploading it to
YouTube is a separate, still-open step: replace `[PLACEHOLDER: YouTube URL]` in
`DEVPOST_TEXT.md` once that URL exists.

---

## Pre-recording checklist (if you re-record on Windows)

1. Start the server from the repository root, one command per line:
   ```powershell
   .\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
   cd frontend
   npm ci
   npm run build
   cd ..
   $env:DEMO_MODE = "true"
   $env:PAYPAL_MODE = "mock"
   .\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
   ```
2. Check the header chips read `demo on · paypal mock · llm none · phase 7`. If
   they do not, stop: the video would mislabel what it shows.
3. Open <http://127.0.0.1:8000/#/walkthrough> and press **Reset demo** to start
   from a known state, then **Run it live** once as a dry run, then reset again.
4. Browser window 1500×900 at 100% zoom, one tab, bookmarks bar hidden.
5. Close notifications (Windows Focus assist, Slack, Teams, mail); auto-hide the
   taskbar; do not show client IDs or secret values on screen.
6. Record with `scripts\windows_check.ps1` already run, so you can say the
   machine's test results out loud if asked.
7. Watch the result back against this file before uploading.

---

## Shot list (as rendered — timings from `video-manifest.json`)

| # | Time | On screen |
| --- | --- | --- |
| 1 | 0:00 | A dispute is decided on evidence. Evidence decays. (`__title__`) |
| 2 | 0:09 | MS-2001 · 41 days old · no tracking on file (`03-order-facts.png`) |
| 3 | 0:18 | Overview · demo on · paypal mock · llm none (`01-overview.png`) |
| 4 | 0:28 | Proposals arrive PENDING · the agent cannot approve (`07-planner-proposals.png`) |
| 5 | 0:37 | Orders, sorted by rule score (`02-orders.png`) |
| 6 | 0:45 | Every point attributed, with a direction (`04-risk-reasons.png`) |
| 7 | 0:54 | ESTIMATE · trained on synthetic data (`05-model-estimate.png`) |
| 8 | 1:00 | Seven documents · present or missing (`06-evidence-checklist.png`) |
| 9 | 1:06 | Metrics and both baselines, on the Methodology page (`14-methodology.png`) |
| 10 | 1:12 | PENDING → APPROVED (`07-planner-proposals.png`) |
| 11 | 1:22 | Approve, then execute (`08-proposal-approved.png`) |
| 12 | 1:32 | EXECUTED · handled locally · SIMULATED (`09-proposal-executed.png`) |
| 13 | 1:40 | One claim · one attempt · one audit row (`13-audit.png`) |
| 14 | 1:48 | Evidence packet, score and timeline (`12-dispute-packet.png`) |
| 15 | 1:57 | Submission is SIMULATED and labelled (`12-dispute-packet.png`) |
| 16 | 2:06 | Append-only audit log · actor and source on every row (`13-audit.png`) |
| 17 | 2:12 | Source labels and the rules the code holds itself to (`15-methodology-more.png`) |
| 18 | 2:19 | What is not built (`16-methodology-limits.png`) |
| 19 | 2:25 | The whole story, nine stages, each labelled (`11-walkthrough-story.png`) |
| 20 | 2:32 | When the app does not know, it says so (`16-methodology-limits.png`) |
| 21 | 2:39 | 215 backend tests · 32 browser tests · 16 mutation checks (`02-orders.png`) |
| 22 | 2:47 | PayPal Sandbox only. Nothing here moves real money. (`__outro__`) |

The narration is continuous per scene, not per shot; the transcript below is the
spoken text, in order, with the on-screen context for each scene.

---

## Transcript (430 words, spoken)


**1. The problem** — `s01.mp3`

> A PayPal dispute is decided on evidence: a tracking number, a delivery confirmation, a message thread. By day forty-one, the tracking number was never attached to the PayPal order, and the buyer is already saying chargeback. Merchants lose these cases on paperwork they no longer have.

**2. What it is** — `s02.mp3`

> MerchantShield AI scores every order, proposes the action that saves the evidence, and executes only after a human approves. Every record carries one of three labels: a real Sandbox response, generated locally, or a mock standing in for PayPal. There is no fourth label.

**3. Scoring an order** — `s03.mp3`

> Twenty-five hand-written rules score each order from zero to one, and every point is attributed with a direction. No tracking costs twenty points. You can argue with a rule; you cannot argue with a number that appears from nowhere.

**4. Estimate and evidence** — `s04.mp3`

> Beside it, a logistic-regression prototype, clearly labelled estimate, trained on synthetic data, with its metrics and two baselines on the Methodology page. Underneath, the seven documents this kind of case needs, which ones you hold, and what to do about each gap.

**5. Acting on it, safely** — `s05.mp3`

> Ask the planner, and it proposes actions: attach this tracking number, message the buyer, flag the order. Everything arrives pending. The agent has no write access. Approve, then execute. The claim is a single conditional update, so two clicks cannot create two tracking numbers.

**6. Once, and honestly unknown** — `s06.mp3`

> A test fires eight concurrent executes and asserts exactly one claim, one external call and one audit row. And a timeout is not a failure. It is an unknown, and the app refuses a blind retry, because that is how duplicates happen.

**7. The dispute** — `s07.mp3`

> When the case does open, the packet is already assembled. The draft is a deterministic template without a key; with a Gemini key it is a model draft that must pass a hallucination guard. Every save is a new version. Submission is labelled simulated: no case is filed with PayPal.

**8. Why you can trust it** — `s08.mp3`

> Every state change is in an append-only audit log, with an actor and a source. The Methodology page prints the model's real numbers next to two baselines, and states what is not built: no production PayPal, no dispute filing, no carrier API, no training on PayPal data.

**9. What it changes** — `s09.mp3`

> For a small merchant, that is the difference between arguing a case and losing it by default. Evidence collected on day one is worth more than any percentage a dashboard could invent. And when the app does not know something, it says so.

**10. Where it stands** — `s10.mp3`

> Two hundred and fifteen backend tests, thirty-two browser tests and sixteen mutation checks run from one command. If a guarantee is removed, a test fails. PayPal Sandbox only. Nothing here moves real money.

---

## Word count and timing

| Scene | Words | Audio length |
| --- | --- | --- |
| 1. The problem | 46 | — |
| 2. What it is | 44 | — |
| 3. Scoring an order | 39 | — |
| 4. Estimate and evidence | 42 | — |
| 5. Acting on it, safely | 44 | — |
| 6. Once, and honestly unknown | 42 | — |
| 7. The dispute | 50 | — |
| 8. Why you can trust it | 47 | — |
| 9. What it changes | 43 | — |
| 10. Where it stands | 33 | — |
| **Total** | **430** | **2:55 (175.1 s)** |

430 words over 175 seconds works out at **147 words per minute**, which is a
normal narration pace. The Devpost limit is 3:00; this is 2:55, with five
seconds of headroom before the narration would need trimming.

---

## What the video claims, and what it does not

- It says: 25 hand-written rules, three provenance labels, one claim per
  approved action, `UNKNOWN` is not retried blindly, submission is `SIMULATED`.
  Each of those is a test in this repository, and the counts (215 backend tests,
  32 browser tests, 16 mutation checks) are the counts of this checkout.
- It does not say: any win rate, any dollar figure kept safe, any reduction in
  dispute volume, any production PayPal use, or that a live Sandbox call
  happened. It has no footage of one either.

## If you only have sixty seconds

Scene 1 (the problem), scene 2 (the three labels), then scenes 3–5 (one order
scored, one action approved and executed). That is the thesis: evidence,
approval, provenance.
