#!/usr/bin/env bash
# Compatibility entry point retained for the stage-refactor roadmap. The hub
# consolidation matrix supersedes the old duplicate 14-gate implementation and
# is now the single source of release-gate truth.

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec "${ROOT}/scripts/verify-hub-consolidation-gates.sh" "$@"
