#!/usr/bin/env bash
# Harness entry point for the pinned Catalyst query-to-table MVP.
#
# Catalyst and med-agent-hub are sibling target submodules. Other local
# bootstrap dependencies remain disposable checkouts, never nested submodules.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CATALYST_DIR="${ROOT_DIR}/targets/catalyst"
HUB_DIR="${ROOT_DIR}/targets/med-agent-hub"
DEFAULT_MVP_COMPOSE_OVERRIDE_FILE="${ROOT_DIR}/compose/catalyst-mvp-isolated.override.yml"

MVP_COMPOSE_OVERRIDE_FILE="${MVP_COMPOSE_OVERRIDE_FILE:-${DEFAULT_MVP_COMPOSE_OVERRIDE_FILE}}"
if [[ ! -f "${MVP_COMPOSE_OVERRIDE_FILE}" ]]; then
  echo "ERROR: Catalyst MVP compose override does not exist: ${MVP_COMPOSE_OVERRIDE_FILE}" >&2
  exit 1
fi
MVP_COMPOSE_OVERRIDE_FILE="$(
  cd "$(dirname "${MVP_COMPOSE_OVERRIDE_FILE}")"
  printf '%s/%s\n' "$(pwd -P)" "$(basename "${MVP_COMPOSE_OVERRIDE_FILE}")"
)"
export MVP_COMPOSE_OVERRIDE_FILE

# The tracked override intentionally moves the OpenELIS TLS endpoints away
# from the default stack. Keep the URLs used by seed/health aligned with those
# published ports while still allowing callers to supply explicit values.
if [[ "${MVP_COMPOSE_OVERRIDE_FILE}" == "${DEFAULT_MVP_COMPOSE_OVERRIDE_FILE}" ]]; then
  export GATEWAY_PORT="${GATEWAY_PORT:-18000}"
  export CATALYST_UI_PORT="${CATALYST_UI_PORT:-13000}"
  export ANALYTICS_DB_PORT="${ANALYTICS_DB_PORT:-15443}"
  export DATA_PIPES_PORT="${DATA_PIPES_PORT:-18090}"
  export MED_AGENT_HUB_PORT="${MED_AGENT_HUB_PORT:-18082}"
  export OPENELIS_HTTPS_PORT="${OPENELIS_HTTPS_PORT:-28443}"
  export HAPI_HTTPS_PORT="${HAPI_HTTPS_PORT:-28444}"
  export SUPERSET_PORT="${SUPERSET_PORT:-18088}"
fi

usage() {
  cat <<'EOF'
Usage: scripts/catalyst-mvp.sh {up|seed|health|boot|restart|down|reset|superset-status|superset-import}

  up       Start the Catalyst services against the external model router without changing persisted data.
  seed     Explicitly reload the pinned synthetic OpenELIS fixture and FHIR mart.
  health   Run the full MVP health and provenance gate.
  boot     First-time initialization: run up, seed, and health in sequence.
  restart  Stop then start services while retaining all named volumes; does not seed.
  down     Stop the disposable MVP services while retaining all named volumes.
  reset    Remove the disposable MVP state and volumes.
  superset-status  Show the published-bundle import state for this isolated stack.
  superset-import  Import the current published Catalyst bundle into this isolated Superset.
EOF
}

command_name="${1:-}"
if [[ $# -ne 1 ]] || [[ ! "${command_name}" =~ ^(up|seed|health|boot|restart|down|reset|superset-status|superset-import)$ ]]; then
  usage >&2
  exit 2
fi

require_pinned_clean_target() {
  local label="$1"
  local relative_path="$2"
  local target_dir="${ROOT_DIR}/${relative_path}"
  local expected actual target_top

  target_top="$(git -C "${target_dir}" rev-parse --show-toplevel 2>/dev/null || true)"
  if [[ "${target_top}" != "${target_dir}" ]]; then
    echo "ERROR: ${label} is not initialized at ${target_dir}." >&2
    echo "Run: git submodule update --init ${relative_path}" >&2
    exit 1
  fi
  expected="$(git -C "${ROOT_DIR}" rev-parse "HEAD:${relative_path}")"
  actual="$(git -C "${target_dir}" rev-parse HEAD)"
  if [[ "${actual}" != "${expected}" ]]; then
    echo "ERROR: ${label} is at ${actual}; the harness pins ${expected}." >&2
    echo "Run: git submodule update --init ${relative_path}" >&2
    exit 1
  fi
  if [[ -n "$(git -C "${target_dir}" status --porcelain)" ]]; then
    echo "ERROR: ${label} has uncommitted changes at ${target_dir}." >&2
    exit 1
  fi
}

require_pinned_clean_target "Catalyst" "targets/catalyst"

if [[ -n "$(git -C "${CATALYST_DIR}" ls-tree HEAD .gitmodules)" ]]; then
  echo "ERROR: the pinned Catalyst revision declares nested Git submodules." >&2
  echo "Use a Catalyst revision with runtime bootstrap dependencies instead." >&2
  exit 1
fi

require_pinned_clean_target "med-agent-hub" "targets/med-agent-hub"

# The harness owns both product pins. Build the sibling Hub checkout directly;
# standalone Catalyst runs retain their own same-commit fallback bootstrap.
export MED_AGENT_HUB_CONTEXT="${HUB_DIR}"

run_catalyst() {
  local script_name="$1"
  "${CATALYST_DIR}/scripts/${script_name}"
}

case "${command_name}" in
  up) run_catalyst mvp-up.sh ;;
  seed) run_catalyst mvp-seed.sh ;;
  health) run_catalyst mvp-health.sh ;;
  boot)
    run_catalyst mvp-up.sh
    run_catalyst mvp-seed.sh
    run_catalyst mvp-health.sh
    ;;
  restart)
    run_catalyst mvp-down.sh
    run_catalyst mvp-up.sh
    ;;
  down) run_catalyst mvp-down.sh ;;
  reset) run_catalyst mvp-reset.sh ;;
  superset-status) run_catalyst mvp-superset.sh status ;;
  superset-import) run_catalyst mvp-superset.sh import ;;
esac
