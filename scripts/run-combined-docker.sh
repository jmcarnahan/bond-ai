#!/usr/bin/env bash
#
# Run the combined Docker image locally (frontend + backend in one container).
#
# Usage:
#   ./scripts/run-combined-docker.sh                 # build Flutter + Docker, then run
#   ./scripts/run-combined-docker.sh --skip-flutter  # skip Flutter build (use existing)
#   ./scripts/run-combined-docker.sh --rebuild       # force Docker rebuild (no cache)
#
# Press Ctrl+C to stop. Container is automatically removed on exit.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

IMAGE_NAME="bond-ai-combined"
CONTAINER_NAME="bond-ai-combined-local"
PORT="${PORT:-8080}"

SKIP_FLUTTER=false
DOCKER_BUILD_FLAGS=""

for arg in "$@"; do
  case "$arg" in
    --skip-flutter) SKIP_FLUTTER=true ;;
    --rebuild)      DOCKER_BUILD_FLAGS="--no-cache" ;;
    *)              echo "Unknown option: $arg"; exit 1 ;;
  esac
done

cd "$PROJECT_ROOT"

# --- Flutter build ---
if [ "$SKIP_FLUTTER" = false ]; then
  echo "========================================="
  echo "Building Flutter web app..."
  echo "========================================="
  cd flutterui
  flutter build web --release \
    --no-tree-shake-icons \
    --dart-define=API_BASE_URL=/rest \
    --dart-define=ENABLE_AGENTS=true
  cd "$PROJECT_ROOT"
  echo "✓ Flutter build complete"
else
  if [ ! -f "flutterui/build/web/index.html" ]; then
    echo "Error: flutterui/build/web/index.html not found."
    echo "Run without --skip-flutter first, or build Flutter manually."
    exit 1
  fi
  echo "Skipping Flutter build (using existing)"
fi

# --- Docker build ---
echo ""
echo "========================================="
echo "Building Docker image '$IMAGE_NAME'..."
echo "========================================="
docker build $DOCKER_BUILD_FLAGS \
  -f deployment/Dockerfile.combined \
  -t "$IMAGE_NAME" .
echo "✓ Docker build complete"

# --- Clean up any previous container ---
docker rm -f "$CONTAINER_NAME" 2>/dev/null || true

# --- Build env flags from .env ---
# Docker's --env-file can't handle multi-line values (e.g. BOND_MCP_CONFIG).
# We source the .env (shell handles quoting/multi-line), extract the variable
# names, and pass each one to Docker via -e VAR (which reads from the current
# shell environment).
DOCKER_ENV_FLAGS=()
if [ -f .env ]; then
  set -a
  source .env
  set +a

  # Extract variable names from .env (lines that start with VAR_NAME=)
  while IFS= read -r varname; do
    [ -n "$varname" ] && DOCKER_ENV_FLAGS+=("-e" "$varname")
  done < <(grep -oE '^[A-Za-z_][A-Za-z0-9_]*=' .env | tr -d '=' | sort -u)
fi

# --- Run ---
echo ""
echo "========================================="
echo "Starting $CONTAINER_NAME on port $PORT"
echo "========================================="
echo ""
echo "  Frontend:  http://localhost:$PORT/"
echo "  Health:    http://localhost:$PORT/health"
echo "  API:       http://localhost:$PORT/rest/"
echo ""
echo "  Press Ctrl+C to stop."
echo "========================================="
echo ""

# Override OAuth redirect URIs for the combined container.
# The .env values point to localhost:8000 (direct Uvicorn) and localhost:5000
# (Flutter dev server), but in Docker everything runs behind Nginx on $PORT.
# We export these overrides so the -e VARNAME flags in DOCKER_ENV_FLAGS pick
# up the correct values (Docker reads from the host's shell environment).
LOCAL_ORIGIN="http://localhost:$PORT"
export OKTA_REDIRECT_URI="$LOCAL_ORIGIN/auth/okta/callback"
export COGNITO_REDIRECT_URI="$LOCAL_ORIGIN/auth/cognito/callback"
export GOOGLE_AUTH_REDIRECT_URI="$LOCAL_ORIGIN/auth/google/callback"
export JWT_REDIRECT_URI="$LOCAL_ORIGIN"

# Rewrite BOND_MCP_CONFIG for Docker:
# - MCP server URLs use localhost/127.0.0.1 to reach services on the host.
#   Inside Docker, localhost = the container, so we replace with
#   host.docker.internal (Docker's magic hostname for the host machine).
# - OAuth redirect_uri values must stay as localhost (browser navigates to
#   them), but need port updated from 8000 to $PORT.
#
# Strategy: save redirect_uri ports with a placeholder, rewrite all
# localhost→host.docker.internal, then restore redirect_uri as localhost.
if [ -n "${BOND_MCP_CONFIG:-}" ]; then
  BOND_MCP_CONFIG="${BOND_MCP_CONFIG//localhost:8000/__REDIRECT_PLACEHOLDER__}"
  BOND_MCP_CONFIG="${BOND_MCP_CONFIG//127.0.0.1/host.docker.internal}"
  BOND_MCP_CONFIG="${BOND_MCP_CONFIG//localhost/host.docker.internal}"
  BOND_MCP_CONFIG="${BOND_MCP_CONFIG//__REDIRECT_PLACEHOLDER__/localhost:$PORT}"
  export BOND_MCP_CONFIG
fi

# Mount host /tmp so the SQLite metadata DB (/tmp/.metadata.db) is shared
# between Docker and non-Docker runs. Without this, each environment uses
# a separate DB, orphaning agents already created in Bedrock.
docker run --rm \
  --name "$CONTAINER_NAME" \
  -p "$PORT:8080" \
  -v /tmp:/tmp \
  "${DOCKER_ENV_FLAGS[@]}" \
  -e PORT=8080 \
  "$IMAGE_NAME"
