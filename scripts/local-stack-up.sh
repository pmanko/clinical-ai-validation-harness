#!/usr/bin/env bash
# One-shot local dev bring-up after a reboot or Docker Desktop restart.
#
# Assumes the one-time setup is already done: Homebrew, Docker Desktop, uv,
# Maven/Java, Node/yarn, llama.cpp installed; chartsearchai/querystore .omod
# files and the chartsearchai ESM bundle already built into artifacts/;
# .env.chartsearch configured; querystore backend already switched to
# elasticsearch with bootstrap.autostart. This script does NOT rebuild any of
# that — it just starts the processes/containers so the stack (and the
# already-indexed patient data) comes back up as it was.
#
# Re-run anytime; every step is idempotent.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

echo "==> Loading Homebrew environment"
if [ -x /opt/homebrew/bin/brew ]; then
  eval "$(/opt/homebrew/bin/brew shellenv)"
fi

echo "==> Checking Docker Desktop"
if ! docker info >/dev/null 2>&1; then
  echo "    starting Docker Desktop..."
  open -a Docker
  echo -n "    waiting for the daemon"
  until docker info >/dev/null 2>&1; do
    echo -n "."
    sleep 2
  done
  echo
fi
echo "    docker is up"

echo "==> Checking llama-router (:8077)"
if curl -fsS -m 2 http://localhost:8077/v1/models >/dev/null 2>&1; then
  echo "    already running"
else
  command -v llama-server >/dev/null 2>&1 || {
    echo "ERROR: llama-server not on PATH (brew install llama.cpp)" >&2
    exit 1
  }
  echo "    starting in background (log: /tmp/llama-router.log)"
  nohup env LLAMA_ROUTER_MODELS_MAX="${LLAMA_ROUTER_MODELS_MAX:-4}" \
    "${ROOT}/scripts/llama-router-up.sh" >/tmp/llama-router.log 2>&1 &
  disown
  for _ in $(seq 1 15); do
    curl -fsS -m 2 http://localhost:8077/v1/models >/dev/null 2>&1 && break
    sleep 1
  done
fi

echo "==> Bringing up the Docker Compose stack"
set -a
[ -f .env.chartsearch ] && . ./.env.chartsearch
set +a
docker compose -f compose/openmrs-2.8-refapp.yml up -d

echo "==> Waiting for the OpenMRS backend to become healthy"
observed=0
for i in $(seq 1 60); do
  status=$(docker inspect -f '{{.State.Health.Status}}' harness-openmrs-backend 2>/dev/null || echo starting)
  if [ "${status}" = "healthy" ]; then
    echo "    healthy after $((i * 5))s"
    observed=1
    break
  fi
  sleep 5
done
if [ "${observed}" != "1" ]; then
  echo "WARNING: backend not healthy after 5 min — check: docker compose -f compose/openmrs-2.8-refapp.yml logs backend" >&2
fi

cat <<EOF

Stack is up:
  OpenMRS SPA:   http://localhost:8088/openmrs/spa   (admin / Admin123)
  llama-router:  http://localhost:8077/v1/models
  Elasticsearch: http://localhost:9200/_cat/indices?v

Stop everything with: scripts/local-stack-down.sh
EOF
