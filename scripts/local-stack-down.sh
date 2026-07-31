#!/usr/bin/env bash
# Stop the local dev stack started by scripts/local-stack-up.sh.
#
# Leaves Docker volumes intact (patient data, ES index, module state) so the
# next local-stack-up.sh brings everything back exactly as it was. Does not
# stop Docker Desktop itself or uninstall anything.
#
# Only stops a llama-router process this checkout started: it reads the PID
# recorded at artifacts/llama-router/router.pid (written by local-stack-up.sh
# or chartsearchai-local.sh) and verifies the process is actually a
# llama-server before killing it — never a broad `pkill -f`, which could
# match and kill an unrelated router from another checkout.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

say() { printf '%s\n' "$*"; }
fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

# docker compose interpolates the whole file for `down` too, and
# med-agent-hub's build.args.HUB_BUILD_REVISION is a required (`:?`)
# variable — without it, `down` fails with a cryptic Compose error instead
# of a clear one.
[ -f .env.chartsearch ] || fail ".env.chartsearch not found. Copy .env.chartsearch.example and edit it, or run 'make chartsearchai-local' for first-time setup."
set -a
# shellcheck disable=SC1091
. ./.env.chartsearch
set +a
[ -d targets/med-agent-hub/.git ] || [ -f targets/med-agent-hub/.git ] \
  || fail "targets/med-agent-hub submodule not initialized (run: git submodule update --init)"
HUB_BUILD_REVISION="$(git -C targets/med-agent-hub rev-parse HEAD)"
export HUB_BUILD_REVISION

say "==> Stopping the Docker Compose stack (volumes preserved)"
./scripts/stack-down.sh

say "==> Stopping llama-router"
ROUTER_PID_FILE="${ROOT}/artifacts/llama-router/router.pid"
if [ ! -f "${ROUTER_PID_FILE}" ]; then
  say "    no router.pid on record — nothing to stop"
else
  pid="$(cat "${ROUTER_PID_FILE}")"
  if [ -z "${pid}" ] || ! kill -0 "${pid}" 2>/dev/null; then
    say "    recorded pid ${pid:-<empty>} is not running — cleaning up stale pid file"
  else
    cmd="$(ps -p "${pid}" -o comm= 2>/dev/null || true)"
    case "${cmd}" in
      *llama-server*)
        kill "${pid}"
        say "    stopped llama-router (pid ${pid})"
        ;;
      *)
        say "    WARNING: pid ${pid} is not a llama-server process (comm=${cmd:-unknown}) — leaving it alone"
        ;;
    esac
  fi
  rm -f "${ROUTER_PID_FILE}"
fi

say "Done."
