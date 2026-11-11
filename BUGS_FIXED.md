# Bugs found and fixed

Only bugs that actually occurred during development, with the evidence that
showed them and the test that now prevents a repeat. No invented entries.

---

## BUG-0001 - SQLite refuses to create a database in a missing directory

**Phase:** 0
**Found:** 2026-11-01, starting uvicorn with
`DATABASE_URL=sqlite:///../artifacts/phase-0/sandbox-linux/preview.sqlite3`
while `artifacts/` did not exist.

**Symptom** (real output, trimmed):

```
sqlite3.OperationalError: unable to open database file

The above exception was the direct cause of the following exception:
...
  File ".../backend/app/db/base.py", line 92, in init_db
    Base.metadata.create_all(bind=get_engine())
...
sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) unable to open database file
ERROR:    Application startup failed. Exiting.
```

**Why it matters, beyond my own convenience.** The error message says nothing
about directories, so it reads like a permissions problem. More importantly it
is exactly the state of a **freshly extracted ZIP**: the Playwright run points
`DATABASE_URL` at `artifacts/phase-0/<env>/e2e-phase0.sqlite3`, and a fresh
extract has no `artifacts/` folder. The phase requirement that the browser test
"work in a freshly extracted ZIP where `artifacts/` does not exist" would have
failed on the very first run.

**Root cause.** SQLite creates a missing *file* but never a missing *directory*.

**Fix.** `backend/app/db/base.py` now has `_ensure_sqlite_parent_dir()`, called
from `get_engine()` before the engine is created. It parses the SQLite URL,
skips in-memory and non-SQLite URLs, and `mkdir(parents=True, exist_ok=True)`
on the parent.

**Why fixed in the backend rather than in `global-setup.ts`.** The test harness
*could* create the directory first, but that only works if Playwright runs
`globalSetup` before it launches `webServer` - an ordering I had asserted in a
comment without verifying it. Fixing it in the application removes the
dependency entirely and also helps anyone who just sets `DATABASE_URL` to a
fresh path by hand. The unverified claim was deleted from the comment.

**Regression test.** `backend/tests/test_db_bootstrap.py`:

- `test_startup_creates_a_missing_sqlite_parent_directory` - asserts the nested
  path does not exist, boots the app, then asserts both the health and order
  endpoints work and the file was created.
- `test_in_memory_sqlite_url_is_left_alone`
- `test_non_sqlite_url_is_left_alone`

**Verified:** 32 backend tests pass; the server then started and served the
full HTTP smoke test (`artifacts/phase-0/sandbox-linux/http-smoke.log`).

---

## BUG-0002 - Unverified ordering claim written into a code comment

**Phase:** 0
**Found:** 2026-11-01, while fixing BUG-0001.

**Symptom.** `frontend/tests/global-setup.ts` contained the comment:

> "Note: Playwright launches `webServer` *after* globalSetup, so the backend
> always sees the fresh file."

I had not verified that ordering in the Playwright 1.64.1 documentation or by
running it. Under rule R1 that is a fabricated claim, even though it is only a
comment - comments are what the next reader trusts.

**Fix.** The claim was removed and replaced with a statement of what is
actually true and testable: the suite does **not** depend on that ordering,
because the backend creates its own SQLite parent directory.

**Lesson recorded.** "It is only a comment" is not an exemption from R1.

---

## BUG-0003 - Secret scanner reported a false positive on an empty placeholder

**Phase:** 0
**Found:** 2026-11-01, on the first real run of `scripts/package_release.py`.

**Symptom** (real output):

```
[package] files to include : 60
[package] scanning for secrets...
[package] ABORT - possible secrets found:
          .env.example: Non-empty LLM_API_KEY assignment (LLM_AP...)
=== EXIT: 1 ===
```

`.env.example` deliberately ships `LLM_API_KEY=` with no value, so this was a
false positive - and it blocked packaging entirely.

**Root cause.** The pattern was
`LLM_API_KEY\s*=\s*['\"]?[A-Za-z0-9_\-]{8,}`. In Python regex `\s` matches
newlines. Given

```
LLM_API_KEY=
LLM_MODEL=
```

the `\s*` after `=` consumed the newline and `[A-Za-z0-9_-]{8,}` then matched
the *next line's variable name* `LLM_MODEL`. The scanner was effectively
reading across line boundaries.

**Why it matters more than a false positive.** The same bug works in the other
direction. A genuine secret sitting on the line *after* an empty placeholder
would be reported against the wrong variable, and more importantly the
anchoring was never doing what it claimed. A security check that is wrong
about *where* it matched cannot be trusted about *whether* it matched.

**Fix.** Both environment-variable patterns now use `[ \t]*` instead of `\s*`,
so they cannot cross a newline. A `PAYPAL_CLIENT_ID` pattern was added at the
same time. The reasoning is recorded as a comment above the patterns so nobody
"simplifies" it back to `\s*`.

**Verified two ways:**

1. Packaging now succeeds and reports `secret scan : clean`.
2. A planted fake secret file was scanned and **was** detected, proving the
   fix did not simply disable the check:

```
findings: 2
  - docs/_tmp_probe.txt: Anthropic key (sk-ant...)
  - docs/_tmp_probe.txt: Non-empty PAYPAL_CLIENT_SECRET assignment (PAYPAL...)
SELF-TEST PASSED: scanner detects planted secrets
```

The probe file was deleted immediately afterwards and is not in the archive.

**Follow-up owed:** this self-test was run by hand. It should become a real
pytest case in Phase 1 so it runs on every CI build.

---

## BUG-0004 - The README told you to create a `.env` the app silently ignored

**Phase:** 0
**Found:** 2026-11-01, auditing the Windows quick-start before handing it over.

**Symptom.** `README.md` said `Copy-Item .env.example .env`, and
`.env.example` exists for exactly that purpose - but `app/core/config.py` had
`env_file=None`, so the file was never read. Demonstrated directly:

```
### DEFECT 1 PROOF: README tells you to create .env, but does the app read it?
82:        env_file=None,  # the process environment is the single source of truth

--- writing a .env with DEMO_MODE=false and booting with NO shell env vars:
  .env says DEMO_MODE=false ; app actually sees demo_mode = False
  .env says PAYPAL_MODE=mock; app actually sees paypal_mode = auto

  => the .env file is IGNORED.
```

`paypal_mode` is the tell. The file said `mock`; the app reported `auto`, its
default. (`demo_mode` matching was a coincidence - `false` is also the
default, which is precisely how this kind of bug hides.)

**Why it matters.** This is a beginner-hostile failure. You would copy the
file, set `PAYPAL_CLIENT_ID` in it, see `paypal_credentials_present: false`,
and have no idea why. Worse, `PAYPAL_MODE=mock` in `.env` would be ignored and
the app would fall back to `auto` - the opposite of a safe default.

**Fix.**

- `resolve_env_file()` returns `<project root>/.env` (absolute, so it is found
  whether you launch uvicorn from `backend/` or the project root), overridable
  with `MS_ENV_FILE`.
- `get_settings()` passes it as `_env_file`. Pydantic-settings precedence
  means **real environment variables still win over `.env`**, so a stale file
  cannot beat what you just exported.
- `Settings()` constructed directly still ignores any file, keeping it
  hermetic.
- `demo_mode_was_explicit` now also inspects the `.env` file, so setting
  `DEMO_MODE` there no longer produces a spurious "DEMO_MODE is not set"
  startup warning. Commented-out lines do not count as a choice.

**Verified** by re-running the exact failing experiment:

```
  env file found at: .../merchantshield-ai/.env
  .env PAYPAL_MODE=mock -> app sees paypal_mode = mock   <-- was 'auto' before the fix
  demo_mode_was_explicit = True (no spurious startup warning)

### shell still beats .env:
  .env says false, shell says true -> app sees demo_mode = True
```

**Regression tests.** `backend/tests/test_env_file.py`, 7 cases, including
`test_env_file_cannot_enable_a_production_paypal_host` - rule R4 must survive
configuration arriving by a new route.

**Test isolation added at the same time.** A new autouse fixture
`_isolate_env_file` points `MS_ENV_FILE` at a non-existent path for every
test. Without it, a developer with a real `.env` would get different results
from CI. `scripts/mutation_check.py` also stopped copying real `.env` files
into its temp sandbox.

---

## BUG-0005 - `npm test` would have failed on Windows without an activated venv

**Phase:** 0
**Found:** 2026-11-01, same audit. **Found by inspection, not by a Windows
run - I have no Windows machine.**

**Symptom (predicted, not observed).** `playwright.config.ts` launched the
backend with the bare command `python -m uvicorn ...`. The normal Windows
workflow is to open a terminal, `cd frontend`, and run `npm test`. If
`.\.venv\Scripts\Activate.ps1` was not applied in that terminal, `python`
resolves to the system interpreter, which has no `uvicorn`.

Playwright would not show "No module named uvicorn". It would show
`Timed out waiting 120000ms from config.webServer`, which points the reader at
the wrong problem entirely.

**Fix.** `resolvePython()` in `playwright.config.ts` now prefers, in order:

1. `MS_PYTHON`, if set;
2. `.venv\Scripts\python.exe` on Windows, `.venv/bin/python3` or
   `.venv/bin/python` elsewhere;
3. plain `python` from `PATH`.

> **Superseded by BUG-0009 (2026-11-02).** Step 3 was itself the bug: falling
> back to a system `python` reintroduces the misleading webServer timeout.
> The resolver now throws instead of returning `python`.

Resolved paths containing a space are quoted, because
`C:\Users\First Last\...` is ordinary on Windows.

**Verified (Linux only).** The resolver picks
`.venv/bin/python3`, and that interpreter does have the dependencies
(`uvicorn 0.34.0 | fastapi 0.115.6`). The Windows branch is **unverified** -
it is reached only on `process.platform === 'win32'`.

---

## BUG-0006 - The browser suite deleted a database the backend already had open

**Phase:** 0
**Found:** 2026-11-02, while running the Playwright harness end to end in the
Linux sandbox (RAN HERE).

**How it was found.** Not by reading the code. I ran
`npx playwright test` and read the ordering of the log lines:

```
[WebServer] ... app.db.seed | Seeded 1 demo order (source=SIMULATED, is_demo=true).
[global-setup] artifacts -> .../artifacts/phase-0/local-windows
```

The backend seeds **before** `globalSetup` prints anything. Playwright starts
`webServer` first and runs `globalSetup` second. I had assumed the opposite.

**Symptom.** `global-setup.ts` deleted `e2e-phase0.sqlite3` (and its `-wal` /
`-shm` siblings) to guarantee an empty database. Because the server was
already up, it was deleting a file that the uvicorn process had **open**:

- **Linux:** `unlink` on an open file succeeds. The inode survives for the
  open handle, so the server keeps happily writing to a file that no longer
  has a name. Everything appears to pass. The bug is invisible.
- **Windows:** SQLite opens the database without `FILE_SHARE_DELETE`, so
  `fs.rmSync` hits a sharing violation (`EBUSY`/`EPERM`) and `globalSetup`
  throws, aborting the entire run.

This is exactly the shape of defect that passes on CI and fails only on the
one machine that matters.

**Fix.** Remove the hazard rather than argue about the timing. Each run now
uses its own database file, named after a per-run id
(`e2e-phase0-<run id>.sqlite3`, see `E2E_RUN_ID` in `frontend/tests/paths.ts`).
A fresh name cannot pre-exist, so it is always empty, so nothing has to be
deleted while it is open. `globalSetup` now deletes only databases left by
*previous* runs - no process holds those - and downgrades a failure to delete
a stale file to a warning, because this run is unaffected by it.

The run id is read from `MS_E2E_RUN_ID` when present and written back into
`process.env` otherwise, so the uvicorn child process and every Playwright
worker inherit the same value.

**Verified (Linux only, RAN HERE).** Two consecutive runs:

```
run 1 -> e2e-phase0-mvz2mjv8-2242.sqlite3
run 2 -> run id mvz2mx8a-2323
         [global-setup] removed 1 stale database file(s)
         artifacts now contain exactly: e2e-phase0-mvz2mx8a-2323.sqlite3
```

**NOT VERIFIED ON WINDOWS.** The Windows failure described above is reasoned
from SQLite's documented file-sharing behaviour, not observed. What *was*
observed here is the start-up ordering that made the old code unsafe.

---

## BUG-0007 - The new port pre-flight failed every test (self-inflicted, caught by running)

**Phase:** 0
**Found:** 2026-11-02, immediately after adding the port check (RAN HERE).

**Symptom.** I added a "is the port already in use?" pre-flight so a leftover
server could not make the suite report PASS against old code. Placed in
`globalSetup`, it fired on every single run - because, per BUG-0006,
`webServer` has already started by then and **our own** uvicorn owns the port.

Moving it to config-load time fixed that, and then broke differently: all six
tests failed with `port 8010 on 127.0.0.1 is already in use`. Playwright
**re-loads the config file inside every worker process**, and by then the
server is up, so the check fired again in the worker.

**Fix.** The probe runs only in the main runner process, detected with
`process.env['TEST_WORKER_INDEX'] === undefined`, and only at config-load
time - before `webServer` is spawned. Node has no synchronous socket API, so
a short-lived child process performs the connect and reports through its exit
code. Any failure of the probe itself fails *open*: a diagnostic must never be
the thing that blocks the suite.

**Recorded even though it never shipped**, because it is the clearest example
in this phase of why inspection is not verification. Both faults were found by
running the suite, not by reading the diff.

**Verified (Linux only, RAN HERE).**

- Port occupied by a foreign listener -> fails in 1.8s at config load, with
  `Get-NetTCPConnection -LocalPort 8010,5174` in the message, and **no**
  server spawned.
- Port free -> config loads, server boots, `globalSetup` runs, all six tests
  are collected and attempt to execute. The only failure is
  `browserType.launch: Executable doesn't exist` - Chromium cannot be
  downloaded in this sandbox.

---

## BUG-0008 - The LICENSE named a copyright holder nobody had agreed to

**Phase:** 0
**Found:** 2026-11-02, by reading `LICENSE` against the README (RAN HERE).

**Symptom.** `README.md` said:

> Replace the placeholder copyright holder with your legal name before
> publishing the repository.

but `LICENSE` contained no placeholder. It read
`Copyright (c) 2026 MerchantShield AI contributors` - an invented holder. Two
problems: the documentation described a state the repository was not in, and
the project had asserted a copyright holder on the owner's behalf without
being told who that is.

This matters beyond tidiness: Devpost requires the licence to be detectable
and visible in the repository's About section, so the wrong holder would be
published as-is.

**Fix.** `LICENSE` now reads:

```
Copyright (c) 2026 [COPYRIGHT HOLDER - owner to confirm]
```

The placeholder is deliberately conspicuous so it cannot be published by
accident. The owner replaces it before the repository goes public; no name is
inferred or auto-filled.

---

## BUG-0009 - `resolvePython()` fell back to a Python that cannot run the backend

**Phase:** 0
**Found:** 2026-11-02, re-reading the BUG-0005 fix (RAN HERE).

**Symptom.** The BUG-0005 resolver ended with "otherwise return plain
`python` from PATH". That reintroduces the very failure BUG-0005 set out to
remove: a system interpreter without the backend dependencies produces
`No module named uvicorn`, which Playwright reports only as
`Timed out waiting 180000ms from config.webServer` - pointing the reader at
the wrong problem for the full three minutes.

**Fix.** With neither `MS_PYTHON` nor a `.venv`, `resolvePython()` now throws
immediately, naming the path it looked for and giving the exact commands to
create the virtualenv (`py -3.11 -m venv .venv` on Windows). CI is unaffected
because the workflow sets `MS_PYTHON: python` explicitly.

**Verified (Linux only, RAN HERE).** With `.venv` temporarily moved aside and
`MS_PYTHON` unset, `npx playwright test --list` fails at config load with the
instructions, in under two seconds. With `MS_PYTHON=/usr/bin/python3` it
proceeds normally and lists all 6 tests. The `.venv` was then restored and
re-checked (`Python 3.11.2`, dependencies import OK).

---

## BUG-0010 - README contradicted measurements taken in the same repository

**Found.** 2026-11-07, while moving the project to its own repository root and
re-running everything (MASTER 6 / 10.2).

**Symptom.** Four statements in `README.md` disagreed with either the code or
MASTER v4:

| Claim in README | Reality |
| --- | --- |
| "39 passing backend tests" | 86 tests exist and 86 passed (`86 passed, 1 warning in 0.74s`) |
| `cd C:\dev\merchantshield-test\merchantshield-ai` | after the restructure there is no `merchantshield-ai` folder; it is the repository root |
| road map: "8 deterministic story orders" | MASTER section 9 PHASE 1 says **15** (HANDOFF section 5 records the earlier "8-15" instruction and concludes MASTER wins) |
| `LLM_PROVIDER`: `gemini` / `anthropic` / `openai` / `none` | MASTER 10.5 CUTS every provider except `gemini` and `none` |

**Root cause.** The test count was written before 47 tests were added and never
revisited; the other three are documents drifting from the spec, which is
exactly what MASTER's "single source of truth" rule exists to catch. Nothing
here was caught by a test, because nothing tested the documents - the Phase 0
banned-phrase honesty test (MASTER 10.9) is still missing, and it would not
have caught any of these four anyway.

**Fix.** README corrected in the restructure commit, with the measured numbers
and the MASTER-mandated values. No code, test or configuration was changed to
match the documentation - the documentation was changed to match reality.
Decision recorded as D-022.

**Not fixed here (still open, tracked in HANDOFF section 5).** No
`scripts/run_demo.*`, no `scripts/test_all.*`, no `scripts/safe_commit.sh`, no
`scripts/verify_paypal_live.py`, no "Run it in 5 minutes" section, no
banned-phrase test, no `"engines": {"node": ">=24 <25"}`, one browser suite not
yet moved to `frontend/e2e`, mutation registry still Phase 0 + Phase 1 only.
Those are Sprint A work, not restructure work.

---

## BUG-0011 - `GET /api/orders/{id}` passed a dict where an assessment was expected

**Phase:** 1-7 integration
**Found:** 2026-11-09, first run of the new order-detail endpoint.

**Symptom.** `AttributeError: 'dict' object has no attribute 'as_dict'` on every
order detail request. `scan()` returns a serialized dict; `detail()` treated it
as a risk assessment object.

**Root cause.** Two functions with similar names and different return types,
written an hour apart. Nothing in the type annotations caught it because the
dict branch was typed `Any`.

**Fix.** `detail()` calls `assess()` and serializes with `.as_dict()`, and
`tests/test_orders.py::test_order_detail_includes_every_section` calls the
endpoint. This is the kind of bug a browser suite catches in ten seconds and a
type checker does not catch at all.

---

## BUG-0012 - The message-buyer diff reported "no change" after a real change

**Phase:** 2
**Found:** 2026-11-09, `test_message_buyer_creates_a_logged_message_in_the_diff`.

**Symptom.** The action executed, the message row existed, and the stored
`after` snapshot equalled `before` - so the audit trail claimed nothing had
changed.

**Root cause.** SQLAlchemy's `order.messages` relationship was loaded when the
`before` snapshot was taken. Adding a `BuyerMessage` and flushing does not
invalidate an already-loaded collection, so the `after` snapshot re-read the
stale list.

**Fix.** `session.expire(order, ["messages"])` after the flush, with a comment
saying why. The test asserts the diff, not just the row.

---

## BUG-0013 - Mock-mode failures were all classified as FAILED

**Phase:** 2
**Found:** 2026-11-09, `test_possibly_applied_failures_become_unknown[crash]`.

**Symptom.** Injecting `timeout`, `5xx`, `reset` or `crash` into the mock
produced `FAILED` instead of `UNKNOWN` - the one state that exists specifically
to prevent a duplicate external call.

**Root cause.** The facade's mock branch caught `PayPalError` and returned
FAILED, assuming "the mock never fails here". The failure-injection modes made
that assumption false, and the branch silently flattened the taxonomy.

**Fix.** Same classification as the live path: connection errors and rejections
are FAILED, everything else is UNKNOWN. Tested through the facade in
`tests/test_paypal.py::test_facade_classifies_injected_failures` and through the
API in `tests/test_actions.py`. Recorded as D-027.

---

## BUG-0014 - An approved draft still displayed as DRAFT

**Phase:** 6
**Found:** 2026-11-09, by the Playwright suite (this one was *not* visible to
the backend tests, which passed throughout).

**Symptom.** Click "Approve v2": request returns `200 {"id":2,"status":
"APPROVED","version":2}`, and the card keeps showing `DRAFT` for v2.

**Root cause.** Two independent faults stacked:

1. `POST /disputes/{id}/drafts/{draft_id}/approve` returned a *short* payload
   while `POST /disputes/{id}/drafts` returned the full draft. The frontend's
   mapper is strict (no `any`, runtime guards), so `approveDraft()` threw on the
   missing `missing_evidence` array.
2. `DisputePanel` only rendered its `error` state when the detail had failed to
   load. An error thrown *after* load was invisible, so the component looked
   like a button that did nothing.

**Fix.** One `draft_payload()` serializer used by both endpoints; the error
banner now renders whenever `error !== null`; a backend test compares the key
sets of the two responses. Recorded as D-034.

**Why this one matters.** It is the exact failure mode the project is about: the
server believed one thing, the screen said another, and no test failed. The
browser suite is what caught it.

---

## BUG-0015 - `Cache-Control` was absent, so a stale GET could win

**Phase:** 5-7
**Found:** 2026-11-09, while investigating BUG-0014 (it turned out not to be the
cause, but it is a real defect that would have produced the same symptom).

**Symptom.** A JSON `GET` could be served from the browser's heuristic cache,
showing state older than the `POST` that had just returned.

**Fix.** `cache: 'no-store'` in the API client and middleware on the server.
Recorded as D-028 as a decision, because it is a policy, not just a fix.

---

## BUG-0016 - Action diffs carried `+00:00` timestamps and microseconds

**Phase:** 2
**Found:** 2026-11-09, reading a real action payload while building the UI.

**Symptom.** `"after": {"shipped_at": "2026-11-09T18:15:18.828512+00:00"}` - a
naive-looking offset format on a project whose rule R10 requires a literal `Z`
and millisecond precision in every JSON timestamp.

**Root cause.** `_snapshot()` used `datetime.isoformat()` directly, and the
action serializer did `.isoformat().replace("+00:00", "Z")` without a timespec.

**Fix.** Both use `to_z()`. `tests/test_api_contract.py` asserts the Z suffix on
order and audit timestamps; action fields now come from the same helper.

---

## BUG-0017 - The Playwright audit-row locator matched its own child chips

**Phase:** 7 (test bug, not product bug - recorded anyway)
**Found:** 2026-11-09, `the audit log filters by event and keeps its source labels`
failing with "expected 2, received 1".

**Symptom.** The row count and the chip count disagreed, because
`[data-testid^="audit-row-"]` also matches `audit-row-source-12`.

**Fix.** Anchor the selector to the element type: `tr[data-testid^="audit-row-"]`.
Left in this document because a test that silently counts the wrong thing is how
a suite turns green and stops meaning anything.

---

## BUG-0018 - The demo-seed button claimed it had seeded 15 orders

**Phase:** 1 / 7
**Found:** 2026-11-09, in the browser suite, on a shared end-to-end database.

**Symptom.** After "Reset demo", pressing "Seed demo" reported
"Seeded 15 demo orders", but the API had answered `{"inserted": 0}` because the
database was not empty (a storefront order from an earlier test was present).

**Root cause.** The UI hardcoded the sentence; the API's seeding rule is
"only into an empty database", which is the correct rule.

**Fix.** The UI reports the number the API returned, and the browser test now
asserts `Seeded N` against the actual count of demo orders afterwards - so
"Seeded 0" is a passing, honest result.

---

## BUG-0019 - The pinned requirements did not install what the code imports

**Phase:** 7 / 7
**Found:** 2026-11-11, during the final fresh-clone verification, by reading
`backend/requirements.txt` against `backend/ml/train.py` and
`backend/app/services/risk_model.py`.

**Symptom.** `backend/requirements.txt` did not pin `numpy` or `scikit-learn`,
yet `backend/ml/train.py` imports both, the test suite trains a model
(`tests/test_ml.py`), and `app/services/risk_model.py` retrains on first boot
when `backend/ml/model/` is absent (it is gitignored, so a fresh clone always
trains). A judge following the README on a clean machine would therefore have
hit `ModuleNotFoundError: numpy` on first request, not on install.

**Root cause.** The Phase 3 model was developed in an environment where the
scientific stack was already installed, so the pin was never added. Serving
itself only needs a dot product — the omission was invisible in the running app
once the artefact existed.

**Fix.** `numpy==2.1.3` and `scikit-learn==1.5.2` are now pinned, with a comment
that serving needs neither (coefficients are exported to JSON). Verified by
building a fresh virtualenv from the file in a clean copy of the repository with
no `node_modules`, `.venv`, database or `artifacts/`, then running the full
suite there: 214 passed.

**Consequence for the judge:** `pip install -r backend/requirements.txt` is now
sufficient for the backend, for the tests, and for first-boot training.

---

## BUG-0020 - A locally-handled action was displayed as a real PayPal Sandbox response

**Phase:** 7 / 7
**Found:** 2026-11-11, while capturing screenshots for the explainer video. The
drawer showed a green `PAYPAL_SANDBOX` chip next to a `FLAG_FOR_REVIEW` action
that the audit log had just recorded as `SIMULATED`.

**Symptom.** In `frontend/src/pages/Orders.tsx` the executed-action footer read

```tsx
source={action.result['source'] === 'MOCK' ? 'MOCK' : 'PAYPAL_SANDBOX'}
```

so any result source that was not `MOCK` - including `SIMULATED`, which is what
`FLAG_FOR_REVIEW` and `MESSAGE_BUYER` store, because they are applied inside this
app and never leave it - rendered as `PAYPAL_SANDBOX` with the tooltip "Real
response from the PayPal Sandbox API (never production)". That is the single
worst mislabel this product can produce: it claims a PayPal response that never
happened, on the one screen whose entire purpose is provenance.

**Root cause.** Two things compounding. (1) The UI narrowed three labels into
two by hand, instead of rendering the stored label. (2) The API response for an
executed action carried a `source` field but no statement of whether an external
call had been made at all, so the UI had to guess - and guessed wrong.

**Why the existing suite missed it.** `frontend/e2e/orders.spec.ts` executed an
`ADD_TRACKING` action. That one *is* served by the mock adapter, so it renders
`MOCK` and took the correct branch of the ternary. No test ever executed a
locally-handled action and looked at its label.

**Fix.**
- Backend: `services/actions.execute()` now stores `"external_call": external is
  not None` in `action.result`, so the API states the fact instead of implying it.
- Frontend: `resultSource()` reads the stored label with `isSourceLabel()` and
  renders it unchanged; `ActionResultSource` shows "External call served by" only
  when an external call actually happened, "Handled locally: no external call was
  made" otherwise, and a red defect notice if an external call ever arrives with
  no readable label.
- Tests: `backend/tests/test_actions.py::test_local_action_reports_no_external_call`
  (API shape) and `frontend/e2e/zz-source-label.spec.ts` (rendered chip). The
  browser test was verified to fail against the old mapping - reintroducing it
  produces `Received string: "... External call served by PAYPAL_SANDBOX ..."`
  - so it is a guard, not decoration.

**Also fixed while here.** The new browser test originally ran against the first
seeded order and executed an action there, which changed what
`orders.spec.ts` ("the planner proposes PENDING actions") and
`walkthrough.spec.ts` ("reset demo reports what it deleted") saw, because the
suite shares one database. It now buys its own storefront order first, so no spec
depends on another's leftovers.

---

## BUG-0021 - A storefront order could be mistaken for demo data by its reference

**Phase:** 7 / 7
**Found:** 2026-11-11, as an intermittent browser-suite failure
(`walkthrough.spec.ts` → "reset demo reports what it deleted and keeps live rows",
2 failures out of 32 runs, different runs each time).

**Symptom.**

```
Error: expect(received).toHaveLength(expected)
Expected length: 0
Received length: 1
Received array: [{"order_ref": "MS-2C2D39B5", "is_demo": false, ...}]
```

**Root cause.** Seeded story orders are `MS-2001` … `MS-2015`, and storefront
orders are `MS-<uuid4().hex[:8].upper()>` (`services/store.py`). So a live
storefront order's reference can begin `MS-2` — about one run in sixteen, since
the first hex character is 2 roughly 1/16 of the time. The test decided what was
demo data with `order_ref.startsWith('MS-2')`, which is a *naming coincidence*,
not the property it meant. When a live order landed on `MS-2…` and was created
before the reset, "every demo row is gone" failed against a row that was
correctly kept.

**Why it mattered beyond the flake.** The assertion was checking the wrong
thing. The product's rule is that demo membership lives in the `is_demo` column
and is independent of `source` (MASTER 3). A test that infers demo membership
from a string prefix would keep passing after a change that broke exactly that
separation.

**Fix.** The spec now filters on `order.is_demo` — the flag the API actually
exposes and the reset endpoint actually uses — for all three assertions (count
before, gone after reset, restored after reseed). No production code changed;
the defect was in the test, which is why it is recorded here rather than
silently patched.

**Verified.** Full suite re-run after the fix: 32/32 passed. The old predicate is
unstable by construction, so a single green run is not proof; the fix removes the
dependency on a generated string entirely.

---

## Not yet reproduced / not yet investigated

Listed so they are not quietly forgotten.

| ID | Note |
| --- | --- |
| OBS-0001 | `starlette/testclient.py` emits a `DeprecationWarning` about `anyio.abc.BlockingPortal`. Third-party, pinned versions, not ours. `filterwarnings` escalates DeprecationWarnings only for `app.*`, so ours would still fail the suite. Revisit if Starlette is upgraded. |
