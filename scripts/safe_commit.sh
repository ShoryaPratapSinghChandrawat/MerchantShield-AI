#!/usr/bin/env bash
# Commit with explicit paths only, and refuse to commit anything suspicious.
#
# The rules this enforces (from MASTER 9):
#   * never `git add -A` / `git add .` - every path is named;
#   * whitespace errors fail the commit;
#   * a secret-shaped string in the staged diff fails the commit;
#   * an empty staging area fails, because "nothing to commit" is usually a
#     mistake rather than an intention;
#   * the commit message describes what changed, so a future reader has a chance.
#
# Usage:
#   bash scripts/safe_commit.sh "docs: rewrite README" README.md DEMO_SCRIPT.md
#   bash scripts/safe_commit.sh -a "chore: everything staged"   # stage-and-commit every tracked change
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if [ $# -lt 2 ]; then
  echo "usage: $0 \"<message>\" <path> [path ...]" >&2
  echo "       $0 -a \"<message>\"   (every tracked modification, listed for review)" >&2
  exit 2
fi

MESSAGE="$1"; shift

if [ "$MESSAGE" = "-a" ]; then
  echo "Refusing: -a would stage everything, which is exactly what this script exists to avoid." >&2
  exit 2
fi

echo "==> staging ${#} explicit path(s)"
git add -- "$@"

echo "==> whitespace check"
if ! git diff --cached --check; then
  echo "FAIL: whitespace errors in the staged diff." >&2
  exit 1
fi

echo "==> staged file list"
git diff --cached --stat

STAGED_FILES=$(git diff --cached --name-only)
if [ -z "$STAGED_FILES" ]; then
  echo "FAIL: nothing staged - did the paths exist?" >&2
  exit 1
fi

echo "==> scanning the staged diff for secrets"
# Deliberately shallow: this catches an accidentally pasted credential, not a
# determined attacker. Real secrets live in environment variables, never here.
PATTERNS='(client[_-]?secret|api[_-]?key|access[_-]?token|password)[[:space:]]*[:=][[:space:]]*["'\'']?[A-Za-z0-9_\-]{12,}'
if git diff --cached -U0 | grep -inE "$PATTERNS" | grep -viE '(your-|example|placeholder|test-|dummy|\$\{|\$env|os\.environ|settings\.)' ; then
  echo "FAIL: something above looks like a real credential." >&2
  exit 1
fi

if echo "$STAGED_FILES" | grep -E '(^|/)\.env$' ; then
  echo "FAIL: .env must never be committed." >&2
  exit 1
fi

echo "==> committing"
git commit -m "$MESSAGE"

echo "==> done"
git log --oneline -1
