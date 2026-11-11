"""MASTER 10.9 - the mechanical honesty check.

Scans the code and the published copy for banned phrases. The only permitted
place for a banned phrase is a sentence in README "Limitations" that explicitly
DENIES it; those sentences are allowlisted literally, not by keyword, so adding
a new claim cannot slip through by accident.

This test exists because prose is code that nobody compiles.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

#: Files that ship to a judge and must not make an unmeasured claim.
SCAN_TARGETS = (
    Path("frontend/src"),
    Path("README.md"),
    Path("DEMO_SCRIPT.md"),
    Path("DEVPOST_TEXT.md"),
)

BANNED_PHRASES = (
    "win probability",
    "chance to win",
    "money protected",
    "fewer disputes",
    "fully validated",
    "exactly-once",
)

#: The exact sentences (README Limitations) that break a rule in order to deny it.
ALLOWED_SENTENCES = (
    "This project does not claim exactly-once semantics for any external call.",
    "No win probabilities, no \"money protected\", no \"X% fewer disputes\".",
    "That is not a win probability and not a \"chance to win\": it is an "
    "estimate from your own order fields.",
)

TEXT_SUFFIXES = {".ts", ".tsx", ".js", ".jsx", ".css", ".html", ".md", ".json"}


def _iter_files(target: Path):
    if not target.exists():
        raise AssertionError(
            f"{target} is missing; the honesty scan must cover every published file"
        )
    if target.is_file():
        yield target
        return
    for path in sorted(target.rglob("*")):
        if path.is_file() and path.suffix in TEXT_SUFFIXES:
            yield path


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n{2,}", text)
    return [part.strip() for part in parts if part.strip()]


def _normalise(value: str) -> str:
    """Collapse whitespace and drop a leading markdown list marker.

    A bullet is formatting, not a claim: "- No win probabilities." is the same
    sentence as "No win probabilities." for the purpose of this check.
    """
    collapsed = " ".join(value.split())
    stripped = re.sub(r"^(?:[-*+]|\d+\.)\s+", "", collapsed)
    return stripped


ALLOWED = {_normalise(sentence) for sentence in ALLOWED_SENTENCES}


def test_no_banned_phrase_appears_outside_an_explicit_denial() -> None:
    violations: list[str] = []

    for target in SCAN_TARGETS:
        for path in _iter_files(REPO_ROOT / target):
            text = path.read_text(encoding="utf-8")
            for sentence in _sentences(text):
                lowered = sentence.lower()
                for phrase in BANNED_PHRASES:
                    if phrase not in lowered:
                        continue
                    if _normalise(sentence) in ALLOWED:
                        continue
                    if _normalise(sentence) in ALLOWED:
                        continue
                    violations.append(
                        f"{path.relative_to(REPO_ROOT)}: {phrase!r} in -> {sentence[:160]}"
                    )

    assert not violations, "banned phrases found:\n" + "\n".join(violations)


def test_the_allowlist_sentences_really_are_denials() -> None:
    """An allowlist entry must contain both the phrase and a denial word."""
    denial_words = ("not", "no", "never", "cannot")
    for sentence in ALLOWED_SENTENCES:
        lowered = sentence.lower()
        assert any(phrase in lowered for phrase in BANNED_PHRASES), sentence
        assert any(word in lowered for word in denial_words), sentence


def test_scan_targets_exist() -> None:
    for target in SCAN_TARGETS:
        assert (REPO_ROOT / target).exists(), f"{target} must exist to be scanned"


@pytest.mark.parametrize("phrase", BANNED_PHRASES)
def test_the_scanner_would_actually_catch_a_planted_phrase(phrase: str, tmp_path: Path) -> None:
    """A scanner that cannot fail is not a test."""
    planted = tmp_path / "planted.md"
    planted.write_text(f"Our tool guarantees {phrase} for every merchant.\n", encoding="utf-8")

    found = [
        sentence
        for sentence in _sentences(planted.read_text(encoding="utf-8"))
        if phrase in sentence.lower() and _normalise(sentence) not in ALLOWED
    ]
    assert found, f"the scanner failed to catch a planted {phrase!r}"
