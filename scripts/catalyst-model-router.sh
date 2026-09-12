#!/usr/bin/env bash
# Own the containerized external router used by the Catalyst demo deployment.
# Catalyst itself intentionally consumes an external OpenAI-compatible endpoint.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="${ROOT}/compose/catalyst-model-router.yml"
MODELS_FILE="${ROOT}/scripts/catalyst-model-router.models.tsv"
MODEL_DIR="${CATALYST_ROUTER_MODEL_DIR:-${HOME}/.cache/catalyst-router-models}"
ROUTER_PORT="${CATALYST_ROUTER_PORT:-8077}"
ROUTER_URL="http://127.0.0.1:${ROUTER_PORT}"
MODELS_MAX="${CATALYST_ROUTER_MODELS_MAX:-1}"
WARM_MODEL="${CATALYST_ROUTER_WARM_MODEL:-gemma-4-12b-q4}"
NETWORK_ALIAS="${CATALYST_ROUTER_NETWORK_ALIAS:-model-router-candidate}"
READY_TIMEOUT_SECONDS="${CATALYST_ROUTER_READY_TIMEOUT_SECONDS:-300}"

usage() {
  cat <<'EOF'
Usage: scripts/catalyst-model-router.sh {fetch MODEL|verify|config|up|warm [MODEL]|smoke [MODEL]|health|down}

Required for config/up/down:
  CATALYST_ROUTER_PUBLIC_NETWORK       Docker network for the public/rollback Hub
  CATALYST_ROUTER_APPLICATION_NETWORK  Docker network for the current Catalyst Hub

Capacity settings:
  CATALYST_ROUTER_MODELS_MAX  Maximum resident models (default: 1)
  CATALYST_ROUTER_WARM_MODEL  Model loaded after startup (default: gemma-4-12b-q4)
  CATALYST_ROUTER_NETWORK_ALIAS  Network name used by consumers. The safe
                                 default is model-router-candidate; set
                                 model-router only during an intentional cutover.

MODEL is gemma-4-12b-q4 or gemma-e4b. Model downloads use immutable URLs and
are verified before the final filename is installed.
EOF
}

model_record() {
  local alias="$1"
  awk -F '\t' -v wanted="${alias}" '
    $0 !~ /^#/ && $1 == wanted { print; found = 1; exit }
    END { if (!found) exit 1 }
  ' "${MODELS_FILE}"
}

sha256_file() {
  local path="$1"
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "${path}" | awk '{print $1}'
  else
    shasum -a 256 "${path}" | awk '{print $1}'
  fi
}

verify_model() {
  local alias="$1" record filename expected_sha actual
  record="$(model_record "${alias}")" || {
    echo "ERROR: unsupported Catalyst router model: ${alias}" >&2
    return 2
  }
  IFS=$'\t' read -r _ filename expected_sha _ <<<"${record}"
  local path="${MODEL_DIR}/${filename}"
  if [ ! -f "${path}" ]; then
    echo "ERROR: model is missing: ${path}" >&2
    return 1
  fi
  actual="$(sha256_file "${path}")"
  if [ "${actual}" != "${expected_sha}" ]; then
    echo "ERROR: model checksum mismatch: ${path}" >&2
    echo "  expected ${expected_sha}" >&2
    echo "  actual   ${actual}" >&2
    return 1
  fi
  echo "verified ${alias}: ${filename} (${actual})"
}

verify_models() {
  local alias
  while IFS=$'\t' read -r alias _; do
    case "${alias}" in
      ''|'#'*) continue ;;
    esac
    verify_model "${alias}"
  done <"${MODELS_FILE}"
}

fetch_model() {
  local alias="$1" record filename expected_sha source_url partial actual
  record="$(model_record "${alias}")" || {
    echo "ERROR: unsupported Catalyst router model: ${alias}" >&2
    return 2
  }
  IFS=$'\t' read -r _ filename expected_sha source_url <<<"${record}"
  mkdir -p "${MODEL_DIR}"
  local path="${MODEL_DIR}/${filename}"
  if [ -f "${path}" ]; then
    verify_model "${alias}"
    return
  fi
  partial="${path}.partial"
  echo "fetching ${alias} from its pinned source"
  if [ -f "${partial}" ]; then
    curl --fail --location --continue-at - --output "${partial}" "${source_url}"
  else
    curl --fail --location --output "${partial}" "${source_url}"
  fi
  actual="$(sha256_file "${partial}")"
  if [ "${actual}" != "${expected_sha}" ]; then
    echo "ERROR: downloaded model checksum mismatch: ${partial}" >&2
    echo "  expected ${expected_sha}" >&2
    echo "  actual   ${actual}" >&2
    return 1
  fi
  mv "${partial}" "${path}"
  echo "installed verified ${alias}: ${path}"
}

validate_capacity() {
  case "${MODELS_MAX}" in
    ''|*[!0-9]*)
      echo "ERROR: CATALYST_ROUTER_MODELS_MAX must be a non-negative integer" >&2
      return 2
      ;;
  esac
  model_record "${WARM_MODEL}" >/dev/null || {
    echo "ERROR: unsupported CATALYST_ROUTER_WARM_MODEL: ${WARM_MODEL}" >&2
    return 2
  }
}

require_networks() {
  : "${CATALYST_ROUTER_PUBLIC_NETWORK:?set CATALYST_ROUTER_PUBLIC_NETWORK}"
  : "${CATALYST_ROUTER_APPLICATION_NETWORK:?set CATALYST_ROUTER_APPLICATION_NETWORK}"
  docker network inspect "${CATALYST_ROUTER_PUBLIC_NETWORK}" >/dev/null
  docker network inspect "${CATALYST_ROUTER_APPLICATION_NETWORK}" >/dev/null
}

compose() {
  CATALYST_ROUTER_MODEL_DIR="${MODEL_DIR}" \
  CATALYST_ROUTER_MODELS_MAX="${MODELS_MAX}" \
  CATALYST_ROUTER_PORT="${ROUTER_PORT}" \
  CATALYST_ROUTER_NETWORK_ALIAS="${NETWORK_ALIAS}" \
    docker compose -f "${COMPOSE_FILE}" "$@"
}

wait_for_catalog() {
  local attempt
  for attempt in $(seq 1 "${READY_TIMEOUT_SECONDS}"); do
    if curl -fsS --max-time 3 "${ROUTER_URL}/v1/models" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  echo "ERROR: Catalyst model router was not ready after ${READY_TIMEOUT_SECONDS}s" >&2
  compose logs --tail=80 model-router >&2 || true
  return 1
}

warm_model() {
  local alias="$1" response attempt
  model_record "${alias}" >/dev/null || {
    echo "ERROR: unsupported Catalyst router model: ${alias}" >&2
    return 2
  }
  response="$(curl -fsS --max-time 10 \
    -H 'Content-Type: application/json' \
    -d "{\"model\":\"${alias}\"}" \
    "${ROUTER_URL}/models/load")"
  ROUTER_RESPONSE="${response}" python3 - <<'PY'
import json
import os

payload = json.loads(os.environ["ROUTER_RESPONSE"])
if payload.get("success") is not True:
    raise SystemExit(f"router rejected model load: {payload}")
PY
  for attempt in $(seq 1 "${READY_TIMEOUT_SECONDS}"); do
    if curl -fsS --max-time 5 "${ROUTER_URL}/models" \
      | WARM_MODEL="${alias}" python3 -c '
import json, os, sys
models = json.load(sys.stdin).get("data") or []
wanted = os.environ["WARM_MODEL"]
raise SystemExit(0 if any(
    str(item.get("id")) == wanted
    and (item.get("status") or {}).get("value") == "loaded"
    for item in models if isinstance(item, dict)
) else 1)
'; then
      echo "warm model loaded: ${alias}"
      return 0
    fi
    sleep 1
  done
  echo "ERROR: ${alias} did not reach loaded state after ${READY_TIMEOUT_SECONDS}s" >&2
  return 1
}

smoke_model() {
  local alias="$1" response
  warm_model "${alias}"
  response="$(curl -fsS --max-time 1800 \
    -H 'Content-Type: application/json' \
    -d "{\"model\":\"${alias}\",\"messages\":[{\"role\":\"user\",\"content\":\"Reply with OK.\"}],\"max_tokens\":8,\"temperature\":0}" \
    "${ROUTER_URL}/v1/chat/completions")"
  ROUTER_RESPONSE="${response}" MODEL_ALIAS="${alias}" python3 - <<'PY'
import json
import os

payload = json.loads(os.environ["ROUTER_RESPONSE"])
choices = payload.get("choices") or []
content = ((choices[0].get("message") or {}).get("content") if choices else "")
if not str(content or "").strip():
    raise SystemExit(f"router returned no content for {os.environ['MODEL_ALIAS']}")
print(f"router inference passed: {os.environ['MODEL_ALIAS']}")
PY
}

health() {
  local catalog
  catalog="$(curl -fsS --max-time 5 "${ROUTER_URL}/v1/models")"
  ROUTER_CATALOG="${catalog}" WARM_MODEL="${WARM_MODEL}" python3 - <<'PY'
import json
import os

payload = json.loads(os.environ["ROUTER_CATALOG"])
models = {
    str(item.get("id")): item
    for item in payload.get("data") or []
    if isinstance(item, dict) and item.get("id")
}
required = {"gemma-4-12b-q4", "gemma-e4b"}
missing = sorted(required - models.keys())
if missing:
    raise SystemExit(f"router catalog is missing: {', '.join(missing)}")
warm = os.environ["WARM_MODEL"]
status = (models.get(warm, {}).get("status") or {}).get("value")
if status != "loaded":
    raise SystemExit(f"configured warm model {warm} is {status or 'unknown'}")
print(f"router healthy; warm={warm}; catalog={','.join(sorted(models))}")
PY
}

validate_capacity

case "${1:-}" in
  fetch)
    [ "$#" -eq 2 ] || { usage >&2; exit 2; }
    fetch_model "$2"
    ;;
  verify)
    [ "$#" -eq 1 ] || { usage >&2; exit 2; }
    verify_models
    ;;
  config)
    [ "$#" -eq 1 ] || { usage >&2; exit 2; }
    require_networks
    compose config
    ;;
  up)
    [ "$#" -eq 1 ] || { usage >&2; exit 2; }
    verify_models
    require_networks
    compose up -d model-router
    wait_for_catalog
    warm_model "${WARM_MODEL}"
    health
    ;;
  warm)
    [ "$#" -le 2 ] || { usage >&2; exit 2; }
    wait_for_catalog
    warm_model "${2:-${WARM_MODEL}}"
    ;;
  smoke)
    [ "$#" -le 2 ] || { usage >&2; exit 2; }
    wait_for_catalog
    smoke_model "${2:-${WARM_MODEL}}"
    ;;
  health)
    [ "$#" -eq 1 ] || { usage >&2; exit 2; }
    wait_for_catalog
    health
    ;;
  down)
    [ "$#" -eq 1 ] || { usage >&2; exit 2; }
    require_networks
    compose down
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac
