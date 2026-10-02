#!/usr/bin/env bash
# Check local Markdown references and accidental infrastructure identifiers.
# Product semantics and editorial clarity require code/evidence review; exact
# wording, feature phases and delivery arrangements are not executable contracts.
set -euo pipefail
cd "$(dirname "$0")/.."

fail=0
err() { echo "FAIL: $*" >&2; fail=1; }

if [ -n "${DOCS_SECRET_SCAN_PATH:-}" ]; then
  SECRET_PATHS=("${DOCS_SECRET_SCAN_PATH}")
else
  SECRET_PATHS=(
    README.md
    AGENTS.md
    .claude
    specs
    catalyst-sources
  )
fi
if grep -rIhnE '[0-9]{1,3}(\.[0-9]{1,3}){3}/32|sgr-[0-9a-f]{8,}' -- "${SECRET_PATHS[@]}"; then
  err "harness documentation contains a concrete /32 address or security-group rule id"
else
  status=$?
  [ "$status" -eq 1 ] || err "could not scan harness documentation for infrastructure identifiers"
fi

if [ "${DOCS_SKIP_LINK_CHECK:-0}" != "1" ]; then
  if [ -n "${DOCS_LINK_FILES:-}" ]; then
    IFS=':' read -r -a LINK_FILES <<<"${DOCS_LINK_FILES}"
    python3 scripts/verify-local-markdown-links.py "${LINK_FILES[@]}" || fail=1
  else
    python3 scripts/verify-local-markdown-links.py || fail=1
  fi
fi

if [ "$fail" -ne 0 ]; then
  exit 1
fi
echo "docs consistency: OK"
