#!/usr/bin/env bash
# scripts/_preflight.sh
# Sourced by harness scripts that need to call python3 with the `harness.*`
# packages. Verifies the operator is running from the repo root with a usable
# Python environment so a missing `.venv` or wrong cwd surfaces as a clear
# one-line error rather than a confusing ModuleNotFoundError mid-script.

# Intentionally not `set -e` here — sourcing scripts should keep their own
# error-handling discipline.

harness_preflight() {
  if [[ ! -f "pyproject.toml" ]] || [[ ! -d "harness" ]]; then
    echo "ERROR: run from the repo root (pwd should contain pyproject.toml + harness/)." >&2
    echo "  current pwd: $(pwd)" >&2
    return 1
  fi
  if ! python3 -c "import harness" 2>/dev/null; then
    echo "ERROR: cannot import 'harness' from python3." >&2
    echo "  Activate the venv first: source .venv/bin/activate" >&2
    echo "  or install via:           make setup" >&2
    return 1
  fi
}
