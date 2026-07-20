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

usage() {
  cat <<'EOF'
Usage: scripts/catalyst-mvp.sh [--fake] {up|seed|health|boot|down|reset}

  --fake  Start the deterministic fake model router (recommended for first boot).
  up      Start the Catalyst MVP services.
  seed    Load the pinned synthetic OpenELIS viral-load fixture.
  health  Run the full MVP health and provenance gate.
  boot    Run up, seed, and health in sequence.
  down    Stop the disposable MVP services.
  reset   Remove the disposable MVP state.
EOF
}

fake_backend=false
if [[ "${1:-}" == "--fake" ]]; then
  fake_backend=true
  shift
fi

command_name="${1:-}"
if [[ $# -ne 1 ]] || [[ ! "${command_name}" =~ ^(up|seed|health|boot|down|reset)$ ]]; then
  usage >&2
  exit 2
fi

if ! git -C "${CATALYST_DIR}" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "ERROR: Catalyst is not initialized at ${CATALYST_DIR}." >&2
  echo "Run: git submodule update --init targets/catalyst" >&2
  exit 1
fi

if [[ -n "$(git -C "${CATALYST_DIR}" ls-tree HEAD .gitmodules)" ]]; then
  echo "ERROR: the pinned Catalyst revision declares nested Git submodules." >&2
  echo "Use a Catalyst revision with runtime bootstrap dependencies instead." >&2
  exit 1
fi

if ! git -C "${HUB_DIR}" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "ERROR: med-agent-hub is not initialized at ${HUB_DIR}." >&2
  echo "Run: git submodule update --init targets/med-agent-hub" >&2
  exit 1
fi

# The harness owns both product pins. Build the sibling Hub checkout directly;
# standalone Catalyst runs retain their own same-commit fallback bootstrap.
export MED_AGENT_HUB_CONTEXT="${HUB_DIR}"

run_catalyst() {
  local script_name="$1"
  if [[ "${fake_backend}" == true ]] && [[ "${script_name}" == "mvp-up.sh" ]]; then
    MVP_FAKE_BACKEND=true "${CATALYST_DIR}/scripts/${script_name}"
  else
    "${CATALYST_DIR}/scripts/${script_name}"
  fi
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
  down) run_catalyst mvp-down.sh ;;
  reset) run_catalyst mvp-reset.sh ;;
esac
