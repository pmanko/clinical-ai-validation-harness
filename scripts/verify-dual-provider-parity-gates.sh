#!/usr/bin/env bash
set -euo pipefail

# Stable entrypoint for the dual-provider parity contract. The Python evaluator
# owns both phases so its checks can be unit tested without shell subprocesses.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${PARITY_GATE_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"

exec python3 "$SCRIPT_DIR/verify_dual_provider_parity_gates.py" --root "$ROOT" "$@"
