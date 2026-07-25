#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APPDATA="${OPENMRS_APPLICATION_DATA_DIRECTORY:-${TMPDIR:-/tmp}/chartsearchai-test-appdata}"

mkdir -p "$APPDATA"
cd "$ROOT/targets/chartsearchai"
exec mvn -q -B \
  -DOPENMRS_APPLICATION_DATA_DIRECTORY="$APPDATA" \
  clean install "$@"
