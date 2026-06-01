#!/usr/bin/env bash
# Tail compose logs from the VM. Pass SERVICE=backend (or any other) to
# filter; default tails all services. Pass FOLLOW=0 to dump the last 200
# lines and exit.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1091
. "${ROOT}/scripts/cloud-lib.sh"

SERVICE="${SERVICE:-}"
FOLLOW="${FOLLOW:-1}"
FLAGS="--tail=200"
[ "${FOLLOW}" = "1" ] && FLAGS="${FLAGS} -f"

gcp_ssh "cd ${GCP_REMOTE_REPO} && docker compose -f compose/openmrs-2.8-refapp.yml logs ${FLAGS} ${SERVICE}"
