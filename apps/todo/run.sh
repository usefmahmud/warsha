#!/usr/bin/env bash
# Boot TODO (API + built SPA) on one port. Usage: ./run.sh [port]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT="${1:-8093}"
PY="$ROOT/backend/.venv/bin/python"

if [ ! -x "$PY" ]; then
  echo "no venv at backend/.venv — run: python3 -m venv backend/.venv && backend/.venv/bin/pip install -r backend/requirements.txt" >&2
  exit 1
fi

if [ ! -f "$ROOT/frontend/dist/index.html" ]; then
  echo "warning: frontend/dist missing — serving API only (cd frontend && npm run build)" >&2
fi

cd "$ROOT/backend"
exec "$PY" -m uvicorn app.main:app --host 127.0.0.1 --port "$PORT" --log-level info
