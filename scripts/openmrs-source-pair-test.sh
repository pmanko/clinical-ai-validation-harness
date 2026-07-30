#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MVN_BIN="${MVN_BIN:-mvn}"

verify_integration_head() {
  local repo="$1"
  local label="$2"
  local head
  local integration

  if ! git -C "${repo}" show-ref --verify --quiet refs/remotes/origin/harness-integration; then
    echo "${label}: origin/harness-integration is not available; fetch the submodule remote first" >&2
    return 1
  fi

  head="$(git -C "${repo}" rev-parse HEAD)"
  integration="$(git -C "${repo}" rev-parse origin/harness-integration)"
  if [[ "${head}" != "${integration}" ]]; then
    echo "${label}: HEAD ${head} does not match origin/harness-integration ${integration}" >&2
    return 1
  fi

  echo "${label}: ${head}"
}

verify_integration_head "${ROOT}/targets/querystore" "Querystore"
verify_integration_head "${ROOT}/targets/chartsearchai" "ChartSearchAI"
verify_integration_head "${ROOT}/targets/chartsearchai-esm" "ChartSearchAI ESM"

echo "==> installing the pinned Querystore source"
(
  cd "${ROOT}/targets/querystore"
  "${MVN_BIN}" -q -B clean install
)

echo "==> building the pinned ChartSearchAI source against that Querystore artifact"
(
  cd "${ROOT}/targets/chartsearchai"
  "${MVN_BIN}" -q -B clean package
)

echo "OpenMRS source-pair build passed."
