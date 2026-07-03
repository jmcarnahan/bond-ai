#!/usr/bin/env bash
# verify-combined-stack.sh — verify bond-ai + bond-mcps are running and talking
# in local combined mode (nginx front door on :8000).
#
# Usage:
#   ./scripts/verify-combined-stack.sh          # run all checks
#   BOND_AI_ENV_FILE=.env.combined ./scripts/verify-combined-stack.sh
#
# Checks, shallowest to deepest:
#   1. Docker daemon + bond-ai-nginx-local container up
#   2. All expected ports listening (8000 nginx, 8002 backend, 18000-18004 bond-mcps)
#   3. Backend health through nginx           (:8000/health)
#   4. /rest/providers returns JSON            (nginx /rest proxy → backend)
#   5. MCP discovery through nginx             (:8000/connections/discovery)
#   6. Bare /connections serves the SPA        (OAuth return-trip route, no broken 301)
#   7. JWT trust seam: mint Bond JWTs with JWT_SECRET_KEY and call a bond-mcps
#      /connect/<name>/status directly — 401 without a token, 200/404 with the
#      session shape (aud=["bond-ai-api","mcp-server"]) AND with the narrow
#      server-mint shape (aud=["mcp-server"]) proves the HS256 shared-secret
#      contract (iss/aud/sub) is live end-to-end for both shapes bond-ai sends.
#
# Exit code 0 = all checks passed. Any failure prints a hint and exits 1.
#
# If checks fail, restart the stack:
#   bond-mcps:  cd ../bond-mcps && make dev-combined-jwt
#   bond-ai:    make stop && make dev-combined
# Full recipe: docs/verify-combined-stack.md and docs/local-dev-combined-mode.md §8.

set -u

REPO_ROOT="${BOND_AI_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
ENV_FILE="${BOND_AI_ENV_FILE:-$REPO_ROOT/.env}"
FRONT_DOOR="${FRONT_DOOR:-http://localhost:8000}"
NGINX_CONTAINER="${NGINX_CONTAINER:-bond-ai-nginx-local}"
CURL="curl -s --max-time 5"

PASS=0
FAIL=0

ok()   { PASS=$((PASS+1)); printf '  \033[32mPASS\033[0m  %s\n' "$1"; }
bad()  { FAIL=$((FAIL+1)); printf '  \033[31mFAIL\033[0m  %s\n' "$1"; [ -n "${2:-}" ] && printf '        hint: %s\n' "$2"; }

echo "== bond-ai + bond-mcps combined-stack verification =="
echo

# --- 1. Docker + nginx container -------------------------------------------
if docker info >/dev/null 2>&1; then
  ok "Docker daemon running"
  status=$(docker ps --filter "name=$NGINX_CONTAINER" --format '{{.Status}}')
  if [ -n "$status" ]; then
    ok "nginx container '$NGINX_CONTAINER' up ($status)"
  else
    bad "nginx container '$NGINX_CONTAINER' not running" "run 'make dev-combined' (or 'make nginx')"
  fi
else
  bad "Docker daemon not running" "start Docker Desktop, then 'make dev-combined'"
fi

# --- 2. Ports ---------------------------------------------------------------
for entry in "8000:nginx front door" "8002:bond-ai backend" \
             "18000:bond-mcps auth server" "18001:microsoft MCP" \
             "18002:github MCP" "18003:atlassian MCP" "18004:databricks MCP"; do
  port=${entry%%:*}; name=${entry#*:}
  if lsof -nP -iTCP:"$port" -sTCP:LISTEN -t >/dev/null 2>&1; then
    ok "port :$port listening ($name)"
  else
    case $port in
      18*) hint="cd ../bond-mcps && make dev-combined-jwt" ;;
      *)   hint="make dev-combined" ;;
    esac
    bad "port :$port not listening ($name)" "$hint"
  fi
done

# --- 3. Backend health through nginx ----------------------------------------
code=$($CURL -o /dev/null -w '%{http_code}' "$FRONT_DOOR/health" 2>/dev/null)
if [ "$code" = "200" ]; then
  ok "backend health via nginx ($FRONT_DOOR/health → 200)"
else
  bad "backend health via nginx returned '$code'" "check tmp/logs/backend.log and 'make nginx-logs'"
fi

# --- 4. /rest/providers (nginx proxy sanity) ---------------------------------
out=$($CURL "$FRONT_DOOR/rest/providers" 2>/dev/null)
case "$out" in
  '{'*) ok "/rest/providers returns JSON (nginx /rest proxy → backend OK)" ;;
  '<'*) bad "/rest/providers returned HTML (SPA fallthrough)" "nginx /rest proxy isn't reaching the backend — see docs/local-dev-combined-mode.md" ;;
  '')   bad "/rest/providers returned nothing" "backend may still be starting; check tmp/logs/backend.log" ;;
  *)    bad "/rest/providers returned unexpected response: $(echo "$out" | head -c 60)" ;;
esac

# --- 5. MCP discovery through nginx ------------------------------------------
disco=$($CURL "$FRONT_DOOR/connections/discovery" 2>/dev/null)
case "$disco" in
  *'"mcps"'*)
    n=$(echo "$disco" | tr ',' '\n' | grep -c '"name"' || true)
    ok "MCP discovery via nginx ($n MCPs listed)" ;;
  *) bad "MCP discovery failed (got: $(echo "$disco" | head -c 60))" "is bond-mcps up? cd ../bond-mcps && make dev-combined-jwt" ;;
esac

# --- 6. Bare /connections serves the SPA (OAuth return trip) -----------------
code=$($CURL -o /dev/null -w '%{http_code}' "$FRONT_DOOR/connections" 2>/dev/null)
if [ "$code" = "200" ]; then
  ok "bare /connections serves SPA (OAuth return trip won't 301 to :8080)"
else
  bad "bare /connections returned '$code' (expected 200)" "nginx missing 'location = /connections' block — reload nginx: make nginx-reload"
fi

# --- 7. JWT trust seam (the real cross-repo proof) ---------------------------
# Mint a Bond JWT exactly as bond-ai does (HS256, sub=email, iss=bond-ai,
# aud includes mcp-server) and hit a bond-mcps connect status endpoint on its
# own port — the same call bond-ai's backend makes server-side. Accepted token
# (200, or 404 = "no connect surface") proves the shared-secret contract.
seam_target=""
if [ -n "$disco" ]; then
  # first discovered MCP: derive "name" and "base" (url with /mcp stripped)
  seam_target=$(echo "$disco" | tr '{' '\n' | grep '"url"' | head -1)
fi
if [ ! -f "$ENV_FILE" ]; then
  bad "env file '$ENV_FILE' not found — cannot run JWT seam check" "set BOND_AI_ENV_FILE or run from the repo root"
elif ! grep -q '^JWT_SECRET_KEY=' "$ENV_FILE"; then
  bad "JWT_SECRET_KEY not set in $ENV_FILE — cannot run JWT seam check"
elif [ -z "$seam_target" ]; then
  bad "no discovered MCP to run the JWT seam check against"
else
  name=$(echo "$seam_target" | sed -n 's/.*"name": *"\([^"]*\)".*/\1/p')
  base=$(echo "$seam_target" | sed -n 's/.*"url": *"\([^"]*\)\/mcp".*/\1/p')
  status_url="$base/connect/$name/status"

  # 7a. without a token the endpoint must reject (auth is actually enforced)
  code=$($CURL -o /dev/null -w '%{http_code}' "$status_url" 2>/dev/null)
  if [ "$code" = "401" ] || [ "$code" = "403" ]; then
    ok "bond-mcps rejects unauthenticated status call ($code)"
  else
    bad "unauthenticated $status_url returned '$code' (expected 401)" "is bond-mcps running in JWT mode? use 'make dev-combined-jwt', not 'make dev-combined'"
  fi

  # 7b. with a minted Bond JWT it must accept (shared secret + iss/aud align)
  secret=$(grep -E '^JWT_SECRET_KEY=' "$ENV_FILE" | head -1 | cut -d= -f2- | tr -d '"')
  # prefer the project venv's python (has pyjwt); fall back to poetry run
  if [ -x "$REPO_ROOT/.venv/bin/python" ]; then
    PY="$REPO_ROOT/.venv/bin/python"
  else
    PY="poetry run python"
  fi
  # Two token shapes, both real at runtime: forwarded user sessions carry
  # aud=["bond-ai-api","mcp-server"]; bond-ai's server-side mint (agent
  # tool-def fetch) carries aud=["mcp-server"] only. Test both.
  tokens=$(cd "$REPO_ROOT" && JWT_SEAM_SECRET="$secret" $PY -c "
import os, time, uuid, jwt
base = {'sub': 'verify-stack@example.com', 'iss': 'bond-ai',
        'exp': int(time.time()) + 300}
secret = os.environ['JWT_SEAM_SECRET']
print(jwt.encode({**base, 'aud': ['bond-ai-api', 'mcp-server'],
                  'jti': str(uuid.uuid4())}, secret, algorithm='HS256'))
print(jwt.encode({**base, 'aud': ['mcp-server'],
                  'jti': str(uuid.uuid4())}, secret, algorithm='HS256'))
" 2>/dev/null)
  token=$(echo "$tokens" | sed -n 1p)
  narrow=$(echo "$tokens" | sed -n 2p)
  if [ -z "$token" ] || [ -z "$narrow" ]; then
    bad "could not mint Bond JWTs" "run from the bond-ai repo root (needs 'poetry run python' + pyjwt)"
  else
    code=$($CURL -o /dev/null -w '%{http_code}' -H "Authorization: Bearer $token" "$status_url" 2>/dev/null)
    if [ "$code" = "200" ] || [ "$code" = "404" ]; then
      ok "bond-mcps accepts session-shape Bond JWT ($status_url → $code) — HS256 trust seam live"
    else
      bad "session-shape Bond JWT rejected ($status_url → $code)" "BOND_MCPS_JWT_SECRET in bond-mcps must equal JWT_SECRET_KEY in bond-ai's .env; iss=bond-ai, aud=mcp-server"
    fi
    # 7c. narrow mint shape (aud=["mcp-server"] only — what the server-side
    # mint sends). Requires BOND_MCPS_JWT_AUDIENCE=mcp-server on the MCPs.
    code=$($CURL -o /dev/null -w '%{http_code}' -H "Authorization: Bearer $narrow" "$status_url" 2>/dev/null)
    if [ "$code" = "200" ] || [ "$code" = "404" ]; then
      ok "bond-mcps accepts narrow (server-mint) Bond JWT ($status_url → $code)"
    else
      bad "narrow (server-mint) Bond JWT rejected ($status_url → $code)" "BOND_MCPS_JWT_AUDIENCE=mcp-server must be set on the MCPs (dev-combined-jwt sets it)"
    fi
  fi
fi

# --- summary ------------------------------------------------------------------
echo
echo "== $PASS passed, $FAIL failed =="
if [ "$FAIL" -gt 0 ]; then
  echo
  echo "Restart recipe:"
  echo "  1. cd ../bond-mcps && make dev-combined-jwt     # AS :18000, MCPs :18001-18004"
  echo "  2. cd -            && make stop && make dev-combined"
  echo "  3. re-run this script"
  exit 1
fi
echo "Stack verified. Manual OAuth round-trip test: open $FRONT_DOOR/ → Connections → Connect a tile."
