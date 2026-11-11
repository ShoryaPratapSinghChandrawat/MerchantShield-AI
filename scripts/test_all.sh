#!/usr/bin/env bash
# Run every check this project has, in the order that fails fastest.
#
# Mirrors scripts/test_all.ps1. Stops at the first failure: a green later step
# proves nothing if an earlier one is red.
#
# Usage:
#   bash scripts/test_all.sh              # pytest, tsc, build, Playwright
#   bash scripts/test_all.sh --phase 2    # ... plus mutation check for phase 2
#   bash scripts/test_all.sh --no-browser # skip Playwright
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="$REPO_ROOT/.venv/bin/python"
FRONTEND="$REPO_ROOT/frontend"

PHASE=-1
RUN_BROWSER=1
while [ $# -gt 0 ]; do
  case "$1" in
    --phase) PHASE="${2:-0}"; shift 2 ;;
    --no-browser) RUN_BROWSER=0; shift ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

step() { printf '\n\033[36m==> %s\033[0m\n' "$1"; }
pass() { printf '\033[32mPASS: %s (%ss)\033[0m\n' "$1" "$2"; }
failed() {
  printf '\033[31mFAIL: %s (exit %s)\033[0m\n' "$1" "$2"
  printf '\033[31mStopped. Fix this before trusting anything after it.\033[0m\n'
  exit 1
}

if [ ! -x "$PYTHON" ]; then
  echo "FAIL: no .venv at $PYTHON" >&2
  echo "      python3.11 -m venv .venv && .venv/bin/python -m pip install -r backend/requirements.txt" >&2
  exit 1
fi

run() {
  local name="$1"; shift
  local start=$SECONDS
  step "$name"
  if "$@"; then pass "$name" "$((SECONDS - start))"; else failed "$name" "$?"; fi
}

run "backend pytest" bash -c "cd '$REPO_ROOT/backend' && '$PYTHON' -m pytest"

run "frontend typecheck (tsc --noEmit)" bash -c "cd '$FRONTEND' && npx tsc --noEmit"

run "frontend build (vite build)" bash -c "cd '$FRONTEND' && npx vite build"

if [ "$RUN_BROWSER" -eq 1 ]; then
  run "browser suite (Playwright)" bash -c "cd '$FRONTEND' && npx playwright test"
fi

if [ "$PHASE" -ge 0 ]; then
  run "mutation check (phase $PHASE)" bash -c "cd '$REPO_ROOT' && '$PYTHON' scripts/mutation_check.py --phase $PHASE"
fi

printf '\n\033[32mAll requested checks passed.\033[0m\n'
printf '\033[33mReminder: this proves the checks RAN HERE. It does not prove Windows,\033[0m\n'
printf '\033[33mthe PayPal Sandbox, or Gemini work - those are separate, labelled claims.\033[0m\n'
