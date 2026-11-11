# Decisions

Numbered, dated, and reversible. Each entry says what was decided, why, and
what would make me change my mind.

---

## UNVERIFIED PAYPAL CALLS

Rule R3 requires this list to exist and to be honest.

**As of Phase 7: no live PayPal API call has been made from this build.** The
client exists, is covered by mocked-HTTP tests, and has never been pointed at
the Sandbox with a real credential - this environment has no credential and
cannot reach any host except GitHub, npm and PyPI.

| Endpoint | Written | Called against the Sandbox? |
| --- | --- | --- |
| `POST /v1/oauth2/token` | Yes | No |
| `POST /v2/checkout/orders` | Yes | No |
| `POST /v2/checkout/orders/{id}/capture` | Yes | No |
| `GET /v2/checkout/orders/{id}` | Yes | No |
| `POST /v2/checkout/orders/{id}/track` | Yes | No |
| Disputes API | Not implemented (out of scope; submission is SIMULATED) | No |

`scripts/verify_paypal_live.py` exists precisely so the project owner can turn
one row of this table into "Yes" and record the output. Until that runs, the
table stays as it is.

---

## D-001 - Work inside the existing repository, in a `merchantshield-ai/` subfolder

**Date:** 2026-11-01
**Status:** Accepted (with a caveat you should know about)

The master prompt says "create a fresh folder `merchantshield-ai/`. Do not
assume an existing repository." My workspace is a checkout of
`ShoryaPratapSinghChandrawat/qff2026-phase1-s1-isling_chain`, which is an
unrelated project, and I cannot work outside it.

So I created `merchantshield-ai/` as a **self-contained subfolder**: it has its
own `.gitignore`, `.gitattributes`, `LICENSE`, `PHASE`, `.github/workflows/`
and dependency manifests. Nothing in it references the parent repository.

**Caveat (important, and it affects the hackathon requirement):** GitHub only
runs workflows found at `<repo-root>/.github/workflows/`. Because the CI file
lives at `merchantshield-ai/.github/workflows/ci.yml`, it will **not** trigger
in this combined checkout. It is correct and ready for the standalone repo.

To get real CI evidence we need one of:

- **(a)** copy the workflow to the repo root with
  `defaults.run.working-directory: merchantshield-ai`, or
- **(b)** push `merchantshield-ai/` to its own public GitHub repository, which
  the hackathon requires anyway ("Provide a URL to your public code
  repository").

I have not done either yet, because the prompt says not to commit without
being asked. **(b) is the right long-term answer.**

---

## D-002 - PayPal Sandbox hostnames are enforced by allowlist, not blocklist

**Date:** 2026-11-01
**Status:** Accepted

`validate_paypal_base_url` accepts only `*.sandbox.paypal.com` plus loopback
hosts, and rejects everything else. A blocklist of production hostnames would
eventually miss one. The loopback exception exists so Phase 5 tests can point
the client at a local stub without weakening the rule.

The check runs as a Pydantic field validator, so a bad `PAYPAL_BASE_URL` fails
at `Settings()` construction - i.e. at startup, before any request is served.

Tested in `backend/tests/test_config_guard.py`, including look-alike hosts such
as `https://api-m.sandbox.paypal.com.evil.test`.

**Would change my mind:** nothing short of the project ceasing to be
Sandbox-only, which rule R4 forbids.

---

## D-003 - Do not send `PayPal-Request-Id` on add-tracking

**Date:** 2026-11-01
**Status:** Accepted (documentation verified)

Section 4 told me to verify rather than assume which endpoints support
`PayPal-Request-Id`. I read all three relevant endpoint pages:

- `POST /v2/checkout/orders` - **supports** it (listed under Header Parameters).
- `POST /v2/checkout/orders/{id}/capture` - **supports** it.
- `POST /v2/checkout/orders/{id}/track` - **does not document it.** The Header
  Parameters section lists only `Authorization` and `PayPal-Auth-Assertion`.

So the assumption would have been wrong, and MerchantShield's headline action
(ADD_TRACKING) is precisely the one without a documented idempotency key.

Consequences, locked in now so Phase 2 and Phase 5 are built around them:

1. Add-tracking requests carry **no** `PayPal-Request-Id`.
2. A read timeout on add-tracking is classified `UNKNOWN`, never `FAILED`.
3. `UNKNOWN` leaves only via **Reconcile** (read the order back), never via a
   direct retry. Rule R9 forbids claiming exactly-once semantics here.
4. The README "Limitations" section must state the residual duplicate-call
   risk in plain English.

**Would change my mind:** PayPal documenting idempotency support on that
endpoint. I will re-check the page in Phase 5 and record the date.

---

## D-004 - Pull the production-hostname guard forward into Phase 0

**Date:** 2026-11-01
**Status:** Accepted

Section 5 specifies the guard as part of the Phase 5 PayPal work. I implemented
it in Phase 0 instead.

Reason: it is a safety rule, not a feature. If it arrives in Phase 5, there are
four phases of git history in which a production hostname is reachable. The
cost is one small module and eight tests; the benefit is that no snapshot of
this project can ever point at production.

---

## D-005 - Money is a string in JSON, `Numeric` in the database

**Date:** 2026-11-01
**Status:** Accepted

`189.99` is not representable in binary floating point. A dispute evidence
packet that prints `189.98999999999998` is not merely ugly - it is wrong in the
one field a judge or a PayPal agent would check first.

Stored as `Numeric(12, 2)` (SQLAlchemy maps to Python `Decimal`), serialized
as a fixed 2-decimal string via `MoneyStr` in `app/schemas/common.py`. The
frontend treats it as an opaque display string and never does arithmetic on it.

---

## D-006 - One service, SPA served by FastAPI

**Date:** 2026-11-01
**Status:** Accepted

FastAPI serves `frontend/dist` with SPA fallback; the API lives under `/api`;
Vite proxies `/api` in development. The browser therefore always talks to a
single origin, so there is no CORS configuration at all - which is the
strongest possible form of "no wildcard CORS with credentials".

It also means a judge runs one command to see the whole app, which is what the
rules ask for ("judges must be able to actually run or interact with a working
build").

The SPA catch-all explicitly returns JSON 404 for unmatched `/api/*` paths, so
a typo in an API path can never be answered with HTML that a client would try
to parse as JSON. Tested in `test_unknown_api_route_is_404_json_not_spa_html`
and in the Playwright spec.

---

## D-007 - Phase 0 seeds one order with a fixed timestamp

**Date:** 2026-11-01
**Status:** Accepted

The seeded order uses a hard-coded `2026-11-01T09:30:00Z` rather than "now".
That makes the Phase 0 test assertion on `created_at` exact instead of
approximate, and it satisfies rule R10's "fixed seeds". Phase 1 replaces this
with the 8 deterministic story orders and keeps the same approach.

---

## D-008 - Empty package directories were not created

**Date:** 2026-11-01
**Status:** Accepted

Section 8 shows `backend/services/` and `backend/ml/` in the final layout, and
also says "do not create empty files just to look complete". These two rules
conflict at Phase 0, where neither directory has any content.

I chose honesty over layout-matching: the directories are created in the phase
that first needs them (Phase 2/5 for `services/`, Phase 3 for `ml/`). The same
applies to `docs/QA.md`, which is a Phase 7 deliverable.

---

## D-009 - Node 24 is declared, but Node 22 was used to build here

**Date:** 2026-11-01
**Status:** Accepted, with a disclosure

`.nvmrc` says `24` and CI uses Node 24, per your environment. The build sandbox
only has **Node v22.22.3**, so the local `npm ci`, type-check and `vite build`
evidence in this phase was produced on Node 22.

Every pinned package declares support for both (`vite@8.3.5` requires
`^20.19.0 || >=22.12.0`). This is a real difference between my evidence and
your environment, which is exactly why Phase 0 stops for your Windows
verification.

---

## D-011 - `.env` is loaded, but the shell always wins

**Date:** 2026-11-01
**Status:** Accepted (fixes BUG-0004)

Originally `env_file=None`: the process environment was the only source of
configuration. That is defensible for a server, but it made the README lie -
it told you to copy `.env.example` to `.env`, and the app then ignored the
file. For a first-year student on Windows, re-exporting five `$env:` variables
in every new PowerShell window is also a needless trap.

The chosen shape:

| Source | Precedence |
| --- | --- |
| Real environment variables | **highest** - a stale `.env` can never override what you just exported |
| `<project root>/.env` | next |
| Field defaults | lowest |

Three details worth defending:

1. **The path is absolute**, derived from the module location, so it is found
   whether you launch uvicorn from `backend/` or the project root.
2. **`Settings()` constructed directly still ignores every file.** Only
   `get_settings()` loads one. Tests therefore stay hermetic by default, and
   an autouse fixture additionally points `MS_ENV_FILE` at a path that does
   not exist, so a developer's real `.env` can never change a test result.
3. **Rule R4 is unaffected.** The production-hostname validator runs on the
   merged settings, so `PAYPAL_BASE_URL=https://api-m.paypal.com` in a `.env`
   still refuses to start. There is a test for exactly that.

**Would change my mind:** deploying somewhere that injects config only as
environment variables - in which case the absent `.env` is simply skipped, so
nothing needs to change.

---

## D-010 - Playwright browsers cannot be downloaded in this sandbox

**Date:** 2026-11-01
**Status:** Accepted, with a disclosure

`npx playwright install chromium` fails here with `ECONNRESET` against
`cdn.playwright.dev`, which is outside the sandbox's network allowlist. There
is no system Chromium, Chrome or Firefox either.

Therefore **the Playwright tests have been written but never executed.** They
are marked `NOT VERIFIED` in the phase report. Two things close this gap:

1. your Windows run (`npx playwright install chromium` then `npm test`), and
2. the CI job, which installs Chromium with `--with-deps` and uploads the
   screenshots and console logs as build artifacts.

To compensate I ran an HTTP-level smoke test against the real uvicorn server
serving the real built bundle, saved at
`artifacts/phase-0/sandbox-linux/http-smoke.log`. That verifies the server
half of what Playwright would check (health, order JSON, 404s, SPA fallback,
asset serving) but **not** rendering, layout or console cleanliness.

---

## D-012 - Fixed ports 8010 and 5174, always on 127.0.0.1

**Decision.** The Playwright end-to-end server uses `127.0.0.1:8010`
(overridable with `MS_E2E_PORT`); the Vite dev server uses `127.0.0.1:5174`
with `strictPort: true`. Both are declared once in `frontend/tests/paths.ts`
and imported by `vite.config.ts` and `playwright.config.ts`, so they cannot
drift apart.

**Why fixed, not random.** A random port is unfindable when a process gets
stuck. A fixed one makes the recovery a single documented command:

```powershell
Get-NetTCPConnection -LocalPort 8010,5174 | Select-Object LocalPort,OwningProcess
```

**Why 8010 and not the previous 8099/5173.** 5173 is Vite's default, so it
collides with any other Vite project the owner has running. The pair was
moved together so they are easy to remember and to document as a set.

**Why the literal `127.0.0.1` and never `localhost`.** On Windows,
`localhost` can resolve to IPv6 `::1` while the server is listening on IPv4.
The result is a connection refusal that reads as "the server failed to
start". Using the literal address removes that class of confusion.

**What this does not claim.** It limits exposure to the local machine. It
does **not** guarantee that Windows Firewall or antivirus will never
interfere. Not verified on Windows.

---

## D-013 - `reuseExistingServer: false`, always - including locally

**Decision.** Playwright never reuses a server it did not start, in CI or on a
developer machine. Previously this was `!isCI`, i.e. reuse allowed locally.

**Why.** Reuse is an honesty hazard, not a convenience. A uvicorn left over
from an earlier session is running **old code**. Playwright would connect to
it, the suite would pass, and the report would describe code that is not the
code in the working tree. Of all the ways this project could produce a false
PASS, that is the easiest to trigger and the hardest to notice.

**Cost.** A leftover process is now a hard failure. That cost is paid down by
the config-load pre-flight (see BUG-0007), which names the port, shows the
PowerShell commands to find and stop the owner, and explicitly warns against
"fixing" it by setting `reuseExistingServer: true`.

---

## D-014 - 180-second webServer timeout

**Decision.** `webServer.timeout` is 180,000 ms, up from 120,000 and well
above Playwright's 60,000 default.

**Why.** The first Windows run pays simultaneously for Microsoft Defender
scanning a brand-new `.venv`, cold NTFS caches, and Python importing FastAPI
and SQLAlchemy for the first time. A slow cold start is not a failure, and a
timeout here produces the least informative error in the whole stack. Three
minutes is cheap insurance against a misleading red.

**Trade-off accepted.** When the backend genuinely cannot start, the operator
waits three minutes for the message. The README troubleshooting table tells
them what to do: run the server by hand (step 6) and read the real error.

---

## D-015 - One SQLite database per end-to-end run

**Decision.** The e2e database is `e2e-phase0-<run id>.sqlite3`, not a fixed
name. `globalSetup` deletes databases from *previous* runs only.

**Why.** Playwright starts `webServer` **before** `globalSetup`, so a fixed
filename meant globalSetup was deleting a file the backend already had open.
Full reasoning and evidence: BUG-0006.

**Rejected alternative.** Keeping the fixed name and making the backend reset
its own database on start-up. That would put a destructive code path into
application code for the benefit of the test harness - precisely the kind of
thing that later gets triggered in a context nobody predicted.

---

## D-016 - `allowImportingTsExtensions` enabled in the frontend tsconfig

**Decision.** `frontend/tsconfig.json` sets
`"allowImportingTsExtensions": true` so `vite.config.ts` can import
`./tests/paths.ts` with its extension.

**Why.** Vite 8's native config loader warns that extensionless imports will
stop working in a future major. Rather than carry a warning, or duplicate the
port constants and hope the copies stay in sync, the import keeps its
extension.

**Why this is safe.** The flag is only legal when `noEmit` is true, which it
already is - `tsc` here type-checks and Vite does the emitting. It loosens no
type checking. Verified: `tsc --noEmit` exit 0 and `vite build` exit 0 with
no warnings (RAN HERE).

---

## D-017 - `--name` renames the ZIP file, never the folder inside it

**Decision.** `package_release.py --name` sets the archive filename only. The
single top-level folder inside the archive is always `merchantshield-ai/`.

**Why.** The extracted path is what every README command, every relative
import and every documented `cd` depends on. If `--name` changed it, a re-cut
archive would extract to a differently named folder and silently invalidate
the instructions. The filename is free to vary; the extract path is not.

Names are validated: empty, padded, `.zip`-suffixed, `.`/`..`, and anything
containing `/ \ : * ? " < > |` are rejected before any file is written.

---

## D-018 - The Phase 0 spec is named `walking-skeleton.spec.ts`

**Decision.** `frontend/tests/smoke.spec.ts` was renamed to
`walking-skeleton.spec.ts`.

**Why.** "Walking skeleton" is the name this phase is called everywhere else
in the plan: the thinnest end-to-end slice that proves the whole stack is
connected. "Smoke" suggested a broader suite than three tests. The rename
makes the file match the vocabulary used in the phase plan and the README.

No behaviour changed; the file is the same tests plus the failure-proof log
capture described in BUG-0006's neighbourhood.

---

## D-019 - The project is now the repository root, not a `merchantshield-ai/` subfolder

**Decision.** The contents of `merchantshield-ai/` were moved to the root of
this repository (`MerchantShield-AI`, branch `arena/6b2fe94a-merchantshield-ai`).

**Why.** D-001 put the project in a subfolder of an unrelated QFF2026 repository,
which had two costs that HANDOFF.md already recorded: GitHub only reads
workflows from `.github/workflows/` at the repository root, so `ci.yml` had
never triggered; and `git archive HEAD` produced an empty handoff because the
subfolder was never tracked. Both disappear once the project *is* the repository.

**What this did not change.** No application code, no test, no requirement and
no configuration value was edited to make this move work. The workflow's
internal paths were already relative to the project root (`backend/…`,
`frontend/…`, `scripts/…`, `PHASE`), so they stayed correct - each one was
checked against the filesystem after the move. The Playwright and Vite configs
resolve every path from the test file's own location, so they are unaffected by
the move (verified by the browser run below).

---

## D-020 - Node 24 installed from the npm `node` package in the sandbox

**Decision.** The sandbox's own Node is v22.22.3, but `.nvmrc`, `engines` intent
and CI all say Node 24, so `node@24` (v24.22.2) was installed from the npm
registry and put first on `PATH` for the frontend commands. npm stayed at
10.9.8, executed by that Node 24 binary.

**Why.** MASTER 4.1 requires Node 24 and explicitly permits the npm `node`
package as the install route. Running the build on a different major and then
describing it as a Node 24 run would be exactly the kind of unverified claim
this project refuses to make.

**Caveat.** This is a per-command `PATH` change, not a system install. Anything
run in the sandbox outside those commands still uses Node 22. The measured
results (`tsc --noEmit` exit 0, `vite build` exit 0, Playwright 6/6) are
therefore Node 24.22.2 results; Windows 11 with your Node 24 remains unverified.

---

## D-021 - A real browser ran, but not the pinned one

**Decision.** The browser suite was executed in this sandbox against
**Chromium 153** extracted from the `@sparticuz/chromium` npm package (its
`chromium.br` payload, plus the shared libraries in its `al2023.tar.br`,
supplied with `LD_LIBRARY_PATH`), through a **local, uncommitted** config that
only sets `launchOptions.executablePath`. All 6 tests (3 tests x 1500x900 and
390x844) passed. Evidence: `artifacts/phase-0/sandbox-linux/`.

**Why not the pinned build.** Three attempts:

1. `npx playwright install chromium` - failed: `cdn.playwright.dev`
   `ECONNRESET` on both the Chrome-for-Testing and the headless-shell builds.
2. Look for a system browser instead - none installed, and the image has no
   `libnss3`, `libatk`, `libcups`, `libgbm`, `libX*`, `libasound`, `libpango`
   or `libcairo`, with no root and no reachable package mirror to add them.
3. `@sparticuz/chromium` from the npm registry (an allowed host) - launched,
   rendered, screenshotted. This is the attempt that worked.

**What this proves.** The SPA, the FastAPI server, the SPA-fallback routing, the
seeded SIMULATED record, the source chip, and a silent console all behave as the
tests assert, in a real browser engine, at both viewports.

**What it does NOT prove.** That the *pinned* Playwright Chromium 156 build
passes - it was never downloaded. Chromium 153 is four major versions behind it,
so a Playwright-version-specific regression would not have shown up here.
Nothing about Windows. Nothing about CI. The repository's own
`playwright.config.ts` was used unchanged apart from the browser path; no test
was skipped, deleted, relaxed or rewritten.

**How to reproduce it exactly.** From `frontend/`, with the browser extracted:

```bash
# one-time, outside the repo
npm install @sparticuz/chromium            # 67 MB, ships bin/chromium.br
node --input-type=module -e "import c from '@sparticuz/chromium/build/index.js'; await c.executablePath()"   # -> /tmp/chromium
node -e "zlib.brotliDecompressSync(fs.readFileSync('.../bin/al2023.tar.br'))" > al2023.tar && tar -xf al2023.tar -C /tmp/al2023libs
# then, in frontend/, a local config that ONLY overrides the browser:
MS_ARTIFACT_ENV=sandbox-linux MS_PYTHON=../.venv/bin/python LD_LIBRARY_PATH=/tmp/al2023libs/lib \
  npx playwright test --config=playwright.local-browser.config.ts
```

`playwright.local-browser.config.ts` imported `./playwright.config`, spread it,
and set `use.launchOptions = { executablePath: '/tmp/chromium', args:
['--no-sandbox','--disable-dev-shm-usage'], env: { ...process.env,
LD_LIBRARY_PATH: '/tmp/al2023libs/lib' } }`. That file was deleted after the
run and was never committed, so the committed configuration is unchanged.

**Tag.** Phase 0 is tagged `phase-0` on this basis, with the tag message stating
the substitution. MASTER 10.3's upgrade path (the CI run, or your Windows
machine) is still the evidence that would close the remaining gap.

---

## D-022 - README corrections made during the move

**Decision.** Four factual claims in README.md were corrected in the same
commit as the move: "39 passing backend tests" (86 exist and passed),
`cd …\merchantshield-ai` (no longer the project root), "8 deterministic story
orders" (MASTER section 9 says 15), and `LLM_PROVIDER` listing
`anthropic`/`openai` (MASTER 10.5 cuts every provider except `gemini` and
`none`).

**Why.** MASTER wins over any other document, and a README that contradicts a
measurement taken in the same session is worse than no README. No test or code
was touched. Recorded as BUG-0010.

---

## D-023 - GitHub Actions ran for real, and the pinned browser passed there

**What happened.** The branch and the `phase-0` tag were pushed on 2026-11-07.
Both pushes triggered the workflow - the first time it has ever run, because it
used to sit in a subfolder GitHub never reads. Both runs **succeeded**:

| Run | Trigger | Result | Jobs |
| --- | --- | --- | --- |
| [42356743578](https://github.com/ShoryaPratapSinghChandrawat/MerchantShield-AI/actions/runs/42356743578) | push of tag `phase-0` | success, 46 s | backend tests 13 s; frontend build + Playwright (Node 24) 43 s; mutation check 24 s |
| 42356743073 | push of the branch | success, 1 m 20 s | all three jobs success |

Every step in the Playwright job succeeded, including
`Install Chromium for Playwright` (`npx playwright install --with-deps
chromium`) and `Upload screenshots, console logs and the HTML report`. That
upload step is configured with `if-no-files-found: error`, so its success means
screenshot and console-log files were actually produced by the run.

**Why this matters for the honesty trail.** MASTER 10.3 names a CI run as the
evidence that upgrades a `-browser-unverified` tag. This is that evidence, and
it is stronger than the sandbox run: the runner downloaded the **pinned**
Playwright Chromium (revision 1248 / Chrome 156), on Ubuntu with Node 24, from
the committed `playwright.config.ts` with no local override at all.

**What I could NOT see.** The raw job log and the uploaded artifacts. The
sandbox's egress allowlist blocks both `*.blob.core.windows.net` (artifacts) and
the logs endpoint, so the exact "N passed" line and the screenshots themselves
were not read here. The per-step conclusions come from the GitHub API and are
quoted above; treat "6/6 passed in CI" as *strongly implied* by a green
Playwright step with a successful artifact upload, not as a line I read.

**Still not verified.** Windows 11. `scripts/windows_check.ps1` (never executed
or parsed anywhere). Any PayPal call. The Node 20 deprecation annotations the
API reported for `actions/checkout@v4`, `actions/setup-python@v5`,
`actions/setup-node@v4` and `actions/upload-artifact@v4` are warnings, not
failures, and are worth bumping later.

---

## D-024 - The action allowlist lives in the engine, not in the request schema

**Date:** 2026-11-09
**Status:** Accepted

The first version typed `ProposeActionRequest.type` as a `Literal` of the three
allowed actions. That produced a correct 422 for an unknown type, but the body
was Pydantic's field-validation text, which says nothing about what *is*
allowed.

The type is now a plain `str`, and `services/actions.py` raises
`InvalidActionType` with the allowlist in the message. The status code is
unchanged (422), and `tests/test_actions.py` asserts the message mentions the
allowlist. A caller who guesses wrong learns something.

**Would change my mind:** if the API were public and machine-consumed enough
that the OpenAPI enum mattered more than the human-readable error.

---

## D-025 - Every draft is a version; origin is recorded per version

**Date:** 2026-11-09
**Status:** Accepted

Saving an edited draft never mutates v1. It appends v2 with
`origin="Merchant edit"`, keeping `"AI draft"` and `"Template draft"` on the
versions that were actually produced that way. Approving marks a version
`APPROVED`; submitting requires an approved version and is always recorded with
`submission_mode="SIMULATED"`, because no PayPal Disputes API call is made.

The alternative - one mutable draft - would lose the only audit trail that
matters when a merchant is asked "did you send exactly what you approved?".

---

## D-026 - `UNKNOWN` needs a human, and `NOT_APPLIED` needs a signature

**Date:** 2026-11-09
**Status:** Accepted

A timeout, 5xx, connection reset or crash means "the request may have been
applied". The action becomes `UNKNOWN`. The UI does not offer a retry button in
that state; it offers reconciliation, which reads the order back from PayPal.

Marking the action `NOT_APPLIED` requires `confirm_not_applied=true` in the
request body, which the UI only sends when the merchant ticks "I checked PayPal
and it was not applied". Without the flag the API answers 409.

This is two extra clicks in the rare case, and it is the difference between a
duplicate tracking number and none. Tested in
`tests/test_actions.py::test_reconcile_not_applied_requires_confirmation`.

---

## D-027 - The mock adapter must fail in the same taxonomy as the real client

**Date:** 2026-11-09
**Status:** Accepted (bug fix BUG-0013)

The mock's failure-injection modes (`timeout`, `5xx`, `reset`, `crash`) exist to
exercise the `UNKNOWN` path. The facade originally caught every `PayPalError`
in mock mode and returned `FAILED`, so the injection tested nothing and a
possibly-applied failure was mislabelled as a definite one.

Split into `(PayPalConnectionError, PayPalRequestRejected) -> FAILED` and
`PayPalError -> UNKNOWN`. The tests now assert the taxonomy through the facade,
not just inside the client.

---

## D-028 - `/api` responses are `Cache-Control: no-store`

**Date:** 2026-11-09
**Status:** Accepted

A browser may heuristically cache a `GET` JSON response that carries no
validators. During the Playwright work this produced a real, visible lie: a
draft was approved server-side while the card still said `DRAFT`.

The client sets `cache: 'no-store'` and a middleware sets `Cache-Control:
no-store` on every `/api` response. Two belts, because this class of bug is
invisible until it embarrasses you in front of a judge.

---

## D-029 - One definition of "a demo row", used by every statement

**Date:** 2026-11-09
**Status:** Accepted

`reset_demo` had the rule `is_demo AND source != PAYPAL_SANDBOX` written twice.
Each copy protected the other in practice, so removing either one still kept
live rows - which meant the mutation check reported a *surviving* mutant, and
correctly so: nothing could observe the difference.

The rule now lives in `seed.demo_rows_filter()` and is spread into every
statement. The mutation removes it once, both statements change, and the test
that keeps a live Sandbox order across a reset fails as it should.

---

## D-030 - The mutation check is the reason two tests exist

**Date:** 2026-11-09
**Status:** Accepted

Expanding the registry to Phases 2, 5 and 6 found two genuine gaps:

1. **M2-2 survived.** Eight concurrent executes *did* produce one external call,
   but only because SQLite serialized the writes; the conditional claim was
   never actually exercised at its boundary. Added
   `test_claim_is_conditional_on_approved`, a unit test that claims once and
   requires the second claim to lose.
2. **M2-4 survived as written.** "Set `EXECUTED` before the call" was
   unobservable in-process, because the failure branch overwrote it. That
   mutation tested nothing, so it was replaced with a meaningful one: treat
   *every* external outcome as `EXECUTED`. That is caught immediately.

Result after the changes: 16 of 16 applicable mutations caught across phases
0, 1, 2, 5 and 6 (`artifacts/phase-*/MUTATION_REPORT.md`).

---

## D-031 - Hash routing, no router dependency

**Date:** 2026-11-09
**Status:** Accepted

The app has seven pages and no deep-link requirements beyond "share a page".
A `hash` plus one piece of state does that, keeps the SPA-fallback story in
FastAPI trivial, and adds a dependency only if the product grows real routes.
The Playwright suite navigates with `#/orders` and friends, so the choice is
under test.

---

## D-032 - `MS_CHROMIUM_PATH` exists for this sandbox, and says so

**Date:** 2026-11-09
**Status:** Accepted, with a documented limit

Playwright's pinned browser download is blocked in this environment
(`cdn.playwright.dev` is not on the egress allowlist). Rather than pretend the
suite cannot run, `playwright.config.ts` reads `MS_CHROMIUM_PATH` and uses that
binary if set.

CI never sets it and installs the pinned browser, so CI still tests what a judge
would run. The sandbox run used Chromium 153 instead of the pinned 156; that is
recorded in the README's verification table rather than glossed over.

---

## D-033 - The browser suite lives in `frontend/e2e`, 15 tests, two viewports

**Date:** 2026-11-09
**Status:** Accepted (closes a HANDOFF section 5 gap)

One suite, one directory, one config. 15 tests run at 1500x900 and 390x844
against the built SPA served by FastAPI - the production arrangement, not the
Vite dev proxy. Every test fails on any console error or page error, and writes
its console log from a `finally` block so the evidence survives a failure.

---

## D-034 - The approve endpoint returns the full draft, and a test pins it

**Date:** 2026-11-09
**Status:** Accepted (bug fix BUG-0014)

`POST /drafts/{id}/approve` returned `{id, status, version}` while
`POST /drafts` returned the whole draft. The frontend's mapper is strict, so it
threw; the approval had succeeded server-side and the card still read `DRAFT`.

Both endpoints now return `draft_payload()`, and
`test_approve_returns_the_same_full_draft_shape_as_create` compares the key sets
so the shapes cannot drift again.

---

## D-035 - `frontend/tests/` was deleted, not merged forward

**Context.** Rewriting history was not an option: the remote branch carried three
commits (`51ed15c`, `048cdd4`, `70b785f`) that this checkout never had, because
`.venv` and Git state are reset between sandbox sessions. The branch was therefore
merged (`--no-ff`), and 33 files conflicted.

**Resolution.** Every conflict resolved to this checkout's version (`--ours`),
which is a strict superset except for one directory: the remote's
`frontend/tests/` (`global-setup.ts`, `paths.ts`, `walking-skeleton.spec.ts`).
That directory was superseded by `frontend/e2e/` when the suite grew from the
Phase 0 walking skeleton to 16 tests across 8 spec files, and
`playwright.config.ts` points `testDir` at `e2e`. Keeping both would have left a
second, never-executed copy of the harness in the repository - exactly the kind of
dead file that makes a judge doubt the tree.

**What was preserved from the remote instead of by the merge:** the D-023 CI
record (it merged cleanly into `DECISIONS.md`, because this checkout had appended
after it), and the `README.md` row that describes it - which was then corrected
in this commit to say the CI run is green **on `048cdd4`**, and *not yet verified*
for the later phases.

**Verification after the merge:** 215 backend tests, `tsc --noEmit`, `vite build`,
32/32 browser runs (twice, consecutively), and 16/16 mutations caught - all in the
clean copy, from the merged tree.

