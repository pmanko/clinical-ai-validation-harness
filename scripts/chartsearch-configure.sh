#!/usr/bin/env bash
# Configure the running ChartSearchAI module for the dual-provider contract:
#   - the med-agent-hub relay endpoint (hub provider), and
#   - the provider registry: which providers are enabled and which is the default.
# --local-evaluation also selects the existing local E4B router for the bundled
# pipeline. Parent setup uses this mode only after explicit baseline initialization/reset.
# Product-profile selection still comes from hub discovery in the ESM. Every value
# is written through the REST settings API so the module's global-property cache is
# invalidated immediately (no backend restart needed).
#
# Overrides (env): CHARTSEARCH_HUB_ENDPOINT_URL (required),
#   CHARTSEARCH_PROVIDERS_ENABLED (default "bundled,hub" — the dual-provider default;
#   set "bundled" for a hub-less install), CHARTSEARCH_PROVIDERS_DEFAULT (default "bundled").

set -euo pipefail

LOCAL_EVALUATION=0
if [[ "$#" == 1 && "$1" == "--local-evaluation" ]]; then
  LOCAL_EVALUATION=1
elif [[ "$#" != 0 ]]; then
  echo "usage: $0 [--local-evaluation]" >&2
  exit 2
fi

# shellcheck source=scripts/openmrs-settings-lib.sh
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/openmrs-settings-lib.sh"
HUB_ENDPOINT="${CHARTSEARCH_HUB_ENDPOINT_URL:?set CHARTSEARCH_HUB_ENDPOINT_URL}"
PROVIDERS_ENABLED="${CHARTSEARCH_PROVIDERS_ENABLED:-bundled,hub}"
PROVIDERS_DEFAULT="${CHARTSEARCH_PROVIDERS_DEFAULT:-bundled}"

echo "Configuring ChartSearchAI at ${OPENMRS_SETTINGS_BASE_URL}:"
set_openmrs_property "chartsearchai.hub.endpointUrl" "${HUB_ENDPOINT}"
set_openmrs_property "chartsearchai.providers.enabled" "${PROVIDERS_ENABLED}"
set_openmrs_property "chartsearchai.providers.default" "${PROVIDERS_DEFAULT}"

if [[ "${LOCAL_EVALUATION}" == 1 ]]; then
  # Baseline-only setup: both pipelines share the existing small local model.
  # Ordinary updates never invoke this configuration mode.
  set_openmrs_property "chartsearchai.llm.engine" "remote"
  set_openmrs_property "chartsearchai.llm.remote.endpointUrl" \
    "http://host.docker.internal:${LLAMA_ROUTER_PORT:-8077}/v1/chat/completions"
  set_openmrs_property "chartsearchai.llm.remote.modelName" "gemma-e4b"
fi

echo ""
echo "Module status:"
if ! openmrs_curl -fsS -u "${OPENMRS_SETTINGS_USER}:${OPENMRS_SETTINGS_PASS}" \
     "${OPENMRS_SETTINGS_BASE_URL}/ws/rest/v1/module/chartsearchai?v=custom:(uuid,started,version)" 2>/dev/null \
     | python3 -c "import sys,json; d=json.load(sys.stdin); print(f\"  chartsearchai {d.get('version','?')} started={d.get('started')}\")" 2>/dev/null; then
  echo "  (module status unavailable right now; settings above were still written)"
fi
