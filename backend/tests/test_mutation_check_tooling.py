"""Tests for the mutation-check tool itself.

The mutation check is the evidence that the test suite actually has teeth, so
the tool must not be the weak link. In particular it has to behave the same
on a CRLF Windows checkout as on an LF Linux checkout, because the project
owner develops on Windows 11 and CI runs on Linux.

The script lives outside the ``app`` package, so it is imported by path.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "mutation_check.py"


def load_mutation_check() -> ModuleType:
    spec = importlib.util.spec_from_file_location("ms_mutation_check", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def mc() -> ModuleType:
    return load_mutation_check()


def test_script_exists() -> None:
    assert SCRIPT_PATH.is_file(), f"mutation_check.py missing at {SCRIPT_PATH}"


# --------------------------------------------------------------------------
# Line-ending handling
# --------------------------------------------------------------------------


def test_read_source_normalises_crlf(mc: ModuleType, tmp_path: Path) -> None:
    f = tmp_path / "crlf.py"
    f.write_bytes(b"line one\r\nline two\r\n")

    assert mc.read_source(f) == "line one\nline two\n"


def test_read_source_normalises_lone_cr(mc: ModuleType, tmp_path: Path) -> None:
    f = tmp_path / "cr.py"
    f.write_bytes(b"old mac\rstyle\r")

    assert mc.read_source(f) == "old mac\nstyle\n"


def test_write_source_always_writes_lf(mc: ModuleType, tmp_path: Path) -> None:
    f = tmp_path / "out.py"
    mc.write_source(f, "a\nb\nc\n")

    # Byte-exact: no \r anywhere, whatever platform this runs on.
    assert f.read_bytes() == b"a\nb\nc\n"


def test_round_trip_converts_crlf_to_lf(mc: ModuleType, tmp_path: Path) -> None:
    f = tmp_path / "rt.py"
    f.write_bytes(b"x = 1\r\ny = 2\r\n")

    mc.write_source(f, mc.read_source(f))

    assert f.read_bytes() == b"x = 1\ny = 2\n"


def test_apply_mutation_matches_a_crlf_file(mc: ModuleType, tmp_path: Path) -> None:
    """The real scenario: a Windows checkout with CRLF endings.

    The mutation ``find`` strings are written with ``\\n``. If matching were
    done on raw bytes, every mutation would report TARGET_MISSING on Windows
    and the whole check would fail for the wrong reason.
    """
    sandbox = tmp_path / "sandbox"
    target_rel = "backend/app/demo.py"
    target = sandbox / target_rel
    target.parent.mkdir(parents=True)

    lf_source = "def seed():\n    if settings.demo_mode:\n        insert()\n"
    target.write_bytes(lf_source.replace("\n", "\r\n").encode("utf-8"))
    assert b"\r\n" in target.read_bytes(), "fixture must actually be CRLF"

    mutation = mc.Mutation(
        id="TEST-CRLF",
        phase=0,
        title="crlf matching",
        protects="test fixture",
        relative_path=target_rel,
        find="    if settings.demo_mode:\n",
        replace="    if False:  # MUTANT\n",
        tests=(),
    )

    ok, original, message = mc.apply_mutation(sandbox, mutation)

    assert ok, f"CRLF file was not matched: {message}"
    assert original == lf_source
    assert target.read_bytes() == (
        b"def seed():\n    if False:  # MUTANT\n        insert()\n"
    )

    # Restoring must give back LF bytes, not the CRLF we started with.
    mc.write_source(target, original)
    assert target.read_bytes() == lf_source.encode("utf-8")


def test_apply_mutation_reports_a_missing_target(mc: ModuleType, tmp_path: Path) -> None:
    sandbox = tmp_path / "sandbox"
    target = sandbox / "backend/app/demo.py"
    target.parent.mkdir(parents=True)
    target.write_text("def seed():\n    pass\n", encoding="utf-8")

    mutation = mc.Mutation(
        id="TEST-MISSING",
        phase=0,
        title="refactored away",
        protects="test fixture",
        relative_path="backend/app/demo.py",
        find="    if settings.demo_mode:\n",
        replace="    if False:\n",
        tests=(),
    )

    ok, _original, message = mc.apply_mutation(sandbox, mutation)

    assert not ok
    assert "target text not found" in message


def test_apply_mutation_rejects_an_ambiguous_target(mc: ModuleType, tmp_path: Path) -> None:
    """A find string that matches twice would mutate two places at once."""
    sandbox = tmp_path / "sandbox"
    target = sandbox / "backend/app/demo.py"
    target.parent.mkdir(parents=True)
    target.write_text("x = 1\nx = 1\n", encoding="utf-8")

    mutation = mc.Mutation(
        id="TEST-AMBIGUOUS",
        phase=0,
        title="ambiguous",
        protects="test fixture",
        relative_path="backend/app/demo.py",
        find="x = 1\n",
        replace="x = 2\n",
        tests=(),
    )

    ok, _original, message = mc.apply_mutation(sandbox, mutation)

    assert not ok
    assert "appears 2 times" in message


# --------------------------------------------------------------------------
# The mutation catalogue must stay honest
# --------------------------------------------------------------------------


def current_phase() -> int:
    return int((REPO_ROOT / "PHASE").read_text(encoding="utf-8").strip())


def active_mutations(mc: ModuleType) -> list[object]:
    """Mutations for the current phase or earlier.

    Later-phase entries deliberately point at files that do not exist yet -
    the catalogue lists them so the report can show what is still pending,
    and ``check_mutation`` returns NOT_YET_APPLICABLE for them.
    """
    phase = current_phase()
    return [m for m in mc.MUTATIONS if m.phase <= phase]


def test_there_is_at_least_one_active_mutation(mc: ModuleType) -> None:
    assert active_mutations(mc), f"no mutations defined for phase {current_phase()}"


def test_every_active_mutation_targets_a_file_that_exists(mc: ModuleType) -> None:
    """Catches a rename that would otherwise silently disable a mutation."""
    for mutation in active_mutations(mc):
        path = REPO_ROOT / mutation.relative_path
        assert path.is_file(), (
            f"mutation {mutation.id} points at {mutation.relative_path}, "
            "which does not exist"
        )


def test_future_mutations_are_declared_for_a_later_phase(mc: ModuleType) -> None:
    """A mutation whose file is missing must be honestly marked as future work."""
    phase = current_phase()
    for mutation in mc.MUTATIONS:
        if not (REPO_ROOT / mutation.relative_path).is_file():
            assert mutation.phase > phase, (
                f"mutation {mutation.id} is active in phase {phase} but its target "
                f"{mutation.relative_path} does not exist"
            )


def test_every_active_find_string_is_present_and_unique(mc: ModuleType) -> None:
    for mutation in active_mutations(mc):
        source = mc.read_source(REPO_ROOT / mutation.relative_path)
        count = source.count(mutation.find)
        assert count == 1, (
            f"mutation {mutation.id}: find string occurs {count} times in "
            f"{mutation.relative_path} (must be exactly 1)"
        )


def test_a_mutation_actually_changes_the_source(mc: ModuleType) -> None:
    """A find/replace pair that is a no-op would always report SURVIVED."""
    for mutation in active_mutations(mc):
        assert mutation.find != mutation.replace, (
            f"mutation {mutation.id} replaces its target with itself"
        )


def test_every_mutation_names_at_least_one_test(mc: ModuleType) -> None:
    for mutation in mc.MUTATIONS:
        assert mutation.tests, f"mutation {mutation.id} runs no tests"


def test_mutation_identifiers_are_unique(mc: ModuleType) -> None:
    identifiers = [m.id for m in mc.MUTATIONS]
    assert len(identifiers) == len(set(identifiers))


def test_dotenv_is_never_copied_into_the_sandbox(mc: ModuleType) -> None:
    """A developer's real credentials must not reach the temp copy."""
    skipped = mc._ignore(str(REPO_ROOT), [".env", ".env.local", ".env.example", "app"])

    assert ".env" in skipped
    assert ".env.local" in skipped
    assert ".env.example" not in skipped, "the committed template must be copied"
    assert "app" not in skipped
