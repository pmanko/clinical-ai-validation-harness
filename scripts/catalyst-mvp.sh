#!/usr/bin/env bash
# Harness entry point for the pinned Catalyst query-to-table MVP.
#
# Catalyst is a sibling target submodule. Its local bootstrap dependencies are
# deliberately disposable Git checkouts, not nested submodules of Catalyst.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CATALYST_DIR="${ROOT_DIR}/targets/catalyst"

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
