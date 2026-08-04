#!/usr/bin/env bash
set -euo pipefail

ROOT="${HARNESS_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
MVN_BIN="${MVN_BIN:-mvn}"

verify_integration_head() {
  local repo="$1"
  local label="$2"
  local gitlink_path="$3"
  local head
  local integration
  local gitlink

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

  gitlink="$(git -C "${ROOT}" rev-parse "HEAD:${gitlink_path}")"
  if [[ "${head}" != "${gitlink}" ]]; then
    echo "${label}: HEAD ${head} does not match parent gitlink ${gitlink}" >&2
    return 1
  fi
  if [[ -n "$(git -C "${repo}" status --porcelain --untracked-files=all)" ]]; then
    echo "${label}: source tree is dirty" >&2
    return 1
  fi

  echo "${label}: ${head}"
}

verify_integration_head "${ROOT}/targets/querystore" "Querystore" "targets/querystore"
verify_integration_head "${ROOT}/targets/chartsearchai" "ChartSearchAI" "targets/chartsearchai"
verify_integration_head "${ROOT}/targets/chartsearchai-esm" "ChartSearchAI ESM" "targets/chartsearchai-esm"

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
