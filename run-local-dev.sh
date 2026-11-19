#!/usr/bin/env bash
# Start the QA testing agent: backend (uvicorn --reload) and dashboard (next dev) together.
# Both listen on 127.0.0.1 only. Ports default to 8400 / 4000 so they don't clash with the
# app under test on 3000 / 8000. Ctrl+C stops both.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$REPO_ROOT/frontend"
BACKEND_DIR="$REPO_ROOT/backend"
BE_PORT="${BE_PORT:-8400}"
FE_PORT="${FE_PORT:-4000}"
FE_PID=""
BE_PID=""

cleanup() {
  trap - EXIT INT TERM
  echo; echo "Stopping local FE/BE processes..."
  for pid in "$FE_PID" "$BE_PID"; do
    [[ -n "$pid" ]] && kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

for cmd in uv npm; do
  command -v "$cmd" >/dev/null 2>&1 || { echo "$cmd is required but was not found in PATH."; exit 1; }
done

if [[ -n "${ANTHROPIC_API_KEY:-}" ]]; then
  echo "WARNING: ANTHROPIC_API_KEY is set. Agent runs will be refused (they would bill the API)."
  echo "         Remove it from your shell profile to run agents on your Claude subscription."
fi

[[ -d "$FRONTEND_DIR/node_modules/.bin" ]] || (cd "$FRONTEND_DIR" && npm install)
[[ -f "$FRONTEND_DIR/.env.local" ]] || cp "$FRONTEND_DIR/.env.example" "$FRONTEND_DIR/.env.local"
[[ -f "$BACKEND_DIR/.env" ]] || cp "$BACKEND_DIR/.env.example" "$BACKEND_DIR/.env"
(cd "$BACKEND_DIR" && uv sync --quiet)

# Playwright for Python ships its own Node driver, which doesn't run on older macOS (e.g. 12).
# Fall back to the system Node when the bundled one fails.
if [[ -z "${PLAYWRIGHT_NODEJS_PATH:-}" ]] && ! (cd "$BACKEND_DIR" && uv run playwright --version >/dev/null 2>&1); then
  if command -v node >/dev/null 2>&1; then
    export PLAYWRIGHT_NODEJS_PATH="$(command -v node)"
    echo "Using system Node for Playwright: $PLAYWRIGHT_NODEJS_PATH"
  fi
fi

echo "Starting backend   → http://127.0.0.1:$BE_PORT  (docs: /docs)"
(cd "$BACKEND_DIR" && uv run uvicorn app.main:app --host 127.0.0.1 --port "$BE_PORT" --reload --reload-dir src) &
BE_PID=$!

echo "Starting dashboard → http://localhost:$FE_PORT"
(cd "$FRONTEND_DIR" && NEXT_PUBLIC_BACKEND_URL="${NEXT_PUBLIC_BACKEND_URL:-http://localhost:$BE_PORT}" npx next dev -H 127.0.0.1 -p "$FE_PORT") &
FE_PID=$!

echo "Press Ctrl+C to stop both. Then open Setup check: http://localhost:$FE_PORT/setup"
while kill -0 "$FE_PID" 2>/dev/null && kill -0 "$BE_PID" 2>/dev/null; do sleep 1; done
echo "A process exited; shutting down."
exit 1
