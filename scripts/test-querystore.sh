#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APPDATA="${OPENMRS_APPLICATION_DATA_DIRECTORY:-${TMPDIR:-/tmp}/querystore-test-appdata}"
MODE="${1:-unit}"
if [[ $# -gt 0 ]]; then
  shift
fi

mkdir -p "$APPDATA"
cd "$ROOT/targets/querystore"

case "$MODE" in
  unit)
    exec mvn -q -B \
      -DOPENMRS_APPLICATION_DATA_DIRECTORY="$APPDATA" \
      clean install "$@"
    ;;
  mysql-integration)
    exec mvn -q -B -pl api -Pintegration \
      -DOPENMRS_APPLICATION_DATA_DIRECTORY="$APPDATA" \
      -Dtest=MysqlBackendStoreIntegrationTest \
      test "$@"
    ;;
  *)
    echo "Usage: $0 [unit|mysql-integration] [maven arguments...]" >&2
    exit 2
    ;;
esac
