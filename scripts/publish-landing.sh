#!/usr/bin/env bash
# Publish the static OpenClinAI landing page to the existing cloud proxy.
# The landing directory has no build step. The default mode syncs the landing
# and the two proxy config files; --landing-only syncs only the landing. A
# public-site release must not mirror unrelated source trees, ignored caches,
# or other deployment artifacts.
#
# CAUTION (until sources converge on main — see Phase 0 of the consolidation
# roadmap under specs/artifacts/planning/):
# the two proxy config files sync from THIS checkout. Publishing from a branch
# whose compose/Caddyfile differs from the lane that owns the VM's running
# stack overwrites that lane's config on the VM (observed 2026-07-22: a
# cross-branch publish replaced the m2-lane chartsearchai env shape and had to
# be restored). Publish from the checkout that matches the VM's deployment, or
# verify the compose diff first.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PUBLISH_MODE="${1:-full}"
if [ "${PUBLISH_MODE}" != "full" ] && [ "${PUBLISH_MODE}" != "--landing-only" ]; then
  echo "usage: $0 [--landing-only]" >&2
  exit 2
fi
# shellcheck disable=SC1091
. "${ROOT}/scripts/cloud-lib.sh"

echo "==> running landing regression checks"
( cd "${ROOT}" && uv run pytest -q tests/test_landing_site.py )

if ! gcp_vm_exists || [ "$(gcp_vm_status)" != "RUNNING" ]; then
  echo "error: VM ${GCP_VM_NAME} is not running" >&2
  exit 1
fi

if [ "${PUBLISH_MODE}" = "full" ] && [ ! -f "${ROOT}/.env.chartsearch.cloud" ]; then
  echo "error: .env.chartsearch.cloud is required for the published Caddy host" >&2
  exit 1
fi

# The page is the source of truth for which demo-host assets it needs, not a
# list maintained here: a recut changes the <source>/poster URL in
# landing/index.html, and that edit alone must be enough to keep this script
# correct. Extracted before any deployment mutation, so a missing asset (a
# recut published to landing/ before its video/poster reached the demo host)
# fails here and leaves the currently published page untouched.
MEDIA_HOST="https://catalyst.openelis-global.org/media/"
REMOTE_MEDIA_ASSETS=()
while IFS= read -r asset; do
  REMOTE_MEDIA_ASSETS+=("${asset}")
done < <(
  grep -oE "${MEDIA_HOST}[A-Za-z0-9._-]+" "${ROOT}/landing/index.html" | sort -u
)
if [ "${#REMOTE_MEDIA_ASSETS[@]}" -eq 0 ]; then
  echo "error: no ${MEDIA_HOST}<asset> references found in landing/index.html" >&2
  exit 1
fi
echo "==> verifying ${#REMOTE_MEDIA_ASSETS[@]} demo-host asset(s) referenced by landing/index.html"
for asset in "${REMOTE_MEDIA_ASSETS[@]}"; do
  curl -fsS --retry 8 --retry-delay 2 --max-time 30 "${asset}" -o /dev/null
done

IP="$(gcp_vm_ip)"
gcp_ssh_keygen_once
if [ "${PUBLISH_MODE}" = "--landing-only" ]; then
  gcp_ssh "mkdir -p ${GCP_REMOTE_REPO}/landing"
else
  HUB_BUILD_REVISION="$(git -C "${ROOT}/targets/med-agent-hub" rev-parse HEAD)"
  gcp_ssh "mkdir -p ${GCP_REMOTE_REPO}/landing ${GCP_REMOTE_REPO}/compose"
fi

SSH_TRANSPORT="ssh -i ${GCP_SSH_KEY} -o StrictHostKeyChecking=accept-new"
echo "==> syncing tested landing files only"
# No -L: the recordings are no longer symlinked into this tree at all. They are
# served by the Catalyst demo host, and landing/index.html links to them there,
# so landing/ carries only text and the small hand-made poster images.
rsync -avz --delete -e "${SSH_TRANSPORT}" \
  "${ROOT}/landing/" \
  "${GCP_SSH_USER}@${IP}:${GCP_REMOTE_REPO}/landing/"
if [ "${PUBLISH_MODE}" = "--landing-only" ]; then
  echo "==> landing-only mode; proxy configuration and services unchanged"
else
  CONFIG_CHANGES="$(rsync -azc --itemize-changes -e "${SSH_TRANSPORT}" \
    "${ROOT}/compose/Caddyfile" \
    "${ROOT}/compose/openmrs-2.8-refapp.yml" \
    "${GCP_SSH_USER}@${IP}:${GCP_REMOTE_REPO}/compose/")"

  if [ -n "${CONFIG_CHANGES}" ]; then
    echo "==> proxy config changed; recreating only the proxy"
    printf '%s\n' "${CONFIG_CHANGES}"
    gcp_ssh "cd ${GCP_REMOTE_REPO} && export HUB_BUILD_REVISION='${HUB_BUILD_REVISION}' && set -a && . ./.env.chartsearch.cloud && set +a && docker compose -f compose/openmrs-2.8-refapp.yml up -d --no-deps --force-recreate proxy"
  else
    echo "==> proxy config unchanged; no service restart needed"
  fi
fi

if [ "${PUBLISH_MODE}" = "--landing-only" ]; then
  SITE="${CADDY_SITE:-openclinai.org}"
else
  SITE="$(awk -F= '/^CADDY_SITE=/{print $2}' "${ROOT}/.env.chartsearch.cloud" | tail -1)"
  SITE="${SITE:-openclinai.org}"
fi

echo "==> verifying https://${SITE}/"
SITE_HTML="$(curl -fsS --retry 8 --retry-connrefused --retry-delay 2 --max-time 20 "https://${SITE}/")"
grep -Fq '<h1 id="hero-title">Open Clinical AI</h1>' <<<"${SITE_HTML}"
grep -Fq '1:45 · silent recording at 2× speed' <<<"${SITE_HTML}"
grep -Fq '>Catalyst</a>' <<<"${SITE_HTML}"
while IFS= read -r youtube_link; do
  grep -Fq "${youtube_link}" <<<"${SITE_HTML}"
done < <(grep -oE 'https://youtu.be/[A-Za-z0-9_-]+' "${ROOT}/landing/index.html" | sort -u)
curl -fsS --retry 8 --retry-connrefused --retry-delay 2 --max-time 20 "https://${SITE}/media/openmrs-evidence-poster.png" \
  -o /dev/null
# Separate post-publish verification: the demo-host assets were already
# confirmed reachable above, before this deploy touched anything, but the
# published landing/index.html on the VM is what the pre-publish check read
# from THIS checkout -- re-check the same list against the now-live page so a
# transport failure during rsync is not mistaken for success.
for asset in "${REMOTE_MEDIA_ASSETS[@]}"; do
  curl -fsS --retry 8 --retry-delay 2 --max-time 30 "${asset}" -o /dev/null
done

echo "==> published: https://${SITE}/"
