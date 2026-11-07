#!/usr/bin/env python3
"""Build merchantshield-ai-phaseN.zip from the real working files.

Section 11 rules implemented here:

* Built with :mod:`zipfile` from the actual files on disk - never a git patch.
* Explicit exclusions. Note we never use the pattern ``*.git*``, because that
  would also remove ``.github/`` and ``.gitignore``, both of which must ship.
* Exactly one top-level folder inside the archive.
* The archive is integrity-tested, its entries are listed, it is scanned for
  secrets, and the presence of required files is confirmed.

Usage (Windows PowerShell):
    python scripts\\package_release.py --phase 0
"""

from __future__ import annotations

import argparse
import re
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TOP_LEVEL_NAME = "merchantshield-ai"

EXCLUDED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "dist",
    "build",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".vite",
    ".idea",
    ".vscode",
    "htmlcov",
    "artifacts",
    "playwright-report",
    "test-results",
}

EXCLUDED_SUFFIXES = {
    ".zip",
    ".patch",
    ".diff",
    ".pyc",
    ".pyo",
    ".db",
    ".sqlite",
    ".sqlite3",
    ".db-wal",
    ".db-shm",
    ".log",
    ".coverage",
}

#: Exact filenames that must never ship. ``.env.example`` is explicitly kept.
EXCLUDED_NAMES = {".DS_Store", "Thumbs.db", ".coverage"}

REQUIRED_FILES = (
    "README.md",
    "LICENSE",
    "DECISIONS.md",
    "BUGS_FIXED.md",
    "AI_DISCLOSURE.md",
    ".env.example",
    ".gitignore",
    ".gitattributes",
    ".nvmrc",
    "PHASE",
    ".github/workflows/ci.yml",
    "backend/requirements.txt",
    "backend/pytest.ini",
    "backend/app/main.py",
    "frontend/package.json",
    "frontend/package-lock.json",
    "frontend/playwright.config.ts",
    "scripts/mutation_check.py",
    "scripts/package_release.py",
    "scripts/windows_check.ps1",
    "docs/SOURCES.md",
    "docs/GLOSSARY.md",
)

#: Patterns that look like a leaked credential.
SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("PayPal live client id (A... 80 chars)", re.compile(r"\bA[A-Za-z0-9_-]{79,}\b")),
    ("OpenAI key", re.compile(r"\bsk-[A-Za-z0-9]{20,}\b")),
    ("Anthropic key", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}\b")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b")),
    ("AWS access key id", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("Private key block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    # NOTE: these use [ \t]* rather than \s*. \s matches newlines, so
    # "LLM_API_KEY=\nLLM_MODEL=" would match the *next* line's variable name
    # and report an empty placeholder as a leaked secret. See BUG-0003.
    (
        "Non-empty PAYPAL_CLIENT_SECRET assignment",
        re.compile(r"PAYPAL_CLIENT_SECRET[ \t]*=[ \t]*['\"]?[A-Za-z0-9_\-]{8,}"),
    ),
    (
        "Non-empty PAYPAL_CLIENT_ID assignment",
        re.compile(r"PAYPAL_CLIENT_ID[ \t]*=[ \t]*['\"]?[A-Za-z0-9_\-]{20,}"),
    ),
    (
        "Non-empty LLM_API_KEY assignment",
        re.compile(r"LLM_API_KEY[ \t]*=[ \t]*['\"]?[A-Za-z0-9_\-]{8,}"),
    ),
)

TEXT_SUFFIXES = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".json", ".md", ".yml", ".yaml",
    ".html", ".css", ".txt", ".ini", ".cfg", ".toml", ".example", ".nvmrc",
    ".gitignore", ".gitattributes",
}


def should_skip(path: Path) -> str | None:
    """Return a reason to skip ``path``, or None to include it."""
    relative = path.relative_to(REPO_ROOT)

    for part in relative.parts[:-1]:
        if part in EXCLUDED_DIRS:
            return f"inside excluded dir {part}/"

    name = relative.name
    if name in EXCLUDED_NAMES:
        return "excluded filename"
    if name == ".env" or (name.startswith(".env.") and name != ".env.example"):
        return "real .env file"
    if path.suffix in EXCLUDED_SUFFIXES:
        return f"excluded suffix {path.suffix}"
    return None


def collect_files() -> list[Path]:
    files: list[Path] = []
    for path in sorted(REPO_ROOT.rglob("*")):
        if not path.is_file():
            continue
        if any(part in EXCLUDED_DIRS for part in path.relative_to(REPO_ROOT).parts):
            continue
        if should_skip(path) is None:
            files.append(path)
    return files


def is_texty(path: Path) -> bool:
    return path.suffix in TEXT_SUFFIXES or path.name in {"PHASE", ".nvmrc", "LICENSE"}


def scan_for_secrets(files: list[Path]) -> list[str]:
    findings: list[str] = []
    for path in files:
        if not is_texty(path):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for label, pattern in SECRET_PATTERNS:
            for match in pattern.finditer(text):
                snippet = match.group(0)
                redacted = snippet[:6] + "..." if len(snippet) > 6 else snippet
                findings.append(
                    f"{path.relative_to(REPO_ROOT).as_posix()}: {label} ({redacted})"
                )
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Package a MerchantShield AI phase ZIP.")
    parser.add_argument("--phase", type=int, required=True)
    parser.add_argument("--outdir", type=Path, default=REPO_ROOT.parent)
    parser.add_argument(
        "--name",
        default=None,
        help=(
            "Base name for the ZIP FILE, without the .zip extension. Default: "
            "merchantshield-ai-phase<PHASE>. Useful for a re-cut of the same "
            "phase, e.g. --name merchantshield-ai-phase0-rev2. The single "
            f"top-level folder inside the archive is always '{TOP_LEVEL_NAME}/' "
            "regardless of this option, so the extracted path stays stable."
        ),
    )
    args = parser.parse_args()

    base_name: str = args.name if args.name is not None else f"merchantshield-ai-phase{args.phase}"

    # The name becomes a directory inside the archive, so reject anything that
    # could escape it or produce an unopenable file on Windows.
    if base_name != base_name.strip() or not base_name:
        print("[package] ABORT - --name must not be empty or padded with spaces.")
        return 1
    if base_name.lower().endswith(".zip"):
        print("[package] ABORT - omit the .zip extension from --name.")
        return 1
    forbidden = set('/\\:*?"<>|')
    bad = sorted(forbidden.intersection(base_name))
    if bad or base_name in {".", ".."}:
        print(f"[package] ABORT - --name contains illegal characters: {bad or base_name}")
        return 1

    zip_path: Path = args.outdir / f"{base_name}.zip"
    if zip_path.exists():
        zip_path.unlink()

    files = collect_files()
    print(f"[package] files to include : {len(files)}")

    print("[package] scanning for secrets...")
    findings = scan_for_secrets(files)
    if findings:
        print("[package] ABORT - possible secrets found:")
        for finding in findings:
            print(f"          {finding}")
        return 1
    print("[package] secret scan       : clean")

    present = {p.relative_to(REPO_ROOT).as_posix() for p in files}
    missing = [req for req in REQUIRED_FILES if req not in present]
    if missing:
        print("[package] ABORT - required files missing from the archive:")
        for item in missing:
            print(f"          {item}")
        return 1
    print(f"[package] required files    : all {len(REQUIRED_FILES)} present")

    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in files:
            arcname = f"{TOP_LEVEL_NAME}/{path.relative_to(REPO_ROOT).as_posix()}"
            zf.write(path, arcname)

    with zipfile.ZipFile(zip_path) as zf:
        broken = zf.testzip()
        if broken is not None:
            print(f"[package] ABORT - corrupt entry: {broken}")
            return 1
        names = zf.namelist()

    roots = {name.split("/", 1)[0] for name in names}
    if roots != {TOP_LEVEL_NAME}:
        print(f"[package] ABORT - expected exactly one top-level folder, got {sorted(roots)}")
        return 1

    size_kb = zip_path.stat().st_size / 1024
    print(f"[package] integrity test    : OK ({len(names)} entries)")
    print(f"[package] top-level folder  : {TOP_LEVEL_NAME}/ (exactly one)")
    print(f"[package] archive           : {zip_path} ({size_kb:.1f} KiB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
