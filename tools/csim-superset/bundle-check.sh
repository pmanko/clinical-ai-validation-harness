#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
export CSIM_PORT=18094 CSIM_PUBLIC_URL=http://127.0.0.1:18094
compose() { docker compose -p csim-bundle-check --env-file .env.local -f compose.yaml "$@"; }
case "${1:-}" in
  up)
    if [[ ! -f .env.local ]]; then bash ./local.sh env; fi
    # Dedicated synthetic test volumes, separate from the working demo.
    compose up -d
    compose exec -T superset superset db upgrade
    compose exec -T superset superset init
    compose exec -T superset python /repro/bootstrap_bundle.py
    compose exec -T db psql -v ON_ERROR_STOP=1 -U csim -d csim_synthetic < sql/synthetic.sql
    compose exec -T db psql -v ON_ERROR_STOP=1 -U csim -d csim_synthetic < sql/baseline.sql
    compose exec -T db psql -v ON_ERROR_STOP=1 -U csim -d csim_synthetic < sql/antibiotic-fixture.sql
    ;;
  import)
    compose exec -T superset python /repro/bundle.py import
    compose exec -T superset python /repro/bundle.py receipt
    compose cp superset:/tmp/csim-full-dashboard-receipt.json output/bundle-import-receipt.json
    ;;
  test)
    compose exec -T superset python /repro/verify_bundle.py
    compose exec -T -e CSIM_RECEIPT_PATH=/tmp/csim-full-dashboard-receipt.json superset python /repro/verify_full.py
    compose cp superset:/tmp/csim-full-verification.json output/bundle-verification.json
    compose cp superset:/tmp/csim-bundle-verification.json output/bundle-relationships.json
    ;;
  browser)
    cd e2e
    CSIM_E2E_TARGET=import CSIM_RECORD=1 node run.mjs --grep '0[234568]'
    ;;
  down) compose down ;; # Preserve test volumes for inspecting failures.
  *) echo 'Usage: bundle-check.sh {up|import|test|browser|down}'; exit 2 ;;
esac
