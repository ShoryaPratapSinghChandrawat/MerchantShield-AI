# Mutation report - Phase 0

- Generated: `2026-11-09T18:40:08Z`
- Working-tree fingerprint (unchanged by this run): `542971de5f09428a...`
- Applicable mutations: **3**
- Caught: **3** | Survived: **0** | Target missing: **0** | Not yet applicable: 13

A mutation is *caught* when deliberately breaking the behaviour makes at
least one targeted test fail. A *survived* mutation means the test suite
does not really cover that guarantee.

## Applicable mutations

| ID | Status | What was broken | Targeted tests |
| --- | --- | --- | --- |
| `M0-1` | PASS (CAUGHT) | Seeding ignores DEMO_MODE | `tests/test_seeding.py` |
| `M0-2` | PASS (CAUGHT) | Timestamps serialized naive (no Z suffix) | `tests/test_time_utc.py` |
| `M0-3` | PASS (CAUGHT) | Unknown order answers 200 with an empty object | `tests/test_orders.py` |

## Detail

### `M0-1` - Seeding ignores DEMO_MODE

- **Status:** CAUGHT
- **Protects:** Section 6: seeding runs only when DEMO_MODE=true. A deployment without DEMO_MODE must never invent demo orders.
- **Mutated file:** `backend/app/db/seed.py`
- **Detail:** pytest exited 1
- **Tests that failed as required:**

  - `FAILED tests/test_seeding.py::test_demo_mode_false_seeds_nothing - AssertionE...`
  - `FAILED tests/test_seeding.py::test_demo_mode_unset_is_treated_as_false - Asse...`

### `M0-2` - Timestamps serialized naive (no Z suffix)

- **Status:** CAUGHT
- **Protects:** Rule R10: API JSON timestamps are UTC with a literal Z. An ambiguous timestamp in a dispute evidence packet is worse than none, because it looks authoritative while being wrong.
- **Mutated file:** `backend/app/core/timeutil.py`
- **Detail:** pytest exited 1
- **Tests that failed as required:**

  - `FAILED tests/test_time_utc.py::test_to_z_formats_aware_utc_with_z_suffix - As...`
  - `FAILED tests/test_time_utc.py::test_to_z_converts_a_non_utc_offset_to_utc - A...`
  - `FAILED tests/test_time_utc.py::test_to_z_treats_naive_input_as_utc - Assertio...`
  - `FAILED tests/test_time_utc.py::test_health_server_time_ends_with_z - Assertio...`
  - `FAILED tests/test_time_utc.py::test_order_timestamps_end_with_z - AssertionEr...`

### `M0-3` - Unknown order answers 200 with an empty object

- **Status:** CAUGHT
- **Protects:** Section 6: an unknown order is a 404, never an empty success.
- **Mutated file:** `backend/app/api/orders.py`
- **Detail:** pytest exited 1
- **Tests that failed as required:**

  - `FAILED tests/test_orders.py::test_unknown_order_returns_404 - AttributeError:...`

## Not yet applicable

| ID | Phase | What it will break |
| --- | --- | --- |
| `M1-1` | 1 | Demo reset deletes PAYPAL_SANDBOX rows |
| `M2-1` | 2 | Execute does not require APPROVED |
| `M2-2` | 2 | Claim is not conditional on APPROVED (double execution) |
| `M2-3` | 2 | Action allowlist removed |
| `M2-4` | 2 | Status set to EXECUTED before the external call |
| `M2-5` | 2 | Possibly-applied failure classified as FAILED |
| `M2-6` | 2 | HTTP 5xx classified as a rejection |
| `M2-7` | 2 | NOT_APPLIED accepted without confirmation |
| `M2-8` | 2 | INDETERMINATE reported as NOT_APPLIED |
| `M5-1` | 5 | Access token and client secret written to the log |
| `M5-2` | 5 | Token cache never considers the 60 s safety margin |
| `M6-1` | 6 | Hallucination guard disabled |
| `M6-2` | 6 | The agent can approve its own proposal |
