#!/usr/bin/env bash
# Parent entry point. Existing local configuration is read, never rewritten.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"
set -a
. ./.env.chartsearch.example
[ ! -f .env.chartsearch ] || . ./.env.chartsearch
set +a
exec python3 scripts/setup-environment.py "$@"
