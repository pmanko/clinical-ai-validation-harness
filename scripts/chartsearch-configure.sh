#!/usr/bin/env bash
# Configure the running ChartSearchAI module to relay through one med-agent-hub
# endpoint and select one product profile. Profile discovery remains owned by the
# hub; this script does not register raw model providers or compose stages.

set -euo pipefail

# shellcheck source=scripts/openmrs-settings-lib.sh
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/openmrs-settings-lib.sh"
HUB_ENDPOINT="${CHARTSEARCH_HUB_ENDPOINT_URL:?set CHARTSEARCH_HUB_ENDPOINT_URL}"
HUB_PROFILE="${CHARTSEARCH_HUB_PROFILE_ID:?set CHARTSEARCH_HUB_PROFILE_ID}"

echo "Configuring ChartSearchAI hub relay at ${OPENMRS_SETTINGS_BASE_URL}:"
set_openmrs_property "chartsearchai.hub.endpointUrl" "${HUB_ENDPOINT}"
set_openmrs_property "chartsearchai.hub.profileId" "${HUB_PROFILE}"

echo ""
echo "Module status:"
if ! openmrs_curl -fsS -u "${OPENMRS_SETTINGS_USER}:${OPENMRS_SETTINGS_PASS}" \
     "${OPENMRS_SETTINGS_BASE_URL}/ws/rest/v1/module/chartsearchai?v=custom:(uuid,started,version)" 2>/dev/null \
     | python3 -c "import sys,json; d=json.load(sys.stdin); print(f\"  chartsearchai {d.get('version','?')} started={d.get('started')}\")" 2>/dev/null; then
  echo "  (module status unavailable right now; settings above were still written)"
fi
