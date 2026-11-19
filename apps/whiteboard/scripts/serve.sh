#!/usr/bin/env bash
# Build the SPA and serve API + UI from one process on :8094 (no docker).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${PORT:-8094}"

cd "$ROOT/frontend"
[ -d node_modules ] || npm install
npm run build

cd "$ROOT/backend"
[ -d .venv ] || { python3 -m venv .venv && ./.venv/bin/pip install -q -r requirements.txt; }

exec env WB_STATIC_DIR="$ROOT/frontend/dist" \
  ./.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
