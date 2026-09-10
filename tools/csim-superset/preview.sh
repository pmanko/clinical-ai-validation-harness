#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [[ ! -f .env.preview ]]; then
  python3 - <<'PY'
import json, os, secrets
from pathlib import Path
pin = json.loads(Path('preview.json').read_text())
server = os.environ.get('CSIM_PREVIEW_SERVER') == '1'
settings = {'CSIM_'+name: secrets.token_hex(24) for name in ['DB_PASSWORD','SECRET_KEY','ADMIN_PASSWORD']}
settings.update(CSIM_SUPERSET_IMAGE=pin['image'], CSIM_PORT='18095',
    CSIM_PREVIEW_SERVER='1' if server else '0',
    CSIM_APP_ROOT='/superset-preview' if server else '/',
    CSIM_PUBLIC_HTTPS='1' if server else '0',
    CSIM_PUBLIC_URL='https://catalyst.openelis-global.org/superset-preview' if server else 'http://127.0.0.1:18095')
with os.fdopen(os.open('.env.preview', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as stream:
    for key,value in settings.items(): stream.write(key+'='+value+'\n')
PY
fi
compose() {
  local files=(-f compose.yaml -f compose.preview.yaml)
  if grep -qx 'CSIM_PREVIEW_SERVER=1' .env.preview; then files+=(-f compose.preview.server.yaml); fi
  docker compose --project-name csim-upstream-preview --env-file .env.preview "${files[@]}" "$@"
}
case "${1:-}" in
  up)
    compose up -d
    compose exec -T superset superset db upgrade
    compose exec -T superset superset init
    compose exec -T superset python /repro/bootstrap_bundle.py
    ;;
  seed)
    echo 'Loading invented CSiM records into the separate preview database.'
    for fixture in synthetic baseline antibiotic-fixture; do
      compose exec -T db psql -v ON_ERROR_STOP=1 -U csim -d csim_synthetic < "sql/$fixture.sql"
    done
    ;;
  import)
    compose exec -T superset python /repro/bundle.py import
    compose exec -T superset python /repro/bundle.py receipt
    mkdir -p output
    compose cp superset:/tmp/csim-full-dashboard-receipt.json output/preview-dashboard-receipt.json
    compose exec -T superset python /repro/preview_setup.py
    compose exec -T superset python /repro/verify_preview_import.py
    compose cp superset:/tmp/csim-preview-import-check.json output/preview-import-check.json
    compose exec -T superset python /repro/demo_access.py
    ;;
  test)
    compose exec -T -e CSIM_RECEIPT_PATH=/tmp/csim-full-dashboard-receipt.json superset python /repro/verify_full.py
    compose cp superset:/tmp/csim-full-verification.json output/preview-verification.json
    ;;
  exec) shift; compose exec -T superset "$@" ;;
  status) compose ps ;;
  down) compose down ;;
  *) echo 'Usage: ./preview.sh {up|seed|import|test|exec|status|down}'; exit 2 ;;
esac
