#!/usr/bin/env bash
# Start MerchantShield AI locally in demo mode (Linux/macOS).
#
# Same checks as scripts/run_demo.ps1, in the same order, with the same fixes.
# Demo mode: 15 seeded SIMULATED orders, PayPal served by the local mock and
# labelled MOCK, no credentials, no real money.
set -euo pipefail

PORT="${PORT:-8000}"
HOST_ADDRESS="${HOST_ADDRESS:-127.0.0.1}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="$REPO_ROOT/.venv/bin/python"
DIST_INDEX="$REPO_ROOT/frontend/dist/index.html"

step() { printf '\033[36m==> %s\033[0m\n' "$1"; }
fail() {
  printf '\033[31mFAIL: %s\033[0m\n' "$1"
  if [ -n "${2:-}" ]; then printf '\033[33m      %s\033[0m\n' "$2"; fi
  exit 1
}

step "Checking the repository layout"
[ -f "$REPO_ROOT/backend/app/main.py" ] ||
  fail "backend/app/main.py not found next to this script." "Run this from the repository you cloned."

step "Checking the Python virtual environment"
[ -x "$PYTHON" ] ||
  fail "no .venv at $PYTHON" "python3.11 -m venv .venv && .venv/bin/python -m pip install -r backend/requirements.txt"
"$PYTHON" --version

step "Checking that the frontend is built"
[ -f "$DIST_INDEX" ] || fail "frontend/dist is missing, so there is no SPA to serve." "cd frontend && npm ci && npm run build"
echo "    found $DIST_INDEX"

step "Checking that port $PORT is free"
if command -v ss >/dev/null 2>&1 && ss -ltn "sport = :$PORT" | grep -q LISTEN; then
  fail "port $PORT is already in use." "stop the process holding it, or run with PORT=8010"
elif command -v lsof >/dev/null 2>&1 && lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  fail "port $PORT is already in use." "stop the process holding it, or run with PORT=8010"
fi

export DEMO_MODE=true
export PAYPAL_MODE=mock
export PORT

step "Starting MerchantShield AI on http://${HOST_ADDRESS}:${PORT}"
echo "    DEMO_MODE    = $DEMO_MODE"
echo "    PAYPAL_MODE  = $PAYPAL_MODE"
echo "    LLM_PROVIDER = ${LLM_PROVIDER:-none}"
echo
printf '\033[32m    Open http://%s:%s in your browser.\033[0m\n' "$HOST_ADDRESS" "$PORT"
printf '\033[32m    Press Ctrl+C to stop.\033[0m\n\n'

cd "$REPO_ROOT"
exec "$PYTHON" -m uvicorn app.main:app --app-dir backend --host "$HOST_ADDRESS" --port "$PORT"
