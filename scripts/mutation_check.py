#!/usr/bin/env python3
"""Phase-aware mutation checker for MerchantShield AI.

The question this answers is "do the tests actually bite?". A green test suite
proves nothing if deleting a safety check still leaves it green. So for each
mutation we deliberately break one guarantee and require at least one targeted
test to fail.

Guarantees of this script (section 9):

* It **copies** the repository to a temporary folder and mutates only the copy.
  The working tree is checksummed before and after and the run fails if a
  single byte changed.
* A mutation whose target text is missing is a **hard failure**, not a skip -
  otherwise a refactor could silently disarm the whole check.
* A mutation that every targeted test survives is a **hard failure**.
* Mutations belonging to a future phase are reported as NOT YET APPLICABLE
  rather than quietly dropped.
* The report is written to ``artifacts/phase-<N>/MUTATION_REPORT.md``.

Usage (Windows PowerShell):
    python scripts\\mutation_check.py --phase 0
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR_NAME = "backend"

#: Directories never copied into the mutation sandbox.
EXCLUDED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "build",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "artifacts",
    "htmlcov",
}


@dataclass(frozen=True)
class Mutation:
    """One deliberate break, plus the tests that must notice it."""

    id: str
    phase: int
    title: str
    protects: str
    relative_path: str
    find: str
    replace: str
    tests: tuple[str, ...]


@dataclass
class MutationResult:
    mutation: Mutation
    status: str  # CAUGHT | SURVIVED | TARGET_MISSING | NOT_YET_APPLICABLE
    detail: str = ""
    failing_tests: list[str] = field(default_factory=list)
    returncode: int | None = None


# ---------------------------------------------------------------------------
# The mutation catalogue. Phases beyond the current one are listed here as soon
# as the prompt specifies them, so the report can show what is still pending.
# ---------------------------------------------------------------------------

MUTATIONS: tuple[Mutation, ...] = (
    # ------------------------------------------------------------- phase 0
    Mutation(
        id="M0-1",
        phase=0,
        title="Seeding ignores DEMO_MODE",
        protects=(
            "Section 6: seeding runs only when DEMO_MODE=true. A deployment "
            "without DEMO_MODE must never invent demo orders."
        ),
        relative_path="backend/app/db/seed.py",
        find="    if not settings.demo_mode:\n"
        '        logger.info("DEMO_MODE is false - skipping seeding.")\n'
        "        return 0",
        replace="    if False:  # MUTANT M0-1: DEMO_MODE gate removed\n"
        '        logger.info("DEMO_MODE is false - skipping seeding.")\n'
        "        return 0",
        tests=("tests/test_seeding.py",),
    ),
    Mutation(
        id="M0-2",
        phase=0,
        title="Timestamps serialized naive (no Z suffix)",
        protects=(
            "Rule R10: API JSON timestamps are UTC with a literal Z. An "
            "ambiguous timestamp in a dispute evidence packet is worse than "
            "none, because it looks authoritative while being wrong."
        ),
        relative_path="backend/app/core/timeutil.py",
        find='    aware = ensure_utc(dt)\n    return aware.isoformat(timespec="milliseconds").replace("+00:00", "Z")',
        replace="    # MUTANT M0-2: drop UTC normalisation and the Z suffix\n"
        '    return dt.isoformat(timespec="milliseconds")',
        tests=("tests/test_time_utc.py",),
    ),
    Mutation(
        id="M0-3",
        phase=0,
        title="Unknown order answers 200 with an empty object",
        protects="Section 6: an unknown order is a 404, never an empty success.",
        relative_path="backend/app/api/orders.py",
        find="    if order is None:\n"
        "        raise HTTPException(\n"
        "            status_code=status.HTTP_404_NOT_FOUND, detail=f\"Order {order_id} not found.\"\n"
        "        )\n"
        "    return order",
        replace="    if order is None:  # MUTANT M0-3: 404 replaced by an empty 200\n"
        "        return {}\n"
        "    return order",
        tests=("tests/test_orders.py",),
    ),
    # ------------------------------------------------------------- phase 1
    Mutation(
        id="M1-1",
        phase=1,
        title="Demo reset deletes PAYPAL_SANDBOX rows",
        protects=(
            "Section 6: reset deletes only is_demo=true AND source != PAYPAL_SANDBOX. "
            "Erasing a real sandbox order would destroy the merchant's audit trail."
        ),
        relative_path="backend/app/db/seed.py",
        find="    return (Order.is_demo.is_(True), Order.source != SourceLabel.PAYPAL_SANDBOX.value)",
        replace="    # MUTANT M1-1: the LIVE guard is gone, so Sandbox rows become deletable\n"
        "    return (Order.is_demo.is_(True),)",
        tests=("tests/test_demo.py",),
    ),
    # ------------------------------------------------------------- phase 2
    Mutation(
        id="M2-1",
        phase=2,
        title="Execute does not require APPROVED",
        protects="Section 4.4: no external call happens without explicit merchant approval.",
        relative_path="backend/app/services/actions.py",
        find='    if action.status != ActionStatus.APPROVED.value:\n'
        '        raise ActionConflict(f"Execute requires APPROVED; action is {action.status}.")',
        replace="    # MUTANT M2-1: the APPROVED precondition is gone\n"
        "    if False:\n"
        '        raise ActionConflict(f"Execute requires APPROVED; action is {action.status}.")',
        tests=("tests/test_actions.py",),
    ),
    Mutation(
        id="M2-2",
        phase=2,
        title="Claim is not conditional on APPROVED (double execution)",
        protects=(
            "Section 4.4: the claim is a single conditional UPDATE, so eight "
            "concurrent callers produce exactly one claim and one external call."
        ),
        relative_path="backend/app/services/actions.py",
        find=".where(Action.id == action_id, Action.status == ActionStatus.APPROVED.value)",
        replace=".where(Action.id == action_id)  # MUTANT M2-2: claim no longer conditional",
        tests=("tests/test_actions.py",),
    ),
    Mutation(
        id="M2-3",
        phase=2,
        title="Action allowlist removed",
        protects="Section 4.3: only add_tracking, message_buyer and flag_for_review exist.",
        relative_path="backend/app/services/actions.py",
        find="    if action_type not in ACTION_ALLOWLIST:",
        replace="    if False:  # MUTANT M2-3: allowlist removed",
        tests=("tests/test_actions.py",),
    ),
    Mutation(
        id="M2-4",
        phase=2,
        title="Every external outcome treated as EXECUTED",
        protects=(
            "Section 4.4: EXECUTED means the external call was confirmed to have "
            "succeeded. A FAILED or UNKNOWN outcome recorded as success is exactly "
            "how a merchant ends up believing a tracking number is attached."
        ),
        relative_path="backend/app/services/actions.py",
        find='    if external is not None and external.outcome != "EXECUTED":',
        replace="    if False:  # MUTANT M2-4: every external outcome treated as success",
        tests=("tests/test_actions.py",),
    ),
    Mutation(
        id="M2-5",
        phase=2,
        title="Possibly-applied failure classified as FAILED",
        protects=(
            "Section 4.4: a timeout is UNKNOWN, not FAILED. Calling it FAILED "
            "invites a retry that creates a duplicate tracking number."
        ),
        relative_path="backend/app/services/paypal_service.py",
        find="                return CallResult(\n"
        '                    outcome="UNKNOWN", source="MOCK", detail={}, error=_sanitize(str(exc))\n'
        "                )",
        replace="                return CallResult(  # MUTANT M2-5: UNKNOWN -> FAILED\n"
        '                    outcome="FAILED", source="MOCK", detail={}, error=_sanitize(str(exc))\n'
        "                )",
        tests=("tests/test_actions.py", "tests/test_paypal.py"),
    ),
    Mutation(
        id="M2-6",
        phase=2,
        title="HTTP 5xx classified as a rejection",
        protects="Section 5: 5xx may have been applied server-side, so it is UNKNOWN.",
        relative_path="backend/app/services/paypal_client.py",
        find='        if response.status_code >= 500:\n            raise PayPalUnknownOutcome(f"{method} {path}: PayPal {response.status_code}")',
        replace="        if response.status_code >= 500:  # MUTANT M2-6: 5xx treated as a rejection\n"
        '            raise PayPalRequestRejected(f"{method} {path}: PayPal {response.status_code}", response.status_code, "")',
        tests=("tests/test_paypal.py", "tests/test_actions.py"),
    ),
    Mutation(
        id="M2-7",
        phase=2,
        title="NOT_APPLIED accepted without confirmation",
        protects=(
            "Section 4.4: NOT_APPLIED re-arms the action for retry, so it needs "
            "confirm_not_applied=true from a human who checked PayPal."
        ),
        relative_path="backend/app/services/actions.py",
        find="        if not confirm_not_applied:",
        replace="        if False:  # MUTANT M2-7: confirmation no longer required",
        tests=("tests/test_actions.py",),
    ),
    Mutation(
        id="M2-8",
        phase=2,
        title="INDETERMINATE reported as NOT_APPLIED",
        protects=(
            "Section 4.4: when the read-back fails the app must say INDETERMINATE "
            "and leave the action UNKNOWN, not guess."
        ),
        relative_path="backend/app/services/actions.py",
        find='    return {"outcome": "INDETERMINATE", "action_status": action.status}',
        replace='    return {"outcome": "NOT_APPLIED", "action_status": action.status}  # MUTANT M2-8',
        tests=("tests/test_actions.py",),
    ),
    # ------------------------------------------------------------- phase 5
    Mutation(
        id="M5-1",
        phase=5,
        title="Access token and client secret written to the log",
        protects="Section 5: credentials never appear in logs, errors or API responses.",
        relative_path="backend/app/services/paypal_client.py",
        find='        token = body.get("access_token")',
        replace='        logger.info("MUTANT M5-1 token=%s secret=%s", body.get("access_token"), self._client_secret)\n'
        '        token = body.get("access_token")',
        tests=("tests/test_paypal.py",),
    ),
    Mutation(
        id="M5-2",
        phase=5,
        title="Token cache never considers the 60 s safety margin",
        protects=(
            "Section 5: a token that expires mid-request turns a clean 4xx into "
            "an ambiguous failure, so anything inside the margin is refetched."
        ),
        relative_path="backend/app/services/paypal_client.py",
        find="        if self._token and self._token_expires_at and now < self._token_expires_at:",
        replace="        if self._token:  # MUTANT M5-2: expiry ignored",
        tests=("tests/test_paypal.py",),
    ),
    # ------------------------------------------------------------- phase 6
    Mutation(
        id="M6-1",
        phase=6,
        title="Hallucination guard disabled",
        protects=(
            "Section 6: a draft may not contain a fact that was not in the "
            "evidence packet handed to the model."
        ),
        relative_path="backend/app/services/llm.py",
        find='    guard_ok, invented = hallucination_guard(str(parsed.get("body", "")), allowed)',
        replace="    guard_ok, invented = True, []  # MUTANT M6-1: guard disabled",
        tests=("tests/test_llm.py",),
    ),
    Mutation(
        id="M6-2",
        phase=6,
        title="The agent can approve its own proposal",
        protects="Section 8: the agent plans, the human approves, the engine executes.",
        relative_path="backend/app/services/orders.py",
        find='        created.append({**action_service.as_dict(action), "created": was_created})',
        replace="        action_service.approve(session, action)  # MUTANT M6-2\n"
        '        created.append({**action_service.as_dict(action), "created": was_created})',
        tests=("tests/test_actions.py",),
    ),
)


# ---------------------------------------------------------------------------


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _ignore(_dir: str, names: list[str]) -> set[str]:
    """Names not copied into the mutation sandbox.

    Real ``.env`` files are excluded deliberately: there is no reason to copy a
    developer's credentials into a temp directory, and the test suite is
    hermetic with respect to dotenv anyway (see ``_isolate_env_file``).
    """
    skipped: set[str] = set()
    for name in names:
        if name in EXCLUDED_DIRS or name.endswith(".pyc"):
            skipped.add(name)
        elif name == ".env" or (name.startswith(".env.") and name != ".env.example"):
            skipped.add(name)
    return skipped


def read_source(path: Path) -> str:
    """Read a source file with line endings normalised to ``\n``.

    ``Path.read_text`` already applies universal-newline translation, so a
    CRLF checkout matches an LF ``find`` pattern. The explicit normalisation
    here states that dependency instead of relying on it silently, and keeps
    the function correct if it is ever switched to ``read_bytes``.
    """
    return path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")


def write_source(path: Path, text: str) -> None:
    """Write a source file with LF endings on every platform.

    Without ``newline="\n"`` Python rewrites every ``\n`` as ``\r\n`` on
    Windows, so restoring a file would silently change its bytes and the
    mutated copy would differ from the original in a way nobody asked for.
    ``.gitattributes`` pins these files to LF; this keeps the tool agreeing
    with it.
    """
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def fingerprint_tree(root: Path) -> str:
    """Stable hash of every tracked source file, used to prove non-mutation."""
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        if any(part in EXCLUDED_DIRS for part in path.relative_to(root).parts):
            continue
        digest.update(str(path.relative_to(root)).replace("\\", "/").encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def run_pytest(sandbox: Path, tests: tuple[str, ...]) -> subprocess.CompletedProcess[str]:
    backend = sandbox / BACKEND_DIR_NAME
    command = [sys.executable, "-m", "pytest", *tests, "-c", "pytest.ini", "-q", "--no-header"]
    return subprocess.run(
        command,
        cwd=backend,
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )


def extract_failures(output: str) -> list[str]:
    return [
        line.strip()
        for line in output.splitlines()
        if line.startswith("FAILED") or line.startswith("ERROR")
    ]


def apply_mutation(sandbox: Path, mutation: Mutation) -> tuple[bool, str, str]:
    """Write the mutated file. Returns (ok, original_text, message)."""
    target = sandbox / mutation.relative_path
    if not target.is_file():
        return False, "", f"target file does not exist: {mutation.relative_path}"

    original = read_source(target)
    occurrences = original.count(mutation.find)
    if occurrences == 0:
        return False, original, (
            f"target text not found in {mutation.relative_path}. "
            "The code was refactored but the mutation was not updated - "
            "this check is therefore no longer proving anything."
        )
    if occurrences > 1:
        return False, original, (
            f"target text appears {occurrences} times in {mutation.relative_path}; "
            "it must be unique so the mutation is unambiguous."
        )

    write_source(target, original.replace(mutation.find, mutation.replace))
    return True, original, ""


def check_mutation(sandbox: Path, mutation: Mutation, phase: int) -> MutationResult:
    if mutation.phase > phase:
        return MutationResult(
            mutation=mutation,
            status="NOT_YET_APPLICABLE",
            detail=f"introduced in phase {mutation.phase}; current phase is {phase}",
        )

    ok, original, message = apply_mutation(sandbox, mutation)
    if not ok:
        return MutationResult(mutation=mutation, status="TARGET_MISSING", detail=message)

    target = sandbox / mutation.relative_path
    try:
        proc = run_pytest(sandbox, mutation.tests)
    finally:
        write_source(target, original)  # always restore the sandbox

    failures = extract_failures(proc.stdout + proc.stderr)
    if proc.returncode != 0:
        return MutationResult(
            mutation=mutation,
            status="CAUGHT",
            detail=f"pytest exited {proc.returncode}",
            failing_tests=failures,
            returncode=proc.returncode,
        )

    return MutationResult(
        mutation=mutation,
        status="SURVIVED",
        detail=(
            "every targeted test still passed with the guarantee removed - "
            "the tests do not actually cover this behaviour"
        ),
        returncode=proc.returncode,
    )


def build_report(phase: int, results: list[MutationResult], tree_hash: str) -> str:
    caught = [r for r in results if r.status == "CAUGHT"]
    survived = [r for r in results if r.status == "SURVIVED"]
    missing = [r for r in results if r.status == "TARGET_MISSING"]
    pending = [r for r in results if r.status == "NOT_YET_APPLICABLE"]

    lines: list[str] = [
        f"# Mutation report - Phase {phase}",
        "",
        f"- Generated: `{iso_now()}`",
        f"- Working-tree fingerprint (unchanged by this run): `{tree_hash[:16]}...`",
        f"- Applicable mutations: **{len(caught) + len(survived) + len(missing)}**",
        f"- Caught: **{len(caught)}** | Survived: **{len(survived)}** | "
        f"Target missing: **{len(missing)}** | Not yet applicable: {len(pending)}",
        "",
        "A mutation is *caught* when deliberately breaking the behaviour makes at",
        "least one targeted test fail. A *survived* mutation means the test suite",
        "does not really cover that guarantee.",
        "",
        "## Applicable mutations",
        "",
        "| ID | Status | What was broken | Targeted tests |",
        "| --- | --- | --- | --- |",
    ]

    for result in results:
        if result.status == "NOT_YET_APPLICABLE":
            continue
        icon = {"CAUGHT": "PASS", "SURVIVED": "FAIL", "TARGET_MISSING": "FAIL"}[result.status]
        tests = ", ".join(f"`{t}`" for t in result.mutation.tests)
        lines.append(
            f"| `{result.mutation.id}` | {icon} ({result.status}) | "
            f"{result.mutation.title} | {tests} |"
        )

    lines += ["", "## Detail", ""]
    for result in results:
        if result.status == "NOT_YET_APPLICABLE":
            continue
        lines += [
            f"### `{result.mutation.id}` - {result.mutation.title}",
            "",
            f"- **Status:** {result.status}",
            f"- **Protects:** {result.mutation.protects}",
            f"- **Mutated file:** `{result.mutation.relative_path}`",
            f"- **Detail:** {result.detail}",
        ]
        if result.failing_tests:
            lines += ["- **Tests that failed as required:**", ""]
            lines += [f"  - `{line}`" for line in result.failing_tests]
        lines.append("")

    if pending:
        lines += ["## Not yet applicable", "", "| ID | Phase | What it will break |", "| --- | --- | --- |"]
        for result in pending:
            lines.append(
                f"| `{result.mutation.id}` | {result.mutation.phase} | {result.mutation.title} |"
            )
        lines.append("")

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run MerchantShield AI mutation checks.")
    parser.add_argument("--phase", type=int, required=True, help="current phase number")
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=None,
        help="override the artifacts/phase-N directory",
    )
    args = parser.parse_args()
    phase: int = args.phase

    before = fingerprint_tree(REPO_ROOT)

    print(f"[mutation] repo        : {REPO_ROOT}")
    print(f"[mutation] phase       : {phase}")
    print(f"[mutation] fingerprint : {before[:16]}...")

    results: list[MutationResult] = []
    with tempfile.TemporaryDirectory(prefix="merchantshield-mutation-") as tmp:
        sandbox = Path(tmp) / "repo"
        shutil.copytree(REPO_ROOT, sandbox, ignore=_ignore, symlinks=False)
        print(f"[mutation] sandbox     : {sandbox}")

        # Sanity check: the untouched copy must be green, otherwise every
        # "CAUGHT" below would be meaningless.
        baseline = run_pytest(sandbox, ("tests",))
        if baseline.returncode != 0:
            print("[mutation] BASELINE FAILED - the unmutated copy is already red.")
            print(baseline.stdout[-4000:])
            print(baseline.stderr[-2000:])
            return 2
        print("[mutation] baseline    : green")

        for mutation in MUTATIONS:
            result = check_mutation(sandbox, mutation, phase)
            results.append(result)
            print(f"[mutation] {mutation.id:<6} {result.status:<18} {mutation.title}")
            if result.detail and result.status != "CAUGHT":
                print(f"           -> {result.detail}")

    after = fingerprint_tree(REPO_ROOT)
    if before != after:
        print("[mutation] FATAL: the working tree changed during the run.")
        return 3
    print("[mutation] working tree unchanged (fingerprint matches)")

    report_dir = args.report_dir or (REPO_ROOT / "artifacts" / f"phase-{phase}")
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "MUTATION_REPORT.md"
    report_path.write_text(build_report(phase, results, before), encoding="utf-8")
    print(f"[mutation] report      : {report_path}")

    bad = [r for r in results if r.status in {"SURVIVED", "TARGET_MISSING"}]
    if bad:
        print(f"[mutation] FAILED: {len(bad)} mutation(s) not caught.")
        return 1

    applicable = [r for r in results if r.status == "CAUGHT"]
    print(f"[mutation] OK: all {len(applicable)} applicable mutation(s) caught.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
