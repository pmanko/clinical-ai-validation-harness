#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [[ ! -f .env.local ]]; then
  python3 - <<'PY'
import os, secrets
fd = os.open('.env.local', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, 'w') as f:
    for name in ['DB_PASSWORD', 'SECRET_KEY', 'ADMIN_PASSWORD']:
        f.write('CSIM_' + name + '=' + secrets.token_hex(24) + '\n')
    f.write('CSIM_SUPERSET_IMAGE=' + os.environ.get('CSIM_SUPERSET_IMAGE', 'apache/superset:6.1.0-dev@sha256:5822dff49c41fd745ce33e38af502f9c64df30d133aeba148c5d89b35a1004ef') + '\n')
PY
fi
compose() {
  if [[ "${CSIM_SERVER:-0}" == 1 ]] || grep -qx 'CSIM_SERVER=1' .env.local; then
    docker compose --env-file .env.local -f compose.yaml -f compose.server.yaml "$@"
  else
    docker compose --env-file .env.local -f compose.yaml "$@"
  fi
}
case "${1:-}" in
  env) echo 'Private synthetic-demo environment is configured.' ;;
  up)
    compose up -d
    compose exec -T superset superset db upgrade
    compose exec -T superset superset init
    ;;
  boot)
    bash ./local.sh up
    bash ./local.sh seed
    bash ./local.sh setup
    ;;
  seed)
    echo 'Loading explicitly synthetic CSiM fixture into the separate local database.'
    compose exec -T db psql -v ON_ERROR_STOP=1 -U csim -d csim_synthetic < sql/synthetic.sql
    compose exec -T db psql -v ON_ERROR_STOP=1 -U csim -d csim_synthetic < sql/baseline.sql
    ;;
  setup) compose exec -T superset python /repro/setup_dashboard.py ;;
  bundle-boot)
    bash ./local.sh up
    bash ./local.sh seed
    compose exec -T db psql -v ON_ERROR_STOP=1 -U csim -d csim_synthetic < sql/antibiotic-fixture.sql
    compose exec -T superset python /repro/bootstrap_bundle.py
    bash ./local.sh bundle-import
    ;;
  bundle-import)
    compose exec -T superset python /repro/bundle.py import
    compose exec -T superset python /repro/bundle.py receipt
    mkdir -p output
    compose cp superset:/tmp/csim-full-dashboard-receipt.json output/full-dashboard-receipt.json
    ;;
  bundle-pack)
    compose exec -T superset python /repro/bundle.py pack
    mkdir -p output
    compose cp superset:/tmp/csim-full-native.zip output/csim-full-native.zip
    ;;
  full-setup)
    compose exec -T db psql -v ON_ERROR_STOP=1 -U csim -d csim_synthetic < sql/antibiotic-fixture.sql
    compose exec -T superset python /repro/setup_full_dashboard.py
    compose cp superset:/tmp/csim-full-dashboard-receipt.json output/full-dashboard-receipt.json
    ;;
  full-test)
    compose exec -T superset python /repro/verify_full.py
    compose cp superset:/tmp/csim-full-verification.json output/full-verification.json
    ;;
  test) compose exec -T superset python /repro/verify.py ;;
  export)
    mkdir -p output
    compose exec -T superset python /repro/verify.py --export
    compose cp superset:/tmp/csim-verification.json output/verification.json
    compose cp superset:/tmp/csim-dashboard-export.zip output/dashboard-export.zip
    ;;
  status) compose ps ;;
  down) compose down ;;
  *) echo 'Usage: ./local.sh {bundle-boot|bundle-import|bundle-pack|boot|up|seed|setup|test|export|full-setup|full-test|status|down}'; exit 2 ;;
esac
