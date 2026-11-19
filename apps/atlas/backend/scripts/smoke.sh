#!/usr/bin/env bash
# End-to-end smoke test against a real uvicorn process:
# register → project → ticket → transitions → mention comment → notification →
# agent ticket (API key + client_ref idempotency) → restart → data still there.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${PORT:-18080}"
BASE="http://127.0.0.1:${PORT}"
DATA_DIR="$(mktemp -d)"
DB="${DATA_DIR}/smoke.db"
LOG="${DATA_DIR}/uvicorn.log"

export ATLAS_ENV=test
export ATLAS_SECRET_KEY="smoke-$(date +%s)"
export ATLAS_DATABASE_URL="sqlite:///${DB}"
export ATLAS_ALLOW_REGISTRATION=true

start() {
  "${HERE}/.venv/bin/python" -m uvicorn app.main:app --host 127.0.0.1 --port "${PORT}" \
    --log-level warning >"${LOG}" 2>&1 &
  echo $! > "${DATA_DIR}/pid"
  for _ in $(seq 1 60); do
    if curl -sf "${BASE}/api/health" >/dev/null 2>&1; then return 0; fi
    sleep 0.5
  done
  echo "server did not start"; cat "${LOG}"; exit 1
}
stop() { kill "$(cat "${DATA_DIR}/pid")" 2>/dev/null || true; wait 2>/dev/null || true; }
trap 'stop' EXIT
cd "${HERE}"
start

py() { python3 -c "import sys,json;d=json.load(sys.stdin);print(eval('d'+sys.argv[1]))" "$1"; }
post() { curl -sf -X POST "$1" -H 'Content-Type: application/json' ${2:+-H "$2"} -d "$3"; }

echo "1. health:       $(curl -sf "${BASE}/api/health")"
echo "2. docs:         HTTP $(curl -s -o /dev/null -w '%{http_code}' "${BASE}/docs")"
echo "3. openapi:      $(curl -s "${BASE}/api/openapi.json" | python3 -c 'import sys,json;print(len(json.load(sys.stdin)["paths"]),"paths")')"
echo "4. meta:         $(curl -s "${BASE}/api/meta" | python3 -c 'import sys,json;d=json.load(sys.stdin);print(len(d["statuses"]),"statuses,",len(d["types"]),"types")')"

OWNER=$(post "${BASE}/api/auth/register" "" '{"email":"owner@example.com","username":"youssef","name":"يوسف","password":"Smoke-pass1"}')
OT=$(echo "$OWNER" | py "['access_token']")
AUTH="Authorization: Bearer ${OT}"
echo "5. bootstrap:    owner=$(echo "$OWNER" | py "['user']['username']") role=$(echo "$OWNER" | py "['user']['role']")"

MEMBER=$(post "${BASE}/api/users" "${AUTH}" '{"email":"omar@example.com","username":"omar","name":"عمر","password":"Smoke-pass2","role":"member"}')
MID=$(echo "$MEMBER" | py "['id']")
MT=$(post "${BASE}/api/auth/login" "" '{"email":"omar@example.com","password":"Smoke-pass2"}' | py "['access_token']")
MAUTH="Authorization: Bearer ${MT}"
echo "6. second user:  created by admin (id=${MID:0:8}…)"

PROJ=$(post "${BASE}/api/projects" "${AUTH}" '{"key":"ATL","name":"Atlas","description":"smoke"}')
echo "7. project:      $(echo "$PROJ" | py "['key']") created"

curl -sf -X POST "${BASE}/api/projects/ATL/members" -H "${AUTH}" -H 'Content-Type: application/json' \
  -d "{\"user_id\":\"${MID}\",\"role_in_project\":\"member\"}" >/dev/null
post "${BASE}/api/projects/ATL/labels" "${AUTH}" '{"name":"backend","color":"#2563EB"}' >/dev/null
echo "8. member+label: added omar, label backend"

TICKET=$(post "${BASE}/api/projects/ATL/tickets" "${AUTH}" \
  '{"title":"Smoke ticket","description_md":"ping @omar","priority":"high","labels":["backend"],"estimate_points":3}')
TK=$(echo "$TICKET" | py "['key']")
echo "9. ticket:       ${TK} status=$(echo "$TICKET" | py "['status']") version=$(echo "$TICKET" | py "['version']")"

for S in todo in_progress review; do
  curl -sf -X POST "${BASE}/api/tickets/${TK}/transition" -H "${AUTH}" \
    -H 'Content-Type: application/json' -d "{\"to\":\"${S}\"}" >/dev/null
done
BLOCKED=$(curl -s -X POST "${BASE}/api/tickets/${TK}/transition" -H "${AUTH}" \
  -H 'Content-Type: application/json' -d '{"to":"blocked"}')
echo "10. transitions: backlog→todo→in_progress→review; blocked w/o reason → $(echo "$BLOCKED" | py "['error']['code']")"

curl -sf -X POST "${BASE}/api/tickets/${TK}/comments" -H "${MAUTH}" -H 'Content-Type: application/json' \
  -d '{"body_md":"خلصت، @youssef راجع"}' >/dev/null
echo "11. comment:     mention posted by omar"
echo "12. notification: owner unread=$(curl -sf "${BASE}/api/notifications/unread_count" -H "${AUTH}" | py "['count']")"
echo "13. my work:     mentions=$(curl -sf "${BASE}/api/me/work" -H "${AUTH}" | python3 -c 'import sys,json;print(len(json.load(sys.stdin)["mentions"]))')"

KEY=$(post "${BASE}/api/users/${MID}/api-keys" "${MAUTH}" '{"name":"smoke-bot"}' | py "['key']")
AG=$(post "${BASE}/api/agent/tickets" "X-API-Key: ${KEY}" \
  '{"project_key":"ATL","title":"Agent ticket","priority":"urgent","client_ref":"smoke-run-1"}')
AG2=$(post "${BASE}/api/agent/tickets" "X-API-Key: ${KEY}" \
  '{"project_key":"ATL","title":"Agent ticket","priority":"urgent","client_ref":"smoke-run-1"}')
SAME=$([ "$(echo "$AG" | py "['id']")" = "$(echo "$AG2" | py "['id']")" ] && echo yes || echo no)
echo "14. agent api:   created $(echo "$AG" | py "['key']") (client_ref replay → same id: ${SAME})"

BEFORE=$(curl -s "${BASE}/api/projects/ATL/tickets" -H "${AUTH}" | py "['total']")
stop
sleep 1
start
AFTER=$(curl -s "${BASE}/api/projects/ATL/tickets" -H "${AUTH}" | py "['total']")
WAL=$(python3 -c "import sqlite3;print(sqlite3.connect('${DB}').execute('PRAGMA journal_mode').fetchone()[0])")
echo "15. persistence: tickets before=${BEFORE} after restart=${AFTER}; journal_mode=${WAL}"

[ "${BEFORE}" = "${AFTER}" ] && [ "${AFTER}" -ge 2 ] || { echo "PERSISTENCE FAILED"; exit 1; }
[ "${SAME}" = "yes" ] || { echo "IDEMPOTENCY FAILED"; exit 1; }
echo "SMOKE OK (data dir: ${DATA_DIR})"
