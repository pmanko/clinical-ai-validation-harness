#!/usr/bin/env bash
# Rebuild and verify the shared project-status workspace without any agent-specific tooling.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
status_dir="${root}/specs/artifacts/project-status"

usage() {
  cat <<'EOF'
Usage: scripts/project-status.sh {github|render|check|refresh|worktrees|prune-worktrees}

github          Print live GitHub collection commands for the open PR inventory.
render          Regenerate Markdown and CSV views from the status JSON records.
check           Verify generated views and run the dashboard model test and production build.
refresh         Run render, then check.
worktrees       Show all registered worktrees, including stale registrations.
prune-worktrees Remove only registrations for directories that are already missing.
EOF
}

github() {
  cat <<'EOF'
Run each command, review its output, then update pull-requests.json with the
new head, mergeability, checks, and a dated evidence summary before `refresh`.

First discover current work instead of assuming yesterday's PR numbers:

for repo in pmanko/clinical-ai-validation-harness DIGI-UW/catalyst-ai pmanko/med-agent-hub DIGI-UW/openelis-work pmanko/openmrs-module-chartsearchai; do
  gh pr list --repo "$repo" --state open --limit 100 --json number,title,author,headRefName,headRefOid,baseRefName,isDraft,mergeable,updatedAt,url
done
for repo in openmrs/openmrs-module-chartsearchai openmrs/openmrs-module-querystore openmrs/openmrs-esm-chartsearchai DIGI-UW/OpenELIS-Global-2; do
  gh pr list --repo "$repo" --author pmanko --state open --limit 100 --json number,title,author,headRefName,headRefOid,baseRefName,isDraft,mergeable,updatedAt,url
done

For each active PR, read its files and checks on the same head. Examples:

gh pr view 117 --repo DIGI-UW/catalyst-ai --json headRefOid,mergeStateStatus,mergeable,updatedAt,statusCheckRollup,files
gh pr view 68 --repo openmrs/openmrs-module-querystore --json headRefOid,mergeStateStatus,mergeable,updatedAt,statusCheckRollup
gh pr view 23 --repo openmrs/openmrs-esm-chartsearchai --json headRefOid,mergeStateStatus,mergeable,updatedAt,statusCheckRollup
gh pr view 157 --repo openmrs/openmrs-module-chartsearchai --json headRefOid,mergeStateStatus,mergeable,updatedAt,statusCheckRollup
EOF
}

render() {
  python3 "${status_dir}/render.py"
}

check() {
  python3 "${status_dir}/render.py" --check
  npm --prefix "${root}/site" run status:test
  npm --prefix "${root}/site" run status:build
}

case "${1:-}" in
  github) github ;;
  render) render ;;
  check) check ;;
  refresh) render; check ;;
  worktrees) git -C "${root}" worktree list --porcelain ;;
  prune-worktrees) git -C "${root}" worktree prune ;;
  *) usage >&2; exit 2 ;;
esac
