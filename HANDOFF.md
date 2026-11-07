# MerchantShield AI — handoff

**Written:** 2026-11-07 · **Phase:** 0 (not closed) · **Deadline:** Nov 12 2026 12:00 PT = Nov 13 01:30 IST

This file describes exactly where the project stands. Nothing in it is a
claim that something works unless it says RAN HERE.

---

## 1. What is in this bundle

```
merchantshield-handoff/
├── MASTER.md              the v4 spec, sections 1-10. Single source of truth.
├── HANDOFF.md             this file
└── merchantshield-ai/     the Phase 0 project, 66 files
```

`MASTER.md` is the same file committed at `docs/MASTER.md` in the old
repository (commit `c0a1a57`).

---

## 2. Where the code lived before this bundle

The old repository was `ShoryaPratapSinghChandrawat/qff2026-phase1-s1-isling_chain`,
which is an **unrelated QFF2026 simulation project**. MerchantShield was built
in a self-contained subfolder, `merchantshield-ai/`, and was **never committed**
— it existed only as untracked working-tree files.

Consequences that matter for the new repository:

- There is **no Phase 0 commit and no `phase-0` tag** anywhere.
- `.github/workflows/ci.yml` lives at `merchantshield-ai/.github/workflows/ci.yml`.
  GitHub only reads workflows from the **repository root**, so CI has never
  triggered. In the new repo, `merchantshield-ai/` should become the root, or
  the workflow must move to the root.
- `git archive HEAD` would have produced an empty handoff, because it only
  includes tracked files.

**Action for the new repo:** make the contents of `merchantshield-ai/` the
repository root, put `MASTER.md` at `docs/MASTER.md`, then commit and tag.

---

## 3. State of Phase 0

### Verified in the Linux sandbox (RAN HERE)

| Check | Result |
| --- | --- |
| Backend tests | **86 passed** |
| `tsc --noEmit` (strict) | pass |
| `vite build` | pass, no warnings |
| Mutation check `--phase 0` | 3/3 caught, M1-1 correctly deferred, tree fingerprint unchanged |
| HTTP smoke vs real uvicorn + built bundle | pass |
| Production-hostname refusal | 14-URL matrix, 0 mismatches; real uvicorn boot exits 3 |
| `.env` loading from two working directories | pass |
| Shell env overrides `.env` | pass |
| Clean-checkout dependency install at pinned versions | pass |
| Playwright harness up to browser launch | pass (config, port pre-flight, webServer, globalSetup, collection) |
| Release packaging | 66 files, 22 required present, secret scan clean |

Test file breakdown (86): `test_config_guard` 19, `test_sqlite_url` 19,
`test_mutation_check_tooling` 16, `test_env_file` 7, `test_harness_guards` 7,
`test_time_utc` 6, `test_seeding` 4, `test_db_bootstrap` 3, `test_orders` 3,
`test_health` 2.

### NOT RUN / NOT VERIFIED

- **Playwright in a real browser.** Chromium cannot be downloaded in the
  sandbox (`cdn.playwright.dev` unreachable, ECONNRESET). No system browser.
  So: no screenshots, no console logs, and the failure-path log capture is
  unverified.
- **`scripts/windows_check.ps1`** — 329 lines, never executed *or parsed*;
  there is no PowerShell in the sandbox. Review before trusting.
- **Anything on Windows 11.**
- **GitHub Actions CI** — never pushed, never triggered.
- **Any PayPal API call** — no credentials; Phase 0 is mock-only.

Per MASTER §10.3 the phase should be committed and tagged
**`phase-0-browser-unverified`**, not `phase-0`.

---

## 4. Bugs found and fixed (full write-ups in `BUGS_FIXED.md`)

| ID | Summary |
| --- | --- |
| BUG-0001 | SQLite would not create a DB in a missing directory |
| BUG-0002 | An unverified ordering claim written into a code comment |
| BUG-0003 | Secret scanner false positive: `\s*` matched a newline |
| BUG-0004 | README told you to create a `.env` the app silently ignored |
| BUG-0005 | `npm test` broke without an activated venv |
| BUG-0006 | The suite deleted a SQLite file the backend had open. Playwright starts `webServer` **before** `globalSetup`. Silent on Linux, would abort the run on Windows. Fixed with per-run DB filenames |
| BUG-0007 | The new port pre-flight failed every test — Playwright re-loads the config inside each worker. Self-inflicted, caught by running |
| BUG-0008 | `LICENSE` named an invented copyright holder; now `[COPYRIGHT HOLDER - owner to confirm]` |
| BUG-0009 | `resolvePython()` fell back to a system Python lacking dependencies |

Decisions D-001…D-018 are in `DECISIONS.md`.

---

## 5. Known gaps against MASTER v4

These are spec requirements that Phase 0 does **not** yet meet. They are not
defects in what exists; they are work not started.

| MASTER ref | Requirement | Status |
| --- | --- | --- |
| §10.3 | ONE browser suite at `frontend/e2e` | suite is at `frontend/tests/` — must be moved/renamed |
| §10.4 | `scripts/run_demo.ps1` / `.sh` | do not exist |
| §10.4 | `scripts/test_all.ps1` / `.sh` | do not exist |
| §10.4 | README "Run it in 5 minutes" using those scripts | README has a longer Windows quick start instead |
| §6 | `scripts/safe_commit.sh` | does not exist |
| §10.7 | `scripts/verify_paypal_live.py` | does not exist |
| §10.9 | Banned-phrase honesty test | does not exist |
| §4.1 | `"engines": {"node": ">=24 <25"}` in package.json | not set |
| §9 Phase 0 | 1 Playwright test | 3 tests × 2 viewports exist (exceeds) |
| §7 | Phase 2/5/6 mutations | registry lists Phase 0 + Phase 1 only |

Also note §9 Phase 1 says **15** story orders; an earlier instruction said
"8–15, start with 8". MASTER wins: 15.

---

## 6. Environment facts

- Sandbox: Debian 12, Python **3.11.2**, Node **v22.22.3** (not 24), npm 10.9.8.
- `.nvmrc` and CI say Node 24. The version difference is real and unverified.
- `.venv/`, `frontend/node_modules/`, `frontend/dist/`, `artifacts/` do **not**
  survive between sessions. Recreate with:
  - `python3.11 -m venv .venv` then `.venv/bin/python -m pip install -r backend/requirements.txt`
  - `cd frontend && npm install`
- Ports: **8010** Playwright e2e server, **5174** Vite dev, **8000** manual run.
  All bound to `127.0.0.1`.

Commands that work (from the project root):

```bash
cd backend && env -u MS_ENV_FILE ../.venv/bin/python -m pytest -q
.venv/bin/python scripts/mutation_check.py --phase 0
.venv/bin/python scripts/package_release.py --phase 0 --outdir ..
cd frontend && npm install && npx tsc --noEmit && npx vite build
```

---

## 7. Next step

Per MASTER §10.2, the next instruction is **"Run SPRINT A"** = close Phase 0,
then Phase 1, then Phase 2.

Before that, in the new repository:

1. Make `merchantshield-ai/`'s contents the repo root.
2. Move `.github/workflows/ci.yml` to the root so CI can actually trigger.
3. Put `MASTER.md` at `docs/MASTER.md`.
4. Commit Phase 0 and tag it `phase-0-browser-unverified`.

---

## 8. Addendum - 2026-11-07, new repository (`MerchantShield-AI`)

Written after the work in sections 1-7 was done, so the state above is history,
not the current state. Everything in this addendum is RAN HERE unless it says
otherwise.

**What changed.** The 66 files of `merchantshield-ai/` are now the root of
`ShoryaPratapSinghChandrawat/MerchantShield-AI` on branch
`arena/6b2fe94a-merchantshield-ai`. `MASTER.md` is at `docs/MASTER.md`,
`HANDOFF.md` is here, and `.github/workflows/ci.yml` is at the repository root
where GitHub actually reads it. The workflow's paths were already relative to
the project root, so no path inside it needed changing - every one of them was
checked against the filesystem after the move.

**Re-run from scratch in the new layout** (fresh `.venv`, fresh
`node_modules`), replacing the numbers in section 3 rather than repeating them:

| Check | This run |
| --- | --- |
| Backend tests | 86 passed, 1 third-party warning |
| `tsc --noEmit` | exit 0 |
| `vite build` | exit 0, no warnings |
| Mutation check `--phase 0` | 3/3 caught, M1-1 not yet applicable, working tree unchanged |
| HTTP smoke (`/api/health`, `/api/orders/1`, 404s, `/`) | pass |
| **Playwright browser tests** | **6/6 pass at 1500x900 and 390x844 in a real headless Chromium** |

**The browser caveat, stated plainly.** The pinned Playwright Chromium 156 could
not be downloaded (`cdn.playwright.dev` ECONNRESET) and no system browser
exists. The suite was therefore run against Chromium 153 from the
`@sparticuz/chromium` npm package plus its bundled AL2023 libraries, through a
local config that only sets `launchOptions.executablePath`. That file was
deleted after the run. See `DECISIONS.md` D-021 for the three attempts and the
exact reproduction steps.

**Still NOT RUN:** the pinned browser build, GitHub Actions, anything on
Windows 11, `scripts/windows_check.ps1`, any PayPal call, and the MASTER 10.4 /
10.9 / 4.1 requirements listed in section 5 above - those are Sprint A work.
