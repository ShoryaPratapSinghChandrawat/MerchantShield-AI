# Sources

Requirement -> source -> implementation -> test.

Every row is marked:

| Mark | Meaning |
| --- | --- |
| `OFFICIAL` | Taken from an official page I actually fetched and read. The URL is quoted. |
| `MY CHOICE` | A design decision with no external authority. Mine to defend. |
| `OPEN QUESTION` | Not yet verified. Must not be relied on until it is. |

Last updated: 2026-11-01 (Phase 0).

---

## 0. What I could actually access

Rule R1/R2 require me to be explicit about this.

| Resource | Reachable? | Evidence |
| --- | --- | --- |
| `https://paypalaihackathon.devpost.com/rules` | **Yes** - fetched and read in full | Quoted below |
| `https://developer.paypal.com/api/orders/v2` | **Yes** - fetched and read | Quoted below |
| `https://developer.paypal.com/api/orders/v2/orders-create` | **Yes** - fetched and read | Quoted below |
| `https://developer.paypal.com/api/orders/v2/orders-capture` | **Yes** - fetched and read | Quoted below |
| `https://developer.paypal.com/api/orders/v2/orders-track-create` | **Yes** - fetched and read | Quoted below |
| PayPal Disputes API docs | **Not yet read** | Phase 5/6 work. `OPEN QUESTION`. |
| PayPal Agent Toolkit / MCP docs | **Not yet read** | Phase 6 work. `OPEN QUESTION`. |
| A real PayPal Sandbox account / credentials | **No** - none supplied | Zero live API calls have been made. |
| `cdn.playwright.dev` (Playwright browser download) | **No** - network blocked in the build sandbox | See `BUGS_FIXED.md` / "what I did NOT run" |

---

## 1. Hackathon rules

Source: **https://paypalaihackathon.devpost.com/rules** (Official Rules tab), fetched 2026-11-01.

| Requirement | Verbatim from the rules | Mark | Implementation | Test |
| --- | --- | --- | --- | --- |
| Deadline | "Submission Period: Thursday Oct 1, 2026 (9:15 am Pacific Time) - Thursday **Nov 12, 2026 (12:00 pm Pacific Time)**" | `OFFICIAL` | Project plan | n/a |
| Judging period | "Tuesday Dec 1, 2026 (2:00 pm Pacific Time) - Tuesday Dec 15, 2026 (8:00 am Pacific Time)" | `OFFICIAL` | n/a | n/a |
| Winners | "On or around Monday, Dec 21, 2026" | `OFFICIAL` | n/a | n/a |
| Eligibility (age) | "Individuals who are **at least the age of majority where they reside** as of the time of entry" | `OFFICIAL` | **You must confirm this yourself.** See README. | n/a |
| Eligibility (geography) | Excludes residents of countries where US or local law prohibits participation, naming "Brazil, Quebec, Russia, Crimea, Cuba, Iran, and North Korea and any other country which is comprehensively sanctioned by ... OFAC". India is not named in that exclusion list. | `OFFICIAL` | n/a | n/a |
| Team size | "Teams of Eligible Individuals" - no upper bound stated; a Team must appoint one Representative | `OFFICIAL` | n/a | n/a |
| What to build | "an application that integrates the PayPal developer platform (**using the free sandbox environment**) along with an AI tool, model, or platform of their choice" | `OFFICIAL` | Whole project; Sandbox-only enforced in `app/core/config.py` | `backend/tests/test_config_guard.py` |
| Functional demo | "judges must be able to actually run or interact with a working build ... clear, complete setup and run instructions in your code repository ... OR a hosted demo URL. A design mockup, static prototype, or non-functional demo does not meet this requirement." | `OFFICIAL` | `README.md` run instructions | CI proves the instructions work |
| Public repo + licence | "must be public and open source by including an open source license file. This license should be detectable and visible at the top of the repository page (in the About section)." | `OFFICIAL` | `LICENSE` (MIT) | Manual check on GitHub |
| Video | "should be less than three (3) minutes ... must be uploaded to and made publicly visible on **YouTube**" | `OFFICIAL` | Phase 7 `DEMO_SCRIPT.md` | n/a |
| Text description | "Include a text description that should explain the features and functionality of your Project." | `OFFICIAL` | Phase 7 `DEVPOST_TEXT.md` | n/a |
| AI tools disclosure | "**Tools** - identify which tools (model or AI service) were used and explain how the tools were used in your project." | `OFFICIAL` | `AI_DISCLOSURE.md` | n/a |
| Language | "All Submission materials must be in English" | `OFFICIAL` | All docs are English | n/a |

### Judging criteria (Stage Two, "equally weighted")

Quoted from the Rules tab, section 6:

1. **Technological Implementation** - "How thoroughly and skillfully does the project use PayPal Developer Platform and AI tool(s)? Does the project reflect genuine effort..."
2. Design
3. Potential Impact
4. Innovation / Quality of the Idea
5. Presentation

> Criteria 2-5: the rules page text I retrieved was truncated after criterion 1. The five criteria named in the master prompt match the standard Devpost set, but **I have only verified the wording of criterion 1 verbatim.** Marked `OPEN QUESTION` until the remaining four are re-read directly.

### Deadline conversion (arithmetic, not a source)

- Nov 12, 2026, 12:00 PM Pacific. US daylight saving ends Nov 1, 2026, so Pacific is PST = UTC-8.
- 12:00 PST = **20:00 UTC** = **01:30 IST on Nov 13, 2026** (IST = UTC+5:30).
- This **matches** the deadline stated in the master prompt. The Devpost header also shows "Nov 12, 2026 @ 3:00pm EST", which is the same instant.

---

## 2. PayPal API facts

Source: **https://developer.paypal.com/api/orders/v2** and its per-endpoint pages, fetched 2026-11-01.

| Fact | Source | Mark | Implementation | Test |
| --- | --- | --- | --- | --- |
| Sandbox base URL is `https://api-m.sandbox.paypal.com` | Orders v2 reference, "Base URL(s)" | `OFFICIAL` | `DEFAULT_PAYPAL_SANDBOX_BASE_URL` in `app/core/config.py` | `test_default_base_url_is_the_documented_sandbox_host` |
| OAuth token URL is `https://api-m.sandbox.paypal.com/v1/oauth2/token`, flow = Client Credentials | Orders v2 "Authorization" block on every endpoint page | `OFFICIAL` | Phase 5 | Phase 5 |
| Scope for payments: `https://uri.paypal.com/services/payments/payment` | Orders v2 endpoint pages | `OFFICIAL` | Phase 5 | Phase 5 |

### `PayPal-Request-Id` support, verified per endpoint (section 4)

This is the check the master prompt said not to assume. **The assumption would have been wrong.**

| Endpoint | Method + path | `PayPal-Request-Id` documented? | Mark |
| --- | --- | --- | --- |
| Create order | `POST /v2/checkout/orders` | **Yes.** Listed under Header Parameters: "`PayPal-Request-Id` string Optional - A unique ID identifying the request header for idempotency purposes." | `OFFICIAL` |
| Capture payment for order | `POST /v2/checkout/orders/{id}/capture` | **Yes.** Same wording under Header Parameters. | `OFFICIAL` |
| **Add tracking for an order** | `POST /v2/checkout/orders/{id}/track` | **No.** The Header Parameters section lists only `Authorization` and `PayPal-Auth-Assertion`. There is **no** `PayPal-Request-Id`. | `OFFICIAL` |
| Show order details | `GET /v2/checkout/orders/{id}` | Not yet read | `OPEN QUESTION` |
| Update/cancel tracking | `PATCH /v2/checkout/orders/{id}/trackers/{tracker_id}` | Not yet read | `OPEN QUESTION` |

**Consequence for rule R9.** MerchantShield's headline action is ADD_TRACKING, and that endpoint does **not** document idempotency-key support. Therefore:

- We must **not** send `PayPal-Request-Id` on add-tracking and claim idempotency from it.
- A read timeout on add-tracking is `UNKNOWN`, never `FAILED`, and must be resolved by **Reconcile** (read back the order) rather than by retrying.
- The README "Limitations" section must state the residual duplicate-call risk honestly.

### Add-tracking request shape (for Phase 5)

Required body fields, per the endpoint page: `tracking_number` (string, 1-64), `carrier` (enum, 1451 allowed values, `OTHER` + `carrier_name_other` as the escape hatch), `capture_id` (string). Optional: `notify_payer` (bool, default false), `items[]`.

Note `capture_id` is **required** - so an order must have been captured before tracking can be added. That ordering constraint shapes the Phase 5 demo flow.

---

## 3. My choices (no external authority)

| Choice | Rationale | Mark | Where | Test |
| --- | --- | --- | --- | --- |
| Three provenance labels on every row | Rule R5 | `MY CHOICE` | `app/models/enums.py` | `test_orders.py` |
| Money serialized as a 2-dp string | A float cannot hold `189.99` exactly; wrong amounts in an evidence packet are worse than no packet | `MY CHOICE` | `app/schemas/common.py` | `test_get_seeded_order_returns_full_provenance` |
| Timestamps as `...Z` with milliseconds | Rule R10, unambiguous for evidence | `MY CHOICE` | `app/core/timeutil.py` | `test_time_utc.py` |
| Reject non-sandbox PayPal hosts by allowlist | Enumerating production hosts would miss one | `MY CHOICE` | `app/core/config.py` | `test_config_guard.py` |
| Backend creates its own SQLite parent directory | Makes a freshly extracted ZIP work; removes a test-runner ordering dependency | `MY CHOICE` | `app/db/base.py` | `test_db_bootstrap.py` |
| SQLite `PRAGMA foreign_keys=ON` per connection | SQLite defaults to OFF, which would break the FK-safe delete order in `/api/demo/reset` | `MY CHOICE` | `app/db/base.py` | Phase 1 |
| One service: FastAPI serves `frontend/dist` | Single origin, so no CORS and a judge runs one command | `MY CHOICE` | `app/main.py` | `smoke.spec.ts`, HTTP smoke log |

---

## 4. Open questions to close before the relevant phase

| # | Question | Needed by |
| --- | --- | --- |
| Q1 | Verbatim wording of judging criteria 2-5 | Phase 7 (README mapping) |
| Q2 | Does the Sandbox account support the Disputes API, and with what limits? | Phase 5/6 |
| Q3 | How does each endpoint's documentation describe its error responses? Which 4xx genuinely prove "no side effect"? | Phase 2/5 |
| Q4 | Is a PayPal Agent Toolkit or MCP server available in a **read-only** configuration, and how are write tools disabled? | Phase 6 |
| Q5 | `PayPal-Request-Id` support on `GET /v2/checkout/orders/{id}` and the trackers PATCH | Phase 5 |
| Q6 | Your eligibility: are you at or above the age of majority where you reside? | **Before submitting** |
