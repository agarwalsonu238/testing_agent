#!/usr/bin/env bash
# Start backend (uvicorn --reload) and frontend (next dev) together.
# Ctrl+C stops both.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$REPO_ROOT/frontend"
BACKEND_DIR="$REPO_ROOT/backend"
BE_PORT="${BE_PORT:-8000}"
FE_PORT="${FE_PORT:-3000}"
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

[[ -d "$FRONTEND_DIR/node_modules" ]] || (cd "$FRONTEND_DIR" && npm install)
[[ -f "$FRONTEND_DIR/.env.local" ]] || cp "$FRONTEND_DIR/.env.example" "$FRONTEND_DIR/.env.local"
[[ -f "$BACKEND_DIR/.env" ]] || cp "$BACKEND_DIR/.env.example" "$BACKEND_DIR/.env"

echo "Starting backend  → http://localhost:$BE_PORT  (docs: /docs)"
(cd "$BACKEND_DIR" && uv run uvicorn app.main:app --host 0.0.0.0 --port "$BE_PORT" --reload) &
BE_PID=$!

echo "Starting frontend → http://localhost:$FE_PORT"
(cd "$FRONTEND_DIR" && npx next dev -p "$FE_PORT") &
FE_PID=$!

echo "Press Ctrl+C to stop both."
while kill -0 "$FE_PID" 2>/dev/null && kill -0 "$BE_PID" 2>/dev/null; do sleep 1; done
echo "A process exited; shutting down."
exit 1
