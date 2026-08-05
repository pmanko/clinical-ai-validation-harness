#!/usr/bin/env bash
set -euo pipefail

ROOT="${HARNESS_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
allow_harness_branch=0
check_publication_prs=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --allow-harness-branch)
      allow_harness_branch=1
      ;;
    --check-publication-prs)
      check_publication_prs=1
      ;;
    *)
      printf 'Usage: %s [--allow-harness-branch] [--check-publication-prs]\n' \
        "${0##*/}" >&2
      exit 2
      ;;
  esac
  shift
done

fail() {
  printf 'ERROR: %s\n' "$1" >&2
  exit 1
}

require_clean_remote_commit() {
  local repo="$1"
  local label="$2"

  [[ -e "$repo/.git" ]] || fail "$label is not an initialized Git worktree"
  [[ -z "$(git -C "$repo" status --porcelain --untracked-files=all)" ]] \
    || fail "$label source tree is dirty"
  git -C "$repo" branch -r --contains HEAD | grep -q 'origin/' \
    || fail "$label HEAD is not available from its origin remote"
}

require_parent_pin() {
  local repo="$1"
  local label="$2"
  local path="$3"
  local head
  local pin

  head="$(git -C "$repo" rev-parse HEAD)"
  pin="$(git -C "$ROOT" rev-parse "HEAD:$path")"
  [[ "$head" == "$pin" ]] \
    || fail "$label checkout $head does not match the harness pin $pin"
}

require_exact_integration_head() {
  local repo="$1"
  local label="$2"
  local path="$3"

  git -C "$repo" show-ref --verify --quiet refs/remotes/origin/harness-integration \
    || fail "$label is missing origin/harness-integration; fetch its remote"
  require_parent_pin "$repo" "$label" "$path"
  [[ "$(git -C "$repo" rev-parse HEAD)" == \
     "$(git -C "$repo" rev-parse origin/harness-integration)" ]] \
    || fail "$label does not match origin/harness-integration"
}

require_main_commit() {
  local repo="$1"
  local label="$2"
  local path="${3:-}"

  git -C "$repo" show-ref --verify --quiet refs/remotes/origin/main \
    || fail "$label is missing origin/main; fetch its remote"
  git -C "$repo" merge-base --is-ancestor HEAD origin/main \
    || fail "$label HEAD has not been merged into origin/main"
  if [[ -n "$path" ]]; then
    require_parent_pin "$repo" "$label" "$path"
  fi
}

require_integration_publication() {
  local repo="$1"
  local path="$2"
  local label="$3"
  local head
  local publication
  local duplicate

  command -v gh >/dev/null 2>&1 \
    || fail "GitHub CLI is required for --check-publication-prs"
  head="$(git -C "$ROOT/$path" rev-parse origin/harness-integration)"
  publication="$(gh pr list \
    --repo "$repo" \
    --head pmanko:harness-integration \
    --base main \
    --state all \
    --limit 100 \
    --json number,state,headRefOid,url \
    --jq ".[] | select(.headRefOid == \"$head\") | [.number, .state, .url] | @tsv")"
  [[ -n "$publication" ]] \
    || fail "$label integration head $head has no OpenMRS PR from pmanko:harness-integration"

  duplicate="$(gh pr list \
    --repo "$repo" \
    --author pmanko \
    --base main \
    --state open \
    --limit 100 \
    --json number,headRefName,headRefOid,url \
    --jq ".[] | select(.headRefOid == \"$head\" and .headRefName != \"harness-integration\") | [.number, .headRefName, .url] | @tsv")"
  [[ -z "$duplicate" ]] \
    || fail "$label integration head is also published from a feature branch: $duplicate"

  printf '%s publication: %s\n' "$label" "$publication"
}

require_clean_remote_commit "$ROOT" "validation harness"
if [[ "$allow_harness_branch" == 0 ]]; then
  require_main_commit "$ROOT" "validation harness"
fi

for spec in \
  "targets/chartsearchai|ChartSearchAI" \
  "targets/chartsearchai-esm|ChartSearchAI ESM" \
  "targets/querystore|QueryStore"; do
  path="${spec%%|*}"
  label="${spec#*|}"
  require_clean_remote_commit "$ROOT/$path" "$label"
  require_exact_integration_head "$ROOT/$path" "$label" "$path"
done

if [[ "$check_publication_prs" == 1 ]]; then
  for spec in \
    "openmrs/openmrs-module-chartsearchai|targets/chartsearchai|ChartSearchAI" \
    "openmrs/openmrs-esm-chartsearchai|targets/chartsearchai-esm|ChartSearchAI ESM" \
    "openmrs/openmrs-module-querystore|targets/querystore|QueryStore"; do
    repo="${spec%%|*}"
    remainder="${spec#*|}"
    path="${remainder%%|*}"
    label="${remainder#*|}"
    require_integration_publication "$repo" "$path" "$label"
  done
fi

require_clean_remote_commit "$ROOT/targets/med-agent-hub" "med-agent-hub"
require_main_commit \
  "$ROOT/targets/med-agent-hub" "med-agent-hub" "targets/med-agent-hub"

for spec in \
  "targets/catalyst|Catalyst" \
  "targets/openmrs_chatbot|openmrs_chatbot"; do
  path="${spec%%|*}"
  label="${spec#*|}"
  require_clean_remote_commit "$ROOT/$path" "$label"
  require_parent_pin "$ROOT/$path" "$label" "$path"
done

printf 'Repository lines match the approved ownership policy.\n'
