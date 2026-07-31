#!/usr/bin/env bash
# One-shot local dev bring-up after a reboot or Docker Desktop restart.
#
# Fast-resume path: assumes `make chartsearchai-local` (or an equivalent
# first build) already ran — chartsearchai/querystore .omod files, the
# chartsearchai ESM bundle, and .env.chartsearch all already exist. This
# script does NOT build, rebuild, or reconfigure anything; it only starts
# what's already built, as fast as possible, and fails loudly instead of
# reporting a partially-working stack as success.
#
# Use `make chartsearchai-local` instead whenever source under targets/
# changed, or for first-time setup.
#
# Re-run anytime; every step is idempotent.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

say() { printf '%s\n' "$*"; }
fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

wait_http() {
  local label="$1" url="$2" timeout="$3" elapsed=0
  until curl -fsS --max-time 3 "${url}" >/dev/null 2>&1; do
    if [ "${elapsed}" -ge "${timeout}" ]; then
      fail "${label} was not ready after ${timeout}s (${url})"
    fi
    sleep 2
    elapsed=$((elapsed + 2))
  done
  say "    ${label}: ready"
}

wait_container() {
  local label="$1" container="$2" timeout="$3" elapsed=0 status
  while true; do
    status="$(docker inspect -f '{{.State.Health.Status}}' "${container}" 2>/dev/null || echo starting)"
    if [ "${status}" = "healthy" ]; then
      say "    ${label}: healthy"
      return
    fi
    if [ "${status}" = "unhealthy" ]; then
      fail "${label} reported unhealthy; inspect: docker logs ${container}"
    fi
    if [ "${elapsed}" -ge "${timeout}" ]; then
      fail "${label} was not healthy after ${timeout}s (last status: ${status})"
    fi
    sleep 5
    elapsed=$((elapsed + 5))
  done
}

[ -f .env.chartsearch ] || fail ".env.chartsearch not found. Copy .env.chartsearch.example and edit it, or run 'make chartsearchai-local' for first-time setup."
set -a
# shellcheck disable=SC1091
. ./.env.chartsearch
set +a

command -v docker >/dev/null 2>&1 || fail "docker not found on PATH"
command -v git >/dev/null 2>&1 || fail "git not found on PATH"
[ -d targets/med-agent-hub/.git ] || [ -f targets/med-agent-hub/.git ] \
  || fail "targets/med-agent-hub submodule not initialized (run: git submodule update --init)"
HUB_BUILD_REVISION="$(git -C targets/med-agent-hub rev-parse HEAD)"
export HUB_BUILD_REVISION

say "==> Loading Homebrew environment"
if [ -x /opt/homebrew/bin/brew ]; then
  eval "$(/opt/homebrew/bin/brew shellenv)"
fi

say "==> Checking Docker Desktop"
if ! docker info >/dev/null 2>&1; then
  say "    starting Docker Desktop..."
  open -a Docker 2>/dev/null || fail "Docker is not running and 'open -a Docker' failed — start Docker Desktop manually and re-run."
  elapsed=0
  until docker info >/dev/null 2>&1; do
    if [ "${elapsed}" -ge 120 ]; then
      fail "Docker did not become ready after 120s — check Docker Desktop."
    fi
    sleep 2
    elapsed=$((elapsed + 2))
  done
fi
say "    docker: ready"

mkdir -p artifacts/llama-router
ROUTER_URL="http://localhost:8077"
ROUTER_PID_FILE="${ROOT}/artifacts/llama-router/router.pid"

say "==> Checking llama-router (:8077)"
if curl -fsS -m 2 "${ROUTER_URL}/v1/models" >/dev/null 2>&1; then
  say "    already running"
else
  command -v llama-server >/dev/null 2>&1 || fail "llama-server not on PATH (brew install llama.cpp)"
  say "    starting in background (log: artifacts/llama-router/router.log)"
  nohup env LLAMA_ROUTER_MODELS_MAX="${LLAMA_ROUTER_MODELS_MAX:-2}" \
    "${ROOT}/scripts/llama-router-up.sh" \
    >artifacts/llama-router/router.log 2>&1 &
  echo "$!" >"${ROUTER_PID_FILE}"
  wait_http "llama-router" "${ROUTER_URL}/v1/models" 60
fi

say "==> Bringing up the Docker Compose stack (no build — fast-resume only)"
./scripts/stack-up.sh --no-build \
  || fail "stack-up.sh failed — an image may be missing. Run 'make chartsearchai-local' to build it first."

wait_container "OpenMRS backend" harness-openmrs-backend 300
wait_http "OpenMRS proxy" "http://127.0.0.1:${HARNESS_PROXY_HTTP_PORT:-8088}/__proxy_health" 120

cat <<EOF

Stack is up:
  OpenMRS SPA:   http://localhost:${HARNESS_PROXY_HTTP_PORT:-8088}/openmrs/spa   (admin / Admin123)
  llama-router:  ${ROUTER_URL}/v1/models
  Elasticsearch: http://localhost:9200/_cat/indices?v

Stop everything with: scripts/local-stack-down.sh
EOF
