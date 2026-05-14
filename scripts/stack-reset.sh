#!/usr/bin/env bash
# scripts/stack-reset.sh
# Full reset: nuke containers + volumes, then bring stack back up clean.
# Useful before running the deterministic baseline construction from scratch.
set -euo pipefail
HERE="$(dirname "$0")"
"$HERE/stack-down.sh" --volumes
"$HERE/stack-up.sh" --wait
