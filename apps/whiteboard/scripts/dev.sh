#!/usr/bin/env bash
# Dev loop: backend with --reload on :8094 + vite dev server on :5174 (proxies /api).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$ROOT/backend"
[ -d .venv ] || { python3 -m venv .venv && ./.venv/bin/pip install -q -r requirements.txt; }
./.venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8094 &
BACKEND_PID=$!
trap 'kill $BACKEND_PID 2>/dev/null || true' EXIT

cd "$ROOT/frontend"
[ -d node_modules ] || npm install
npm run dev
