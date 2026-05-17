#!/usr/bin/env bash
# Start a cloudflared quick-tunnel exposing the local LM Studio (port 1234)
# as a public HTTPS URL. Prints the URL to paste into .env.chartsearch.cloud
# as CHARTSEARCH_REMOTE_ENDPOINT_URL.
#
# Quick-tunnels are anonymous (no Cloudflare account needed). They get a
# random *.trycloudflare.com subdomain, valid until the cloudflared process
# stops. Run this in a dedicated terminal; cloudflared logs to stdout and
# the URL appears in the first ~5 seconds.
#
# For a stable URL or auth, switch to a named tunnel + Access policy
# (`cloudflared tunnel login` then `cloudflared tunnel create harness-llm`).

set -euo pipefail

LM_STUDIO_URL="${LM_STUDIO_URL:-http://localhost:1234}"

if ! command -v cloudflared >/dev/null 2>&1; then
  echo "error: cloudflared not installed. brew install cloudflared" >&2
  exit 1
fi

echo "==> probing LM Studio at ${LM_STUDIO_URL}"
if ! curl -fsS -m 3 "${LM_STUDIO_URL}/v1/models" >/dev/null 2>&1; then
  cat >&2 <<EOF
warning: LM Studio not reachable at ${LM_STUDIO_URL}.
         Start it with the local server enabled (Developer → Server Settings →
         "Serve on Local Network", or run \`lms server start --bind 0.0.0.0\`).
         Continuing — cloudflared will start but return 502 until LM Studio is up.
EOF
fi

echo "==> starting cloudflared quick-tunnel → ${LM_STUDIO_URL}"
echo "    (copy the https://*.trycloudflare.com URL below and paste into .env.chartsearch.cloud"
echo "     as CHARTSEARCH_REMOTE_ENDPOINT_URL, appending /v1/chat/completions)"
echo ""

exec cloudflared tunnel --no-autoupdate --url "${LM_STUDIO_URL}"
