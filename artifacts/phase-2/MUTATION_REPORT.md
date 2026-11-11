# Mutation report - Phase 2

- Generated: `2026-11-09T18:46:26Z`
- Working-tree fingerprint (unchanged by this run): `2a2b98b6870273c4...`
- Applicable mutations: **12**
- Caught: **12** | Survived: **0** | Target missing: **0** | Not yet applicable: 4

A mutation is *caught* when deliberately breaking the behaviour makes at
least one targeted test fail. A *survived* mutation means the test suite
does not really cover that guarantee.

## Applicable mutations

| ID | Status | What was broken | Targeted tests |
| --- | --- | --- | --- |
| `M0-1` | PASS (CAUGHT) | Seeding ignores DEMO_MODE | `tests/test_seeding.py` |
| `M0-2` | PASS (CAUGHT) | Timestamps serialized naive (no Z suffix) | `tests/test_time_utc.py` |
| `M0-3` | PASS (CAUGHT) | Unknown order answers 200 with an empty object | `tests/test_orders.py` |
| `M1-1` | PASS (CAUGHT) | Demo reset deletes PAYPAL_SANDBOX rows | `tests/test_demo.py` |
| `M2-1` | PASS (CAUGHT) | Execute does not require APPROVED | `tests/test_actions.py` |
| `M2-2` | PASS (CAUGHT) | Claim is not conditional on APPROVED (double execution) | `tests/test_actions.py` |
| `M2-3` | PASS (CAUGHT) | Action allowlist removed | `tests/test_actions.py` |
| `M2-4` | PASS (CAUGHT) | Every external outcome treated as EXECUTED | `tests/test_actions.py` |
| `M2-5` | PASS (CAUGHT) | Possibly-applied failure classified as FAILED | `tests/test_actions.py`, `tests/test_paypal.py` |
| `M2-6` | PASS (CAUGHT) | HTTP 5xx classified as a rejection | `tests/test_paypal.py`, `tests/test_actions.py` |
| `M2-7` | PASS (CAUGHT) | NOT_APPLIED accepted without confirmation | `tests/test_actions.py` |
| `M2-8` | PASS (CAUGHT) | INDETERMINATE reported as NOT_APPLIED | `tests/test_actions.py` |

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

### `M1-1` - Demo reset deletes PAYPAL_SANDBOX rows

- **Status:** CAUGHT
- **Protects:** Section 6: reset deletes only is_demo=true AND source != PAYPAL_SANDBOX. Erasing a real sandbox order would destroy the merchant's audit trail.
- **Mutated file:** `backend/app/db/seed.py`
- **Detail:** pytest exited 1
- **Tests that failed as required:**

  - `FAILED tests/test_demo.py::test_reset_deletes_demo_rows_and_keeps_a_live_order`

### `M2-1` - Execute does not require APPROVED

- **Status:** CAUGHT
- **Protects:** Section 4.4: no external call happens without explicit merchant approval.
- **Mutated file:** `backend/app/services/actions.py`
- **Detail:** pytest exited 1
- **Tests that failed as required:**

  - `FAILED tests/test_actions.py::test_execute_before_approval_is_409 - Assertion...`

### `M2-2` - Claim is not conditional on APPROVED (double execution)

- **Status:** CAUGHT
- **Protects:** Section 4.4: the claim is a single conditional UPDATE, so eight concurrent callers produce exactly one claim and one external call.
- **Mutated file:** `backend/app/services/actions.py`
- **Detail:** pytest exited 1
- **Tests that failed as required:**

  - `FAILED tests/test_actions.py::test_claim_is_conditional_on_approved - Asserti...`

### `M2-3` - Action allowlist removed

- **Status:** CAUGHT
- **Protects:** Section 4.3: only add_tracking, message_buyer and flag_for_review exist.
- **Mutated file:** `backend/app/services/actions.py`
- **Detail:** pytest exited 1
- **Tests that failed as required:**

  - `FAILED tests/test_actions.py::test_propose_rejects_types_outside_the_allowlist`

### `M2-4` - Every external outcome treated as EXECUTED

- **Status:** CAUGHT
- **Protects:** Section 4.4: EXECUTED means the external call was confirmed to have succeeded. A FAILED or UNKNOWN outcome recorded as success is exactly how a merchant ends up believing a tracking number is attached.
- **Mutated file:** `backend/app/services/actions.py`
- **Detail:** pytest exited 1
- **Tests that failed as required:**

  - `FAILED tests/test_actions.py::test_known_failures_become_failed[4xx] - Assert...`
  - `FAILED tests/test_actions.py::test_known_failures_become_failed[connect] - As...`
  - `FAILED tests/test_actions.py::test_possibly_applied_failures_become_unknown[timeout]`
  - `FAILED tests/test_actions.py::test_possibly_applied_failures_become_unknown[5xx]`
  - `FAILED tests/test_actions.py::test_possibly_applied_failures_become_unknown[reset]`
  - `FAILED tests/test_actions.py::test_possibly_applied_failures_become_unknown[crash]`
  - `FAILED tests/test_actions.py::test_retry_reuses_the_same_idempotency_key - as...`
  - `FAILED tests/test_actions.py::test_retry_from_unknown_is_409 - AssertionError...`
  - `FAILED tests/test_actions.py::test_reconcile_applied_marks_executed_with_read_back_evidence`
  - `FAILED tests/test_actions.py::test_reconcile_not_applied_requires_confirmation`
  - `FAILED tests/test_actions.py::test_reconcile_read_error_is_indeterminate - as...`

### `M2-5` - Possibly-applied failure classified as FAILED

- **Status:** CAUGHT
- **Protects:** Section 4.4: a timeout is UNKNOWN, not FAILED. Calling it FAILED invites a retry that creates a duplicate tracking number.
- **Mutated file:** `backend/app/services/paypal_service.py`
- **Detail:** pytest exited 1
- **Tests that failed as required:**

  - `FAILED tests/test_actions.py::test_possibly_applied_failures_become_unknown[timeout]`
  - `FAILED tests/test_actions.py::test_possibly_applied_failures_become_unknown[5xx]`
  - `FAILED tests/test_actions.py::test_possibly_applied_failures_become_unknown[reset]`
  - `FAILED tests/test_actions.py::test_possibly_applied_failures_become_unknown[crash]`
  - `FAILED tests/test_actions.py::test_retry_from_unknown_is_409 - assert 200 == 409`
  - `FAILED tests/test_actions.py::test_reconcile_applied_marks_executed_with_read_back_evidence`
  - `FAILED tests/test_actions.py::test_reconcile_not_applied_requires_confirmation`
  - `FAILED tests/test_actions.py::test_reconcile_read_error_is_indeterminate - as...`
  - `FAILED tests/test_paypal.py::test_facade_classifies_injected_failures - Asser...`

### `M2-6` - HTTP 5xx classified as a rejection

- **Status:** CAUGHT
- **Protects:** Section 5: 5xx may have been applied server-side, so it is UNKNOWN.
- **Mutated file:** `backend/app/services/paypal_client.py`
- **Detail:** pytest exited 1
- **Tests that failed as required:**

  - `FAILED tests/test_paypal.py::test_5xx_is_an_unknown_outcome_never_a_retry - a...`

### `M2-7` - NOT_APPLIED accepted without confirmation

- **Status:** CAUGHT
- **Protects:** Section 4.4: NOT_APPLIED re-arms the action for retry, so it needs confirm_not_applied=true from a human who checked PayPal.
- **Mutated file:** `backend/app/services/actions.py`
- **Detail:** pytest exited 1
- **Tests that failed as required:**

  - `FAILED tests/test_actions.py::test_reconcile_not_applied_requires_confirmation`

### `M2-8` - INDETERMINATE reported as NOT_APPLIED

- **Status:** CAUGHT
- **Protects:** Section 4.4: when the read-back fails the app must say INDETERMINATE and leave the action UNKNOWN, not guess.
- **Mutated file:** `backend/app/services/actions.py`
- **Detail:** pytest exited 1
- **Tests that failed as required:**

  - `FAILED tests/test_actions.py::test_reconcile_read_error_is_indeterminate - As...`

## Not yet applicable

| ID | Phase | What it will break |
| --- | --- | --- |
| `M5-1` | 5 | Access token and client secret written to the log |
| `M5-2` | 5 | Token cache never considers the 60 s safety margin |
| `M6-1` | 6 | Hallucination guard disabled |
| `M6-2` | 6 | The agent can approve its own proposal |
