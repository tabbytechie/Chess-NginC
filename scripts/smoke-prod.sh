#!/usr/bin/env bash
# Production smoke test (REL-013). Exercises the full play loop against a
# deployed API base URL and fails non-zero on any unexpected status or shape.
#
# Usage: API_BASE=https://api.example.com ./scripts/smoke-prod.sh
#
# It asserts the Phase 3/5 contract: the engine replies inside the human move's
# own response (auto-reply, two plies), a resignation is attributed as a result,
# and the game exports as PGN. `/ready` is checked live; the "503 with the DB
# stopped" case is intentionally not automated here (it needs stopping the
# database) and is covered by tests/test_health.py instead.
set -euo pipefail

API_BASE="${API_BASE:?set API_BASE, e.g. https://api.example.com}"
JAR="$(mktemp)"
BODY="$(mktemp)"
trap 'rm -f "${JAR}" "${BODY}"' EXIT

# jq-free JSON field reader: json_get <body-file> <python-expression>
# The expression receives the parsed object as ``d`` and must yield a string.
json_get() {
  python3 -c 'import sys, json
d = json.load(open(sys.argv[1]))
print(eval(sys.argv[2]))' "$1" "$2"
}

check() { # check <desc> <expected> <actual>
  if [ "$2" != "$3" ]; then
    echo "FAIL: $1 — expected $2, got $3" >&2
    exit 1
  fi
  echo "ok: $1 ($3)"
}

# --- Liveness + readiness -----------------------------------------------------
code=$(curl -s -o /dev/null -w "%{http_code}" "${API_BASE}/api/v1/health")
check "health" 200 "${code}"

code=$(curl -s -o "${BODY}" -w "%{http_code}" "${API_BASE}/api/v1/ready")
check "ready" 200 "${code}"
check "ready.database" "up" "$(json_get "${BODY}" "d['database']")"

# --- Register -----------------------------------------------------------------
EMAIL="smoke-$(date +%s)@example.com"
code=$(curl -s -o /dev/null -w "%{http_code}" -c "${JAR}" \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"${EMAIL}\",\"password\":\"s3cret-pass\"}" \
  "${API_BASE}/api/v1/auth/register")
check "register" 201 "${code}"

# --- Create a computer game as White on Easy ----------------------------------
code=$(curl -s -o "${BODY}" -w "%{http_code}" -b "${JAR}" \
  -H 'Content-Type: application/json' \
  -d '{"mode":"computer","player_color":"white","engine_level":"easy"}' \
  "${API_BASE}/api/v1/games")
check "create game" 201 "${code}"
GID="$(json_get "${BODY}" "d['id']")"
VER="$(json_get "${BODY}" "d['version']")"
check "create player_color" "white" "$(json_get "${BODY}" "d['player_color']")"
check "create move_count" "0" "$(json_get "${BODY}" "len(d['moves'])")"
echo "ok: game id=${GID} version=${VER}"

# --- Play 1. e4 and confirm the engine auto-replies in the SAME response ------
code=$(curl -s -o "${BODY}" -w "%{http_code}" -b "${JAR}" \
  -H 'Content-Type: application/json' \
  -d "{\"uci\":\"e2e4\",\"expected_version\":${VER}}" \
  "${API_BASE}/api/v1/games/${GID}/moves")
check "submit e2e4" 200 "${code}"
# Both plies land: human e4 + one engine reply => 2 moves, version advanced 2x.
check "auto-reply move_count" "2" "$(json_get "${BODY}" "len(d['moves'])")"
check "auto-reply first ply" "e4" "$(json_get "${BODY}" "d['moves'][0]['san']")"
check "version chain" "$((VER + 2))" "$(json_get "${BODY}" "d['version']")"
VER="$(json_get "${BODY}" "d['version']")"
echo "ok: engine replied with $(json_get "${BODY}" "d['moves'][1]['san']")"

# --- Resign and confirm the result is attributed against the player ----------
code=$(curl -s -o "${BODY}" -w "%{http_code}" -b "${JAR}" \
  -X POST "${API_BASE}/api/v1/games/${GID}/resign")
check "resign" 200 "${code}"
check "resign status" "resigned" "$(json_get "${BODY}" "d['status']")"
check "resign result" "0-1" "$(json_get "${BODY}" "d['result']")"
check "resign winner" "black" "$(json_get "${BODY}" "d['winner']")"

# --- Export PGN and assert the result tag + the played move ------------------
code=$(curl -s -o "${BODY}" -w "%{http_code}" -b "${JAR}" \
  "${API_BASE}/api/v1/games/${GID}/pgn")
check "pgn fetch" 200 "${code}"
grep -q '\[Result "0-1"\]' "${BODY}" || { echo "FAIL: PGN missing [Result \"0-1\"]" >&2; exit 1; }
grep -q '1\. e4' "${BODY}" || { echo "FAIL: PGN missing the played move 1. e4" >&2; exit 1; }
echo "ok: pgn carries result + move text"

echo "SMOKE PASS: ${API_BASE}"
